import React, { useState } from "react";
import { api, setSession } from "./api";

export default function Login({ onOk, onGoRegister }) {
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [err, setErr] = useState("");

  const submit = async () => {
    setErr("");
    try {
      const r = await api.login(username, password);
      setSession(r.session);
      onOk();
    } catch (e) {
      setErr(e.message);
    }
  };

  return (
    <div style={{ border: "1px solid #ddd", padding: 16, borderRadius: 12 }}>
      <h3>Login</h3>
      <input placeholder="username" value={username} onChange={e=>setU(e.target.value)} />
      <br/><br/>
      <input placeholder="password" type="password" value={password} onChange={e=>setP(e.target.value)} />
      <br/><br/>
      <button onClick={submit}>Sign in</button>
      <button style={{ marginLeft: 8 }} onClick={onGoRegister}>Register</button>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
    </div>
  );
}
