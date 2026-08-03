import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import type { ReactElement } from "react";

export function RequireAuth({ children }: { children: ReactElement }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return children;
}