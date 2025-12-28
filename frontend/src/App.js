import React, { useState } from "react";
import Layout from "./ui/Layout";
import Login from "./Login";
import Register from "./Register";
import Dashboard from "./Dashboard";
import { getSession } from "./api";

export default function App() {
  const [page, setPage] = useState(getSession() ? "dashboard" : "login");

  const right = (
    <div className="text-xs text-slate-500">
      Environment: <span className="font-semibold text-slate-700">LAB</span>
    </div>
  );

  return (
    <Layout title="NPD Banking" subtitle="Corporate UI • Transfers & Notifications" right={right}>
      {page === "login" && (
        <div className="mx-auto max-w-xl">
          <Login onOk={() => setPage("dashboard")} onGoRegister={() => setPage("register")} />
        </div>
      )}
      {page === "register" && (
        <div className="mx-auto max-w-xl">
          <Register onGoLogin={() => setPage("login")} />
        </div>
      )}
      {page === "dashboard" && (
        <Dashboard onLogout={() => setPage("login")} />
      )}
    </Layout>
  );
}
