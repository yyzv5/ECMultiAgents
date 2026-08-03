"""Milvus 客户端: 封装混合检索与重排的完整链路。

使用 BGE-M3 (FlagEmbedding) 进行稠密+稀疏双向量编码，
通过 Milvus hybrid_search + WeightedRanker 融合，
再经 BGE-Reranker 精排和 Sigmoid 置信度映射。

所有配置从 :mod:`backend.config` 读取，不硬编码。
模型路径通过 ``settings.EMBEDDING_MODEL_PATH`` 和 ``settings.RERANKER_MODEL_PATH`` 配置，
默认指向项目本地 ``src/backend/models/files/`` 目录。
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING

from backend.config import settings

if TYPE_CHECKING:
    import torch
    from FlagEmbedding import BGEM3FlagModel
    from transformers import PreTrainedModel, PreTrainedTokenizerBase

logger = logging.getLogger(__name__)

# 项目根目录（src/backend/ 的上两级）
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class MilvusClient:
    """Milvus 混合检索客户端。"""

    def __init__(self) -> None:
        """连接 Milvus 并加载 Collection（不加载 ML 模型）。

        Raises:
            RuntimeError: Milvus 连接失败或 Collection 不存在。
        """
        self._connect_milvus()
        self._load_collection()

        # ML 模型惰性加载
        self._embed_model: BGEM3FlagModel | None = None
        self._reranker_model: PreTrainedModel | None = None
        self._reranker_tokenizer: PreTrainedTokenizerBase | None = None

    def _connect_milvus(self) -> None:
        """连接 Milvus 服务器。"""
        from pymilvus import connections

        connections.connect(
            alias="default",
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
        )
        logger.info(
            "Milvus connected: %s:%s",
            settings.MILVUS_HOST,
            settings.MILVUS_PORT,
        )

    def _load_collection(self) -> None:
        """加载 Collection 到内存。"""
        from pymilvus import Collection
        from pymilvus.exceptions import CollectionNotExistException

        name = settings.MILVUS_COLLECTION
        try:
            self._collection = Collection(name)
        except CollectionNotExistException:
            msg = (
                f"Milvus collection '{name}' not found. "
                "Run 'python src/backend/db/init_data.py' to create it."
            )
            raise RuntimeError(msg)

        self._collection.load()
        logger.info("Collection '%s' loaded into memory.", name)

    def _load_embed_model(self) -> BGEM3FlagModel:
        """惰性加载 BGE-M3 编码模型（本地路径）。"""
        if self._embed_model is None:
            from FlagEmbedding import BGEM3FlagModel

            model_path = str(_PROJECT_ROOT / settings.EMBEDDING_MODEL_PATH)
            logger.info("Loading BGE-M3 embedding model from %s ...", model_path)
            self._embed_model = BGEM3FlagModel(model_path, use_fp16=True)
            logger.info("BGE-M3 model loaded.")
        return self._embed_model

    def _load_reranker(self) -> tuple[PreTrainedModel, PreTrainedTokenizerBase]:
        """惰性加载 BGE-Reranker 模型（本地路径，transformers 直接加载）。"""
        if self._reranker_model is None:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            model_path = str(_PROJECT_ROOT / settings.RERANKER_MODEL_PATH)
            logger.info("Loading BGE-Reranker model from %s ...", model_path)
            self._reranker_tokenizer = AutoTokenizer.from_pretrained(model_path)
            self._reranker_model = AutoModelForSequenceClassification.from_pretrained(
                model_path, dtype=torch.float16
            )
            self._reranker_model.eval()
            logger.info("BGE-Reranker model loaded.")
        return self._reranker_model, self._reranker_tokenizer

    # ── 编码接口 ──

    def embed_query(
        self, text: str
    ) -> tuple[list[float], dict[int, float]]:
        """编码单条 query，返回 (稠密向量, 稀疏权重)。

        Args:
            text: 查询文本。

        Returns:
            (dense_vec, sparse_weights) — dense 为 list[float]，sparse 为 {token_id: weight}。
        """
        model = self._load_embed_model()
        result = model.encode(
            text,
            return_dense=True,
            return_sparse=True,
        )
        dense = result["dense_vecs"]
        if hasattr(dense, "tolist"):
            dense = dense.tolist()
        if isinstance(dense, list) and len(dense) > 0 and isinstance(dense[0], list):
            dense = dense[0]

        sparse = result["lexical_weights"]
        if isinstance(sparse, list):
            sparse = sparse[0]

        # BGE-M3 返回 str keys + numpy.float32，统一转 int + float
        sparse = {int(k): float(v) for k, v in sparse.items()}

        return dense, sparse

    def embed_documents(
        self, texts: list[str]
    ) -> tuple[list[list[float]], list[dict[int, float]]]:
        """批量编码文档，返回 (稠密向量列表, 稀疏权重列表)。

        Args:
            texts: 文档文本列表。

        Returns:
            (dense_vecs, sparse_vecs) — 两个列表长度与 texts 相同。
        """
        model = self._load_embed_model()
        result = model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
        )
        dense_vecs = result["dense_vecs"]
        if hasattr(dense_vecs, "tolist"):
            dense_vecs = dense_vecs.tolist()

        sparse_vecs = result["lexical_weights"]

        # BGE-M3 返回 str keys + numpy.float32，统一转 int + float
        sparse_vecs = [
            {int(k): float(v) for k, v in sw.items()} for sw in sparse_vecs
        ]

        return dense_vecs, sparse_vecs

    # ── 稀疏向量格式转换 ──

    @staticmethod
    def _sparse_to_milvus(lexical_weights: dict[int, float]) -> dict[str, list]:
        """BGE-M3 稀疏权重 → Milvus 稀疏向量格式。

        Args:
            lexical_weights: {token_id: weight}。

        Returns:
            {"indices": [...], "values": [...]}。

        Note:
            该 dict 格式仅用于内部中转;传给 ``AnnSearchRequest`` 时
            必须再转成 ``[(token_id, weight), ...]`` pairs 列表 ——
            pymilvus 2.6 的 ``entity_is_sparse_matrix`` 只识别 pairs
            或 scipy CSR,对 dict 会误判为稠密向量导致 ``struct.error``。
        """
        if not lexical_weights:
            return {"indices": [], "values": []}
        indices = list(lexical_weights.keys())
        values = list(lexical_weights.values())
        return {"indices": indices, "values": values}

    @staticmethod
    def _sparse_to_pairs(lexical_weights: dict[int, float]) -> list[tuple[int, float]]:
        """BGE-M3 稀疏权重 → Milvus ``AnnSearchRequest`` 接受的行格式。

        pymilvus 2.6 的 ``entity_is_sparse_matrix`` 要求稀疏行是
        ``[(token_id, weight), ...]`` 元组列表(或 scipy CSR 单行);
        ``{"indices": [...], "values": [...]}`` dict 格式会被误判为稠密
        向量,触发 ``struct.error: required argument is not a float``。

        Args:
            lexical_weights: {token_id: weight}。

        Returns:
            ``[(token_id, weight), ...]`` 列表。
        """
        return [(int(k), float(v)) for k, v in lexical_weights.items()]

    @staticmethod
    def _sparse_to_csr_rows(
        sparse_weights_list: list[dict[int, float]],
    ) -> "csr_matrix":
        """BGE-M3 稀疏权重列表 → scipy CSR 稀疏矩阵（ORM insert 用）。

        pymilvus 2.6 的 ``Collection.insert`` 稀疏向量字段接受 scipy
        ``csr_matrix``（整批一行一向量），而 ``_sparse_to_milvus`` 的 dict
        格式仅 ``hybrid_search`` 的 ``AnnSearchRequest`` 接受。
        """
        import scipy.sparse as sp

        rows, cols, vals = [], [], []
        for row_idx, weights in enumerate(sparse_weights_list):
            for token_id, weight in weights.items():
                rows.append(row_idx)
                cols.append(token_id)
                vals.append(weight)
        return sp.csr_matrix(
            (vals, (rows, cols)),
            shape=(len(sparse_weights_list), max(cols) + 1 if cols else 0),
        )

    # ── Sigmoid ──

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Sigmoid 映射: logit → 置信度 (0~1)。"""
        return 1.0 / (1.0 + math.exp(-x))

    # ── 混合检索 ──

    def hybrid_search(self, query: str, top_k: int | None = None) -> list[dict]:
        """完整检索链路：编码 → 混合检索 → 重排 → 置信度。

        Args:
            query: 用户查询文本。
            top_k: 精排后保留的结果数。默认使用 ``settings.RERANKER_TOP_K``。

        Returns:
            按置信度降序排列的结果列表，每条含 text、source、hybrid_score、
            rerank_logit、confidence。
        """
        import torch
        from pymilvus import AnnSearchRequest, WeightedRanker

        if top_k is None:
            top_k = settings.RERANKER_TOP_K

        # 1. 编码
        dense_vec, sparse_weights = self.embed_query(query)

        # 2. 构建 AnnSearchRequest
        req_dense = AnnSearchRequest(
            data=[dense_vec],
            anns_field="dense_vector",
            param={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=settings.MILVUS_HYBRID_TOP_K,
        )
        req_sparse = AnnSearchRequest(
            data=[self._sparse_to_pairs(sparse_weights)],
            anns_field="sparse_vector",
            param={"metric_type": "IP", "params": {}},
            limit=settings.MILVUS_HYBRID_TOP_K,
        )

        # 3. WeightedRanker 融合
        ranker = WeightedRanker(
            settings.MILVUS_DENSE_WEIGHT,
            settings.MILVUS_SPARSE_WEIGHT,
        )

        # 4. Milvus hybrid_search
        search_results = self._collection.hybrid_search(
            reqs=[req_dense, req_sparse],
            rerank=ranker,
            limit=settings.MILVUS_HYBRID_TOP_K,
            output_fields=["text", "source"],
        )

        # search_results[0] 是第一组（也是唯一一组）的结果
        hits = search_results[0]
        if not hits:
            return []

        # 5. 提取文本、来源、融合分数
        texts: list[str] = []
        metas: list[dict] = []
        for hit in hits:
            text = hit.get("text")
            source = hit.get("source")
            texts.append(text)
            metas.append({
                "text": text,
                "source": source,
                "hybrid_score": hit.distance,
            })

        # 6. Reranker 精排
        reranker_model, reranker_tokenizer = self._load_reranker()
        pairs = [[query, text] for text in texts]
        inputs = reranker_tokenizer(
            pairs, padding=True, truncation=True,
            return_tensors="pt", max_length=512,
        )
        with torch.no_grad():
            logits_tensor = reranker_model(**inputs).logits.squeeze(-1)
        logits: list[float] = (
            logits_tensor.tolist()
            if logits_tensor.ndim > 0
            else [logits_tensor.item()]
        )

        # 7. Sigmoid 置信度 + 排序
        for i, logit in enumerate(logits):
            metas[i]["rerank_logit"] = logit
            metas[i]["confidence"] = self._sigmoid(logit)

        metas.sort(key=lambda x: x["confidence"], reverse=True)

        # 8. 取前 top_k 条
        return metas[:top_k]

    # ── 批量插入 ──

    def insert(self, docs: list[dict]) -> None:
        """批量插入文档到 Milvus。

        每个 doc 需含 "text" 和 "source" 字段。内部自动进行 BGE-M3 编码。

        Args:
            docs: [{"text": "...", "source": "..."}, ...]
        """
        if not docs:
            return

        texts = [d["text"] for d in docs]
        sources = [d["source"] for d in docs]

        # 编码
        dense_vecs, sparse_weights_list = self.embed_documents(texts)

        # 转换稀疏向量格式（ORM insert 用 scipy CSR）
        sparse_vecs = self._sparse_to_csr_rows(sparse_weights_list)

        # 构造插入数据（字段顺序须与 Schema 一致：text, source, dense_vector, sparse_vector）
        data = [
            texts,
            sources,
            dense_vecs,
            sparse_vecs,
        ]

        self._collection.insert(data)
        self._collection.flush()
        logger.info("Inserted %d documents into '%s'.", len(docs), settings.MILVUS_COLLECTION)

    def close(self) -> None:
        """断开 Milvus 连接，释放资源。"""
        from pymilvus import connections

        connections.disconnect("default")
        logger.info("Milvus connection closed.")


__all__ = ["MilvusClient"]
