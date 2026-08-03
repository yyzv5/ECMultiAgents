import { useState } from "react";
import { request } from "../api/client";
import { LoadingButton } from "../components/LoadingButton";
import type { AuditIssue, ListingAuditResp } from "../api/types";

type Status = ListingAuditResp["status"];

interface Preset {
  label: string;
  data: {
    platform: string;
    title: string;
    image_urls: string;
    category: string;
    variations: string;
    attributes: string;
  };
}

const PRESETS: Preset[] = [
  {
    label: "合规商品",
    data: {
      platform: "Amazon",
      title: "Wireless Bluetooth Headphones Noise Cancelling",
      image_urls:
        "https://example.com/img1.jpg\nhttps://example.com/img2.jpg\nhttps://example.com/img3.jpg",
      category: "Electronics > Audio > Headphones",
      variations: '[{"color": "Black"}, {"color": "White"}]',
      attributes: "brand:Acme\nwarranty:1 year",
    },
  },
  {
    label: "违禁词",
    data: {
      platform: "Shopee",
      title: "Best #1 Cure-All Miracle Medicine 100% Guaranteed",
      image_urls: "https://example.com/img1.jpg",
      category: "Health > Medicine",
      variations: "[]",
      attributes: "brand:Acme",
    },
  },
  {
    label: "可自动修复",
    data: {
      platform: "AliExpress",
      title: "Cheap Cheap Cheap Super Sale Lowest Price!!!",
      image_urls:
        "https://example.com/img1.jpg\nhttps://example.com/img2.jpg\nhttps://example.com/img3.jpg\nhttps://example.com/img4.jpg",
      category: "Fashion > Accessories",
      variations: '[{"size": "M"}, {"size": "L"}]',
      attributes: "material:Cotton",
    },
  },
];

function StatusBadge({ status }: { status: Status }) {
  const map: Record<Status, { cls: string; text: string }> = {
    approved: { cls: "badge-green", text: "审核通过" },
    needs_revision: { cls: "badge-yellow", text: "需要修改" },
    pending_human_review: { cls: "badge-orange", text: "等待人工审核" },
    rejected: { cls: "badge-red", text: "已驳回" },
  };
  const { cls, text } = map[status];
  return <span className={`badge ${cls}`}>{text}</span>;
}

function IssueItem({ issue }: { issue: AuditIssue }) {
  return (
    <li>
      <div className="issue-field">
        {issue.field} <span className="issue-rule">[{issue.rule}]</span>
      </div>
      <div className="issue-detail">{issue.detail}</div>
      {issue.suggestion && (
        <div className="issue-suggestion">建议：{issue.suggestion}</div>
      )}
    </li>
  );
}

