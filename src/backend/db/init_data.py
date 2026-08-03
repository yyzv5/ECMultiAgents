"""离线演示数据初始化脚本(M4.4)。

独立运行:
    python src/backend/db/init_data.py              # 全量初始化(PG + Milvus)
    python src/backend/db/init_data.py --skip-milvus # 仅 PG

功能:
    1. ``metadata.create_all(engine)`` 建所有 ORM 表(含 users)。
    2. 插入 36 条 ``product_sales`` + 36 条 ``ad_performance`` 演示数据。
    3. 创建 Milvus ``knowledge_base`` Collection(5 字段 Schema + 双索引)。
    4. 插入 20 条跨境运营知识文档。

幂等性:
    - PG: 插入前检查 ``SELECT count(*)``，非零则跳过。
    - Milvus: ``has_collection()`` 检查已存在则跳过创建;
      ``client.insert(docs)`` 不做额外检查(同主键由 Milvus 自动去重)。
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from backend.models.user import Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ───────────────────────────── PG 数据生成 ─────────────────────────────

# 3 个 ASIN × 3 平台,用于演示
_PRODUCTS = [
    {
        "asin": "B0C123456A",
        "title": "无线蓝牙耳机 TWS 降噪运动入耳式",
        "category": "电子产品",
    },
    {
        "asin": "B0C789012B",
        "title": "iPhone 16 Pro 透明防摔手机壳",
        "category": "手机配件",
    },
    {
        "asin": "B0C345678C",
        "title": "20000mAh 快充移动电源 PD 65W",
        "category": "电子产品",
    },
]

_PLATFORMS = [
    {"name": "Amazon",     "currency": "USD"},
    {"name": "Shopee",     "currency": "SGD"},
    {"name": "AliExpress", "currency": "CNY"},
]

# 基础销量参数 (per-day base, 会按月做波动)
_SALES_PARAMS: dict[str, dict[str, tuple[float, int, int, int]]] = {
    # asin → {platform: (base_sales, base_units, base_pv, base_sessions)}
    "B0C123456A": {
        "Amazon":     (8500.0,  85, 12000, 8000),
        "Shopee":     (3200.0,  60,  8000, 5500),
        "AliExpress": (15000.0, 100, 6000, 4000),
    },
    "B0C789012B": {
        "Amazon":     (4200.0, 140, 18000, 12000),
        "Shopee":     (2100.0, 200, 15000, 10000),
        "AliExpress": (8000.0, 320,  9000,  6000),
    },
    "B0C345678C": {
        "Amazon":     (6800.0,  68, 10000, 7000),
        "Shopee":     (2500.0,  50,  6000, 4000),
        "AliExpress": (12000.0, 90,  5000, 3500),
    },
}

# 月度波动系数 (月份 → 系数, 7 月为旺季)
_MONTH_FACTOR = {5: 0.85, 6: 1.0, 7: 1.25}

# 广告活动模板
_CAMPAIGNS = {
    "B0C123456A": "BT_Headphone_SP",
    "B0C789012B": "PhoneCase_SP",
    "B0C345678C": "PowerBank_SP",
}


def _generate_pg_data() -> tuple[list[dict], list[dict]]:
    """生成 ≥30 条 product_sales + ≥30 条 ad_performance 演示数据。

    每个 ASIN × 平台 × 月份 生成 2 条销售记录（上/下半月各一条）。
    3 ASIN × 3 平台 × 3 月 × 2 = 54 条销售记录。
    广告数据 3 ASIN × 3 平台 × 3 月 = 27 条 SP + 9 条 SB = 36 条。

    Returns:
        (sales_rows, ad_rows) — 两个 list[dict],可直接用于 ORM 构造。
    """
    sales_rows: list[dict] = []
    ad_rows: list[dict] = []

    for prod in _PRODUCTS:
        asin = prod["asin"]
        for plat in _PLATFORMS:
            pname = plat["name"]
            params = _SALES_PARAMS[asin][pname]
            base_sales, base_units, base_pv, base_sess = params

            for month in (5, 6, 7):
                factor = _MONTH_FACTOR[month]
                # 月初 + 月末两条记录（上/下半月各一条）
                for day in (1, 15):
                    d = date(2026, month, day)
                    half_month_factor = 0.55 if day == 1 else 0.45
                    sales_val = round(base_sales * 30 * factor * half_month_factor, 2)
                    units_val = max(1, int(base_units * 30 * factor * half_month_factor))
                    pv_val = max(1, int(base_pv * 30 * factor * half_month_factor))
                    sess_val = max(1, int(base_sess * 30 * factor * half_month_factor))

                    sales_rows.append({
                        "platform": pname,
                        "asin": asin,
                        "title": prod["title"],
                        "category": prod["category"],
                        "date": d,
                        "currency": plat["currency"],
                        "sales": sales_val,
                        "units": units_val,
                        "page_views": pv_val,
                        "sessions": sess_val,
                    })

                # 广告数据（每月一条）
                d = date(2026, month, 15)
                impressions = int(base_pv * 30 * factor * 1.5)
                clicks = max(1, int(impressions * 0.03))
                spend = round(clicks * 0.8, 2)
                ad_sales_val = round(base_sales * 30 * factor * 0.4, 2)
                orders = max(1, int(base_units * 30 * factor * 0.35))
                acos = round(spend / ad_sales_val, 4) if ad_sales_val else 0.0
                ctr = round(clicks / impressions, 4) if impressions else 0.0
                cpc = round(spend / clicks, 4) if clicks else 0.0

                ad_rows.append({
                    "platform": pname,
                    "asin": asin,
                    "campaign": _CAMPAIGNS[asin],
                    "ad_type": "SP",
                    "date": d,
                    "impressions": impressions,
                    "clicks": clicks,
                    "spend": spend,
                    "ad_sales": ad_sales_val,
                    "orders": orders,
                    "acos": acos,
                    "ctr": ctr,
                    "cpc": cpc,
                })

    # 补充到 ≥30 条: 为每个 ASIN 追加 1 条 SB (品牌推广) 5 月记录
    for prod in _PRODUCTS:
        asin = prod["asin"]
        for plat in _PLATFORMS:
            pname = plat["name"]
            params = _SALES_PARAMS[asin][pname]
            base_sales, base_units, base_pv, base_sess = params
            d = date(2026, 5, 1)
            impressions = int(base_pv * 0.5)
            clicks = max(1, int(impressions * 0.02))
            spend = round(clicks * 1.2, 2)
            ad_sales_val = round(base_sales * 15 * 0.25, 2)
            orders = max(1, int(base_units * 15 * 0.2))
            acos = round(spend / ad_sales_val, 4) if ad_sales_val else 0.0
            ctr = round(clicks / impressions, 4) if impressions else 0.0
            cpc = round(spend / clicks, 4) if clicks else 0.0

            ad_rows.append({
                "platform": pname,
                "asin": asin,
                "campaign": _CAMPAIGNS[asin].replace("_SP", "_SB"),
                "ad_type": "SB",
                "date": d,
                "impressions": impressions,
                "clicks": clicks,
                "spend": spend,
                "ad_sales": ad_sales_val,
                "orders": orders,
                "acos": acos,
                "ctr": ctr,
                "cpc": cpc,
            })

    logger.info("Generated %d sales rows, %d ad rows.", len(sales_rows), len(ad_rows))
    return sales_rows, ad_rows


# ───────────────────────────── Milvus 文档生成 ─────────────────────────────


def _generate_milvus_docs() -> list[dict]:
    """生成 20 条跨境运营知识文档。

    分类:
        - platform_rules  (5): 平台规则
        - logistics       (3): 物流与仓储
        - compliance      (3): 合规与税务
        - strategy        (4): 运营策略
        - market          (3): 市场分析
        - after_sales     (2): 售后与风控

    Returns:
        ``[{"text": "...", "source": "..."}, ...]``
    """
    docs: list[dict] = [
        # ── platform_rules ──
        {
            "text": (
                "FBA入库要求：商品必须贴有FBA标签(FNSKU),外箱标签清晰可扫描。"
                "每个商品需独立包装,液体类需密封防漏。超尺寸商品(单边>63cm)需走"
                "大件通道,费用更高。入库前需在Seller Central创建Shipment Plan,"
                "选择分仓或合仓策略。旺季(10-12月)入库限制更严,建议提前8周备货。"
            ),
            "source": "platform_rules",
        },
        {
            "text": (
                "Shopee发货规范：订单确认后需在DTS(Days to Ship)内点击发货,"
                "一般为2个工作日。使用Shopee支持的物流渠道(SLS标准物流或合作快递),"
                "超时未发货将计入Late Shipment Rate,影响店铺评分。"
                "大促期间Shopee会延长DTS,需关注Seller Center公告。"
                "东南亚六国(新马泰印尼越南菲律宾)各有不同禁运清单。"
            ),
            "source": "platform_rules",
        },
        {
            "text": (
                "AliExpress卖家发货规范：速卖通要求卖家在承诺发货期内(通常5-7天)"
                "完成发货并上传物流单号。使用官方物流(无忧物流/菜鸟)可享受"
                "平台保障和纠纷优先处理。自发货需确保物流可追踪,否则"
                "平台判定纠纷时卖家举证困难。俄罗斯、巴西等热门目的地"
                "有推荐物流方案,时效和价格差异大。"
            ),
            "source": "platform_rules",
        },
        {
            "text": (
                "Amazon Buy Box竞争要素：价格竞争力(含运费)是首要因素,其次"
                "是FBA配送优势、卖家绩效指标(Order Defect Rate<1%, Late Shipment<4%)、"
                "库存深度和商品信息完整度。使用FBA自动获得Prime标识,显著提升"
                "Buy Box获得率。跟卖时注意品牌备案保护,避免侵权投诉。"
            ),
            "source": "platform_rules",
        },
        {
            "text": (
                "Shopee平台佣金与费率：各站点佣金率不同,一般在1%-6%之间,"
                "部分品类有额外服务费。Shopee Mall商家佣金较高(5%-6%)但享有"
                "更多流量扶持。交易手续费约2%。参加Free Shipping Voucher"
                "活动的订单平台补贴部分运费。大促期间平台会临时调整费率政策。"
            ),
            "source": "platform_rules",
        },
        # ── logistics ──
        {
            "text": (
                "FBA头程物流选择：空运(5-10天,适合高货值/轻小件)、"
                "海运(25-40天,适合大货量/低货值)、快递(3-5天,紧急补货)。"
                "海运拼柜(CCL)每立方约$80-150,整柜(20GP)约$2000-3500。"
                "建议混合策略:常规走海运保成本,空运应急补货防断货。"
                "头程服务商选择需考虑清关能力、派送时效和丢件率。"
            ),
            "source": "logistics",
        },
        {
            "text": (
                "海外仓模式优势与风险：海外仓可实现本地发货(1-3天签收),"
                "提升买家体验和复购率。适合大件商品(家具、户外用品)避免FBA超尺寸费。"
                "但海外仓需提前备货,滞销风险高;仓储费按体积/天计费,"
                "滞销超6个月成本激增。建议结合销售预测做JIT(准时制)补货,"
                "并设置库存红线预警机制。"
            ),
            "source": "logistics",
        },
        {
            "text": (
                "Shopee SLS物流追踪与异常处理：SLS(Shopee Logistics Service)"
                "提供从揽收到妥投的全链路追踪。物流异常常见类型:超时未揽收"
                "(联系快递员或换渠道)、中转停滞(提交工单催促)、"
                "派送失败(确认地址正确性)。卖家可在Seller Center"
                "批量导出物流状态,及时处理异常订单避免纠纷。"
            ),
            "source": "logistics",
        },
        # ── compliance ──
        {
            "text": (
                "欧盟VAT合规要点：在欧盟国家有库存(含FBA)即触发VAT注册义务。"
                "需在存放库存的每个国家注册VAT号并按时申报(月度或季度)。"
                "2021年7月起实施IOSS(Import One-Stop Shop),≤€150的直邮小包"
                "可由平台代扣VAT。亚马逊提供VAT Calculation Service(VCS)"
                "自动计算税额。未合规将面临账号冻结和罚款。"
            ),
            "source": "compliance",
        },
        {
            "text": (
                "美国销售税合规：美国各州税率和规则不同,2018年South Dakota v. "
                "Wayfair案后各州可对远程卖家征收销售税。经济关联(Economic Nexus)"
                "标准通常为年销售额>$100K或200笔交易。FBA库存所在州自动构成"
                "实体关联(Physical Nexus)。建议使用TaxJar/Avalara等工具"
                "自动计算和申报。Marketplace Facilitator法下平台代收代缴的州"
                "卖家无需自行申报。"
            ),
            "source": "compliance",
        },
        {
            "text": (
                "跨境电商知识产权风险防控：上架前必须检查商标(USPTO/EUIPO/CNIPA)"
                "和专利(外观/实用)。常见侵权类型:商标侵权(使用他人品牌词)、"
                "外观专利侵权(产品外形相似)、版权侵权(盗用图片/文案)。"
                "收到侵权投诉后立即下架相关Listing,准备申诉材料"
                "(采购发票、授权书、不侵权分析)。建立上架前IP审查SOP"
                "可大幅降低被诉风险。"
            ),
            "source": "compliance",
        },
        # ── strategy ──
        {
            "text": (
                "跨境定价策略：建议采用「成本加成法」为基础,公式为: "
                "售价=(采购成本+头程运费+FBA费用+平台佣金+广告预算)×目标利润率系数。"
                "同时参考竞品价格带和BSR排名定价。新品期可低价冲量(利润率15-20%),"
                "稳定后提价至30-40%。定期监控竞品价格变动,使用自动调价工具"
                "(如RepricerExpress)保持Buy Box竞争力。"
            ),
            "source": "strategy",
        },
        {
            "text": (
                "Amazon PPC广告优化要点：新品期建议开启自动广告(Discovery)收集"
                "有效关键词,2周后提取高转化词开手动精准匹配。ACOS目标控制在"
                "25-30%(视品类毛利而定)。否定关键词每周更新,排除无关流量。"
                "Sponsored Brands适合品牌曝光,SD广告适合再营销。"
                "建议每日预算不低于$20,避免预算过早耗尽错过晚间流量高峰。"
            ),
            "source": "strategy",
        },
        {
            "text": (
                "库存管理最佳实践：使用IPI(Inventory Performance Index)评分"
                "监控FBA库存健康度,目标>500。核心指标:售罄率(Sell-Through Rate),"
                "理想值为7-90天覆盖;滞销率(>90天无销售的SKU占比)应<10%。"
                "补货公式:安全库存=日均销量×(采购周期+运输周期+安全天数)。"
                "旺季备货量为日常的1.5-2倍,但需考虑库容限制。"
            ),
            "source": "strategy",
        },
        {
            "text": (
                "多平台运营差异化策略：Amazon主打高客单价品牌化商品,"
                "投入品牌备案+A+内容提升转化。Shopee侧重性价比和社交电商,"
                "利用直播和Feed互动引流。AliExpress适合工厂直销,"
                "价格竞争力为王。库存可共享(同一SKU多平台销售),"
                "但需实时同步库存避免超卖。建议使用ERP系统(如马帮/店小秘)"
                "统一管理多平台订单和库存。"
            ),
            "source": "strategy",
        },
        # ── market ──
        {
            "text": (
                "东南亚电商市场分析：2025年东南亚电商GMV预计突破$2300亿,"
                "年增长率约15%。印尼(占40%)和泰国(占18%)是最大市场。"
                "Shopee和Lazada为两大主导平台。消费者偏好低价、COD(货到付款)"
                "比例高、移动端购物占90%以上。热门品类:美妆个护、"
                "手机配件、家居用品。物流基础设施持续改善,但岛屿国家"
                "(印尼、菲律宾)配送时效仍是挑战。"
            ),
            "source": "market",
        },
        {
            "text": (
                "欧洲跨境电商市场洞察：欧洲电商市场规模约€9000亿,"
                "英德法意西为Top5市场。Amazon.de和Amazon.co.uk是中国卖家"
                "主阵地。消费者对品质和售后要求高,退换货率15-25%(服饰类更高)。"
                "CE认证是电子产品准入门槛,WEEE(电子废弃物)和"
                "REACH(化学品)法规需合规。英国脱欧后需单独处理VAT和海关。"
            ),
            "source": "market",
        },
        {
            "text": (
                "北美市场竞争格局：美国电商市场超$1.1万亿,Amazon占38%份额。"
                "竞争最激烈的品类:电子产品、家居、运动户外。"
                "新卖家突围路径:1)利基市场(Niche)切入避免正面竞争; "
                "2)差异化产品(微创新/组合装); 3)品牌化运营"
                "(注册商标+A+内容+品牌旗舰店)。TikTok Shop快速增长,"
                "社交电商成为新增量渠道。"
            ),
            "source": "market",
        },
        # ── after_sales ──
        {
            "text": (
                "跨境电商退货处理流程：Amazon FBA退货自动处理(买家直接退回"
                "亚马逊仓库),卖家需关注退货原因码并定期检查退货报告。"
                "高退货率(>品类平均)会导致Listing被降权甚至下架。"
                "Shopee退货需在2天内响应,提供退款或补发方案。"
                "建议设置退货地址为海外仓或第三方退货处理中心,"
                "降低国际退运费。部分低货值商品可直接退款不退货(Refund Without Return)。"
            ),
            "source": "after_sales",
        },
        {
            "text": (
                "差评应对与账号安全：收到1-2星差评后,先分析是否为产品质量问题"
                "(需改进供应链)还是物流/描述不符(可优化Listing)。"
                "通过Buyer-Seller Message联系买家提供解决方案并请求修改评价"
                "(不可利诱或威胁,违反平台政策)。恶意差评可通过Report Abuse"
                "举报。账号安全要点:开启两步验证(2FA)、定期更换密码、"
                "不在公共WiFi操作Seller Central、警惕钓鱼邮件"
                "(官方邮件不含链接要求登录)。"
            ),
            "source": "after_sales",
        },
    ]
    logger.info("Generated %d Milvus knowledge docs.", len(docs))
    return docs


# ───────────────────────────── PG 初始化 ─────────────────────────────


def _init_pg(engine, SessionLocal) -> None:
    """建表并插入 PG 演示数据(幂等)。

    Args:
        engine: SQLAlchemy Engine 实例。
        SessionLocal: sessionmaker 工厂。
    """
    logger.info("[PG] Creating tables via metadata.create_all ...")
    Base.metadata.create_all(engine)
    logger.info("[PG] Tables created (or already exist).")

    session = SessionLocal()
    try:
        from sqlalchemy import text

        count = session.execute(text("SELECT count(*) FROM product_sales")).scalar()
        if count and count > 0:
            logger.info("[PG] product_sales already has %d rows, skipping insert.", count)
            return

        sales_rows, ad_rows = _generate_pg_data()

        from backend.models.product import AdPerformance, ProductSale

        for row in sales_rows:
            session.add(ProductSale(**row))
        for row in ad_rows:
            session.add(AdPerformance(**row))

        session.commit()
        logger.info("[PG] Inserted %d sales + %d ad rows.", len(sales_rows), len(ad_rows))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ───────────────────────────── Milvus 初始化 ─────────────────────────────


def _init_milvus() -> None:
    """创建 Milvus Collection 并插入知识文档(幂等)。

    Schema: id / text / source / dense_vector(1024) / sparse_vector
    索引:  dense_vector → IVF_FLAT(IP, nlist=128)
           sparse_vector → SPARSE_INVERTED_INDEX(IP)
    """
    from pymilvus import (
        Collection,
        CollectionSchema,
        DataType,
        FieldSchema,
        connections,
        utility,
    )

    from backend.config import settings

    logger.info("[Milvus] Connecting to %s:%s ...", settings.MILVUS_HOST, settings.MILVUS_PORT)
    connections.connect(alias="default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT)

    collection_name = settings.MILVUS_COLLECTION

    if utility.has_collection(collection_name):
        logger.info("[Milvus] Collection '%s' already exists, skipping creation.", collection_name)
        collection = Collection(collection_name)
    else:
        logger.info("[Milvus] Creating collection '%s' ...", collection_name)
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=1024),
            FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
        ]
        schema = CollectionSchema(fields, description="跨境运营知识库")
        collection = Collection(collection_name, schema)

        # 创建索引
        collection.create_index(
            "dense_vector",
            {"index_type": "IVF_FLAT", "metric_type": "IP", "params": {"nlist": 128}},
        )
        collection.create_index(
            "sparse_vector",
            {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "IP", "params": {}},
        )
        logger.info("[Milvus] Indexes created.")

    collection.load()
    logger.info("[Milvus] Collection loaded into memory.")

    # 检查是否已有数据
    if collection.num_entities > 0:
        logger.info("[Milvus] Collection already has %d entities, skipping insert.", collection.num_entities)
        return

    docs = _generate_milvus_docs()
    logger.info("[Milvus] Encoding %d documents with BGE-M3 ...", len(docs))

    # MilvusClient 会重新 connect + load，但 pymilvus 同一 alias 幂等
    from backend.core.milvus_client import MilvusClient

    client = MilvusClient()
    dense_vecs, sparse_weights_list = client.embed_documents([d["text"] for d in docs])
    sparse_vecs = MilvusClient._sparse_to_csr_rows(sparse_weights_list)

    texts = [d["text"] for d in docs]
    sources = [d["source"] for d in docs]
    data = [texts, sources, dense_vecs, sparse_vecs]

    collection.insert(data)
    collection.flush()
    client.close()
    logger.info("[Milvus] Inserted %d documents.", len(docs))


def main() -> None:
    """入口：解析参数并执行初始化。"""
    parser = argparse.ArgumentParser(description="初始化离线演示数据(M4.4)")
    parser.add_argument("--skip-milvus", action="store_true", help="跳过 Milvus 初始化")
    args = parser.parse_args()

    # ── PG ──
    logger.info("========== PG Initialization ==========")
    from backend.db.session import SessionLocal, engine

    _init_pg(engine(), SessionLocal())

    # ── Milvus ──
    if args.skip_milvus:
        logger.info("[Milvus] Skipped (--skip-milvus).")
        return

    logger.info("========== Milvus Initialization ==========")
    try:
        _init_milvus()
    except ModuleNotFoundError as exc:
        if exc.name == "pymilvus":
            logger.warning("[Milvus] pymilvus not installed, skipping Milvus init.")
        else:
            raise
    except Exception:
        logger.exception("[Milvus] Initialization failed.")
        raise

    logger.info("========== All done. ==========")


if __name__ == "__main__":
    main()
