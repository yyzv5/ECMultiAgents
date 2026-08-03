import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { request } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { LoadingButton } from "../components/LoadingButton";

export function Login() {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("demo");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { login } = useAuth();
  const navigate = useNavigate();

  const submit = async () => {
    setError(null);
    setLoading(true);
    try {
      if (tab === "register") {
        await request<unknown>({
          url: "/v1/auth/register",
          data: { username, password },
        });
      }
      const resp = await request<{ access_token: string; token_type: string }>({
        url: "/v1/auth/login",
        data: { username, password },
      });
      login(resp.access_token, username);
      navigate("/chat", { replace: true });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "请求失败";
      setError(`${tab === "register" ? "注册" : "登录"}失败：${msg}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-card">
      <div className="card">
        <h2 className="card-title">ECMultiAgents 演示登录</h2>
        <div className="tabs">
          <button
            type="button"
            className={`tab ${tab === "login" ? "active" : ""}`}
            onClick={() => setTab("login")}
          >
            登录
          </button>
          <button
            type="button"
            className={`tab ${tab === "register" ? "active" : ""}`}
            onClick={() => setTab("register")}
          >
            注册
          </button>
        </div>
        {error && <div className="error">{error}</div>}
        <div className="field">
          <label>用户名</label>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="请输入用户名"
            autoComplete="username"
          />
        </div>
        <div className="field">
          <label>密码</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="请输入密码"
            autoComplete="current-password"
          />
        </div>
        <LoadingButton loading={loading} type="submit" onClick={submit}>
          {tab === "login" ? "登录" : "注册并登录"}
        </LoadingButton>
      </div>
    </div>
  );
}