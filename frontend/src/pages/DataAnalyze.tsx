import { useState } from "react";
import { request } from "../api/client";
import { useSessionId } from "../hooks/useSessionId";
import { LoadingButton } from "../components/LoadingButton";
import type { DataAnalyzeResp } from "../api/types";

const EXAMPLES = [
  "本周销售周报",
  "本月广告表现",
  "对比 Amazon 和 Shopee 平台的销售情况",
];

export function DataAnalyze() {
  const sessionId = useSessionId();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resp, setResp] = useState<DataAnalyzeResp | null>(null);
  const [showSql, setShowSql] = useState(false);

  const submit = async (q: string = query) => {
    if (!q.trim()) return;
    setError(null);
    setResp(null);
    setLoading(true);
    try {
      const data = await request<DataAnalyzeResp>({
        url: "/v1/data/analyze",
        data: { query: q, session_id: sessionId },
      });
      setResp(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "请求失败";
      setError(`分析失败：${msg}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">数据分析</h1>
      <p className="page-desc">自然语言驱动的销售/广告数据分析，支持多轮对话。</p>

      <div className="card">
        <div className="field">
          <label>分析需求</label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="如：本周销售周报 / 各平台广告 ROI 对比"
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
          开始分析
        </LoadingButton>
      </div>

      {error && <div className="error">{error}</div>}

      {resp && (
        <div className="card">
          <div>
            <span className="badge badge-blue">analysis_type: {resp.analysis_type}</span>
          </div>
          <div className="report-text">{resp.report}</div>
          {resp.sql_used && (
            <div>
              <button
                type="button"
                className="btn btn-mini"
                style={{
                  background: "transparent",
                  color: "#2c7be5",
                  border: "none",
                  padding: "8px 0",
                }}
                onClick={() => setShowSql((s) => !s)}
              >
                {showSql ? "隐藏" : "展开"} SQL ▾
              </button>
              {showSql && <pre className="sql-block">{resp.sql_used}</pre>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}