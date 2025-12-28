import React, { useState } from "react";
import { api, setSession } from "./api";
import Card from "./ui/Card";

export default function Login({ onOk, onGoRegister }) {
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (loading) return;
    setLoading(true);
    setErr("");
    try {
      const r = await api.login(username, password);
      setSession(r.session);
      onOk();
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title="Sign in"
      desc="Use your account to access balance, transfers and notifications."
      footer="Tip: Open two browsers to see realtime notifications."
    >
      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-slate-600">Username</label>
          <input
            className="mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="e.g. kiettt"
            value={username}
            onChange={(e) => setU(e.target.value)}
          />
        </div>

        <div>
          <label className="text-xs font-medium text-slate-600">Password</label>
          <input
            className="mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="••••••••"
            type="password"
            value={password}
            onChange={(e) => setP(e.target.value)}
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            type="button"
            disabled={loading}
            onClick={submit}
            className="flex-1 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
          <button
            type="button"
            onClick={onGoRegister}
            className="rounded-xl border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Create
          </button>
        </div>

        {err && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {err}
          </div>
        )}
      </div>
    </Card>
  );
}
