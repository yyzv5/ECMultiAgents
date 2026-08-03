import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function Layout() {
  const { username, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="layout">
      <header className="topbar">
        <div className="brand">ECMultiAgents</div>
        <nav className="nav">
          <NavLink to="/chat" className="nav-link">
            智能问答
          </NavLink>
          <NavLink to="/listing" className="nav-link">
            上架审核
          </NavLink>
          <NavLink to="/data" className="nav-link">
            数据分析
          </NavLink>
        </nav>
        <div className="user">
          <span className="username">{username ?? "未登录"}</span>
          <button className="btn btn-ghost" onClick={onLogout}>
            登出
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}