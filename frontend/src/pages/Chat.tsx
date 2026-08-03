import { useState } from "react";
import { request } from "../api/client";
import { useSessionId } from "../hooks/useSessionId";
import { LoadingButton } from "../components/LoadingButton";
import type { ChatResp } from "../api/types";

const EXAMPLES = [
  "跨境电商运营有哪些核心指标？",
  "Amazon 商品标题合规要求有哪些？",
  "Shopee 平台的物流时效怎么计算？",
  "如何提升跨境电商的转化率？",
  "AliExpress 禁运商品清单有哪些？",
];

export function Chat() {
  const sessionId = useSessionId();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resp, setResp] = useState<ChatResp | null>(null);

  const submit = async (q: string = query) => {
    if (!q.trim()) return;
    setError(null);
    setResp(null);
    setLoading(true);
    try {
      const data = await request<ChatResp>({
        url: "/v1/chat",
        data: { query: q, session_id: sessionId },
      });
      setResp(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "请求失败";
      setError(`对话失败：${msg}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">智能问答</h1>
      <p className="page-desc">基于知识库的 RAG 对话，支持多轮记忆。</p>

      <div className="card">
        <div className="field">
          <label>输入问题</label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="请输入问题..."
            rows={3}
          />
        </div>
        <div className="example-row">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              className="btn btn-mini"
              style={{ background: "#e8f0fe", color: "#1a73e8", border: "none" }}
              onClick={() => {
                setQuery(ex);
                void submit(ex);
              }}
              disabled={loading}
            >
              {ex}
            </button>
          ))}
        </div>
        <LoadingButton loading={loading} onClick={() => submit()}>
          提问
        </LoadingButton>
      </div>

      {error && <div className="error">{error}</div>}

      {resp && (
        <div className="card">
          <div>
            <span className={`badge badge-${resp.intent === "data" ? "orange" : "blue"}`}>
              intent: {resp.intent}
            </span>
            {typeof resp.confidence === "number" && (
              <span className="confidence">
                置信度：{(resp.confidence * 100).toFixed(1)}%
              </span>
            )}
            {resp.rejected && (
              <span className="rejected-tag">（已拒绝回答）</span>
            )}
          </div>
          <div className="report-text" style={{ marginTop: 12 }}>
            {resp.answer}
          </div>
          {resp.sources && resp.sources.length > 0 && (
            <div>
              <strong style={{ fontSize: 13 }}>引用来源：</strong>
              <ul className="sources-list">
                {resp.sources.map((src, i) => (
                  <li key={i}>
                    <a href={src} target="_blank" rel="noreferrer">
                      {src}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}