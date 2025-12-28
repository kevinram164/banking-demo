import React, { useState } from "react";
import { api } from "./api";

export default function Register({ onGoLogin }) {
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const submit = async () => {
    setErr(""); setMsg("");
    try {
      await api.register(username, password);
      setMsg("Register ok. Please login.");
    } catch (e) {
      setErr(e.message);
    }
  };

  return (
    <div style={{ border: "1px solid #ddd", padding: 16, borderRadius: 12 }}>
      <h3>Register</h3>
      <input placeholder="username" value={username} onChange={e=>setU(e.target.value)} />
      <br/><br/>
      <input placeholder="password (>=6)" type="password" value={password} onChange={e=>setP(e.target.value)} />
      <br/><br/>
      <button onClick={submit}>Create account</button>
      <button style={{ marginLeft: 8 }} onClick={onGoLogin}>Back to login</button>
      {msg && <p style={{ color: "green" }}>{msg}</p>}
      {err && <p style={{ color: "crimson" }}>{err}</p>}
    </div>
  );
}
