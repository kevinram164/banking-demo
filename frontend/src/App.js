import React, { useState } from "react";
import Login from "./Login";
import Register from "./Register";
import Dashboard from "./Dashboard";
import Admin from "./Admin";
import { getSession, clearSession } from "./api";

export default function App() {
  const [page, setPage] = useState(getSession() ? "dashboard" : "login");

  const logout = () => {
    clearSession();
    setPage("login");
  };

  if (page === "admin") {
    return <Admin onBack={() => setPage(getSession() ? "dashboard" : "login")} />;
  }

  if (page === "login") {
    return <Login onOk={() => setPage("dashboard")} onGoRegister={() => setPage("register")} onGoAdmin={() => setPage("admin")} />;
  }

  if (page === "register") {
    return <Register onGoLogin={() => setPage("login")} />;
  }

  return <Dashboard onLogout={logout} onGoAdmin={() => setPage("admin")} />;
}
