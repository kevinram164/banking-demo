import React, { useState } from "react";
import { api } from "./api";
import Card from "./ui/Card";

export default function Register({ onGoLogin }) {
  const [phone, setPhone] = useState("");
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (loading) return;
    setLoading(true);
    setErr(""); setMsg("");
    try {
      const r = await api.register(phone, username, password);
      setMsg(`Account created. Your account number: ${r.account_number}. Please sign in.`);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title="Create account"
      desc="Register a new user to test transfers and realtime notifications."
      footer="Security note: bcrypt has max 72 bytes password (lab constraint)."
    >
      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-slate-600">Phone</label>
          <input
            className="mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="digits only (e.g. 0987654321)"
            inputMode="numeric"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>

        <div>
          <label className="text-xs font-medium text-slate-600">Display name</label>
          <input
            className="mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="e.g. Kiet Nguyen"
            value={username}
            onChange={(e) => setU(e.target.value)}
          />
        </div>

        <div>
          <label className="text-xs font-medium text-slate-600">Password</label>
          <input
            className="mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="min 6 chars"
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
            {loading ? "Creating..." : "Create account"}
          </button>
          <button
            type="button"
            onClick={onGoLogin}
            className="rounded-xl border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Back
          </button>
        </div>

        {msg && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {msg}
          </div>
        )}
        {err && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {err}
          </div>
        )}
      </div>
    </Card>
  );
}
