import React, { useState } from "react";
import { api, setSession } from "./api";

export default function Login({ onOk, onGoRegister }) {
  const [phone, setPhone] = useState("");
  const [password, setP] = useState("");
  const [err, setErr] = useState("");

  const submit = async () => {
    setErr("");
    try {
      const r = await api.login(phone, password);
      setSession(r.session);
      onOk();
    } catch (e) {
      setErr(e.message || "Login failed");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md rounded-2xl border bg-white p-7 shadow-sm">
        <div className="flex items-center gap-3 mb-5">
          <div className="h-10 w-10 rounded-xl bg-blue-600 text-white grid place-items-center font-bold">B</div>
          <div>
            <div className="text-base font-semibold text-slate-900">NPD Banking</div>
            <div className="text-xs text-slate-500">Postgres • Redis Session • WebSocket Notify</div>
          </div>
        </div>

        <h2 className="text-xl font-semibold text-slate-900">Sign in</h2>
        <p className="text-sm text-slate-500 mt-1 mb-5">
          Use your account to access balance, transfers and notifications.
        </p>

        <div className="space-y-3">
          <input
            className="w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Phone number (digits only)"
            inputMode="numeric"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
          <input
            className="w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setP(e.target.value)}
          />
        </div>

        <div className="mt-5 flex gap-3">
          <button
            onClick={submit}
            className="flex-1 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Sign in
          </button>
          <button
            onClick={onGoRegister}
            className="flex-1 rounded-xl border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Create
          </button>
        </div>

        {err && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {err}
          </div>
        )}

        <div className="mt-5 text-xs text-slate-400">
          © Banking Demo Lab • Postgres + Redis
        </div>
      </div>
    </div>
  );
}