export function ListingAudit() {
  const [platform, setPlatform] = useState("Amazon");
  const [title, setTitle] = useState("");
  const [imageUrls, setImageUrls] = useState("");
  const [category, setCategory] = useState("");
  const [variations, setVariations] = useState("[]");
  const [attributes, setAttributes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resp, setResp] = useState<ListingAuditResp | null>(null);
  const [decision, setDecision] = useState<"approve" | "reject" | "modify">(
    "approve",
  );
  const [feedback, setFeedback] = useState("");
  const [resumeLoading, setResumeLoading] = useState(false);

  const fillPreset = (p: Preset) => {
    setPlatform(p.data.platform);
    setTitle(p.data.title);
    setImageUrls(p.data.image_urls);
    setCategory(p.data.category);
    setVariations(p.data.variations);
    setAttributes(p.data.attributes);
  };

  const buildPayload = () => ({
    platform,
    title,
    image_urls: imageUrls
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter(Boolean),
    category,
    variations: (() => {
      try {
        return JSON.parse(variations || "[]");
      } catch {
        return [];
      }
    })(),
    attributes: (() => {
      const out: Record<string, string> = {};
      for (const line of attributes.split("\n")) {
        const [k, v] = line.split(":");
        if (k && v) out[k.trim()] = v.trim();
      }
      return out;
    })(),
  });

  const submit = async () => {
    if (!title || !category) {
      setError("标题和类目必填");
      return;
    }
    setError(null);
    setResp(null);
    setLoading(true);
    try {
      const data = await request<ListingAuditResp>({
        url: "/v1/listing/audit",
        data: buildPayload(),
      });
      setResp(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "请求失败";
      setError(`审核失败：${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const submitDecision = async () => {
    if (!resp) return;
    setResumeLoading(true);
    setError(null);
    try {
      const data = await request<ListingAuditResp>({
        url: `/v1/listing/audit/${resp.task_id}/resume`,
        data: {
          human_decision: decision,
          human_feedback: feedback || null,
        },
      });
      setResp(data);
      setFeedback("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "请求失败";
      setError(`恢复审核失败：${msg}`);
    } finally {
      setResumeLoading(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">上架审核</h1>
      <p className="page-desc">多平台 Listing 并行审核，支持人机协同中断。</p>

      <div className="card">
        <div className="example-row">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              className="btn btn-mini"
              style={{ background: "#e8f0fe", color: "#1a73e8", border: "none" }}
              onClick={() => fillPreset(p)}
              disabled={loading}
            >
              预设：{p.label}
            </button>
          ))}
        </div>
        <div className="row">
          <div className="field">
            <label>平台</label>
            <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
              <option>Amazon</option>
              <option>Shopee</option>
              <option>AliExpress</option>
            </select>
          </div>
          <div className="field">
            <label>类目</label>
            <input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="如：Electronics > Audio"
            />
          </div>
        </div>
        <div className="field">
          <label>标题</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="商品标题"
          />
        </div>
        <div className="field">
          <label>图片链接（每行一个或逗号分隔）</label>
          <textarea
            value={imageUrls}
            onChange={(e) => setImageUrls(e.target.value)}
            rows={3}
            placeholder="https://..."
          />
        </div>
        <div className="field">
          <label>变体（JSON 数组）</label>
          <textarea
            value={variations}
            onChange={(e) => setVariations(e.target.value)}
            rows={2}
            placeholder='[{"color":"Black"}]'
          />
        </div>
        <div className="field">
          <label>属性（key:value 一行一对）</label>
          <textarea
            value={attributes}
            onChange={(e) => setAttributes(e.target.value)}
            rows={2}
            placeholder="brand:Acme"
          />
        </div>
        <LoadingButton loading={loading} onClick={submit}>
          提交审核
        </LoadingButton>
      </div>

      {error && <div className="error">{error}</div>}

      {resp && (
        <div className="card">
          <div>
            <StatusBadge status={resp.status} />
            <span className="confidence">task_id: {resp.task_id}</span>
          </div>
          {resp.issues.length > 0 && (
            <ul className="issues-list">
              {resp.issues.map((issue, i) => (
                <IssueItem key={i} issue={issue} />
              ))}
            </ul>
          )}

          {resp.status === "pending_human_review" && (
            <div className="decision-panel">
              <h4 className="card-title">决策面板</h4>
              <div className="field">
                <label>人工决定</label>
                <select
                  value={decision}
                  onChange={(e) =>
                    setDecision(e.target.value as "approve" | "reject" | "modify")
                  }
                >
                  <option value="approve">approve（通过）</option>
                  <option value="modify">modify（自动修复）</option>
                  <option value="reject">reject（驳回）</option>
                </select>
              </div>
              <div className="field">
                <label>反馈说明</label>
                <textarea
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  rows={2}
                  placeholder="可选，给 Agent 的反馈"
                />
              </div>
              <LoadingButton loading={resumeLoading} onClick={submitDecision}>
                提交决策
              </LoadingButton>
            </div>
          )}
        </div>
      )}
    </div>
  );
}