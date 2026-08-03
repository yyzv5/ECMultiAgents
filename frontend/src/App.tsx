import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./components/RequireAuth";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Chat } from "./pages/Chat";
import { ListingAudit } from "./pages/ListingAudit";
import { DataAnalyze } from "./pages/DataAnalyze";

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route path="/chat" element={<Chat />} />
          <Route path="/listing" element={<ListingAudit />} />
          <Route path="/data" element={<DataAnalyze />} />
        </Route>
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </AuthProvider>
  );
}