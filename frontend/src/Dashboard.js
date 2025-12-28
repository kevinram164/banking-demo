import React, { useEffect, useMemo, useState } from "react";
import Layout from "./ui/Layout";
import Card from "./ui/Card";
import { api, getSession, clearSession } from "./api";

export default function Dashboard({ onLogout }) {
  const [me, setMe] = useState(null);
  const [toUser, setToUser] = useState("");
  const [amount, setAmount] = useState("");
  const [notifs, setNotifs] = useState([]);
  const [wsStatus, setWsStatus] = useState("disconnected");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const session = getSession();

  const wsUrl = useMemo(() => {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    return `${scheme}://${window.location.host}/ws?session=${encodeURIComponent(session || "")}`;
  }, [session]);

  const load = async () => {
    const m = await api.me();
    setMe(m);
    const n = await api.notifications().catch(() => []);
    setNotifs(Array.isArray(n) ? n : (n.items || []));
  };

  useEffect(() => {
    load().catch(console.error);

    if (!session) return;
    let ws = null;

    try {
      ws = new WebSocket(wsUrl);
    } catch {
      return;
    }

    ws.onopen = () => setWsStatus("connected");
    ws.onclose = () => setWsStatus("disconnected");
    ws.onerror = () => setWsStatus("error");
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        setNotifs((prev) => [data, ...prev].slice(0, 50));
      } catch {}
    };

    return () => {
      try { ws && ws.close(); } catch {}
    };
  }, [wsUrl, session]);

  const doTransfer = async () => {
    setErr(""); setMsg("");
    try {
      const r = await api.transfer(toUser, amount);
      setMsg(`Transfer success: ${r.amount} to ${r.to_username}`);
      setToUser(""); setAmount("");
      await load();
    } catch (e) {
      setErr(e.message);
    }
  };

  const logout = () => {
    clearSession();
    onLogout?.();
  };

  const wsBadge =
    wsStatus === "connected"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : wsStatus === "error"
      ? "bg-red-50 text-red-700 border-red-200"
      : "bg-slate-50 text-slate-600 border-slate-200";

  return (
    <Layout user={me?.username} env="LAB" onLogout={logout}>
      <div className="space-y-6">
        <div className="grid gap-6 md:grid-cols-3">
          <Card
            title="Account"
            desc="User & available balance"
            right={
              <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${wsBadge}`}>
                Realtime: {wsStatus}
              </span>
            }
          >
            <div className="space-y-3">
              <div>
                <div className="text-xs text-slate-500">User</div>
                <div className="text-sm font-semibold text-slate-900">{me?.username || "-"}</div>
              </div>
              <div className="rounded-2xl bg-blue-50 p-4">
                <div className="text-xs text-blue-700">Available balance</div>
                <div className="mt-1 text-2xl font-bold text-blue-900">
                  {(me?.balance ?? 0).toLocaleString()} ₫
                </div>
              </div>
            </div>
          </Card>

          <Card title="Transfer" desc="Send money to another user">
            <div className="space-y-3">
              <input
                className="w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Recipient username (e.g. hieuny)"
                value={toUser}
                onChange={(e) => setToUser(e.target.value)}
              />
              <input
                className="w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Amount (e.g. 1000)"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
              <div className="flex gap-3">
                <button
                  onClick={doTransfer}
                  className="flex-1 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  Transfer
                </button>
                <button
                  onClick={() => load().catch(()=>{})}
                  className="rounded-xl border px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Refresh
                </button>
              </div>

              {msg && <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{msg}</div>}
              {err && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}
            </div>
          </Card>

          <Card title="Demo notes" desc="What to explain in interview">
            <ul className="list-disc pl-5 text-sm text-slate-700 space-y-2">
              <li>Session stored in <b>Redis</b> → backend stateless</li>
              <li>Balance & transfers stored in <b>Postgres</b></li>
              <li>Realtime notify via <b>WebSocket</b> (Ingress supports WS)</li>
              <li>Scale pods: notify works cross-pod using Redis pub/sub (next step)</li>
            </ul>
          </Card>
        </div>

        <Card title="Notifications" desc="Incoming transfer notifications (WebSocket)">
          <div className="space-y-3">
            {notifs.length === 0 && (
              <div className="rounded-xl border bg-slate-50 px-4 py-3 text-sm text-slate-600">
                No notifications yet.
              </div>
            )}

            {notifs.map((n, idx) => (
              <div key={n.id ?? idx} className="rounded-xl border px-4 py-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold text-slate-900">notification</div>
                  <div className="text-xs text-slate-500">
                    {n.created_at ? new Date(n.created_at).toLocaleString() : ""}
                  </div>
                </div>
                <div className="mt-1 text-sm text-slate-700">
                  {n.message ?? JSON.stringify(n)}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Layout>
  );
}
