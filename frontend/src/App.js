import React, { useEffect, useState } from "react";
import { getSession, clearSession } from "./api";
import Login from "./Login";
import Register from "./Register";
import Dashboard from "./Dashboard";

export default function App() {
  const [page, setPage] = useState(getSession() ? "dashboard" : "login");

  useEffect(() => {
    if (!getSession()) setPage("login");
  }, []);

  const logout = () => {
    clearSession();
    setPage("login");
  };

  return (
    <div style={{ fontFamily: "system-ui", maxWidth: 720, margin: "40px auto" }}>
      <h2>Banking Demo (Postgres + Redis Session)</h2>
      {page === "login" && <Login onOk={() => setPage("dashboard")} onGoRegister={() => setPage("register")} />}
      {page === "register" && <Register onGoLogin={() => setPage("login")} />}
      {page === "dashboard" && <Dashboard onLogout={logout} />}
    </div>
  );
}
