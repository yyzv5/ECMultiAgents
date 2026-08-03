export interface APIResponse<T> {
  code: number;
  data: T;
  message?: string;
}

export interface LoginResp {
  access_token: string;
  token_type: string;
}

export interface ChatResp {
  intent: "rag" | "data" | "listing";
  answer: string;
  sources?: string[] | null;
  confidence?: number | null;
  rejected?: boolean;
}

export interface AuditIssue {
  field: string;
  rule: string;
  detail: string;
  suggestion: string;
}

export interface ListingAuditResp {
  status: "approved" | "needs_revision" | "pending_human_review" | "rejected";
  task_id: string;
  issues: AuditIssue[];
}

export interface DataAnalyzeResp {
  analysis_type: string;
  report: string;
  sql_used?: string | null;
}