import React, { useEffect, useMemo, useState } from "react";
import { api, clearSession, getSession } from "./api";
import Card from "./ui/Card";

export default function Dashboard({ onLogout }) {
  const [me, setMe] = useState(null);
  const [toUser, setToUser] = useState("");
  const [amount, setAmount] = useState("");
  const [txMsg, setTxMsg] = useState("");
  const [txErr, setTxErr] = useState("");
  const [notifs, setNotifs] = useState([]);
  const [wsStatus, setWsStatus] = useState("disconnected");

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
    let ws;
    try {
      ws = new WebSocket(wsUrl);
    } catch (e) {
      console.error(e);
      return;
    }

    ws.onopen = () => setWsStatus("connected");
    ws.onclose = () => setWsStatus("disconnected");
    ws.onerror = () => setWsStatus("error");
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        // prepend
        setNotifs((prev) => [msg, ...prev].slice(0, 50));
      } catch {
        // ignore
      }
    };

    return () => {
      try { ws && ws.close(); } catch {}
    };
  }, [wsUrl, session]);

  const doTransfer = async () => {
    setTxErr(""); setTxMsg("");
    try {
      const r = await api.transfer(toUser, amount);
      setTxMsg(`Transfer success: ${r.amount} to ${r.to_username}`);
      setAmount("");
      setToUser("");
      await load();
    } catch (e) {
      setTxErr(e.message);
    }
  };

  const logout = () => {
    clearSession();
    onLogout?.();
  };

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-6">
        <Card
          title="Account overview"
          desc="Balance and transfer operations."
          footer={
            <div className="flex items-center justify-between">
              <span className="text-xs">
                Realtime channel:{" "}
                <span className={`font-semibold ${wsStatus === "connected" ? "text-emerald-700" : "text-slate-500"}`}>
                  {wsStatus}
                </span>
              </span>
              <button onClick={logout} className="text-xs font-semibold text-blue-700 hover:underline">
                Sign out
              </button>
            </div>
          }
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-xs text-slate-500">User</div>
              <div className="text-lg font-semibold">{me?.username || "-"}</div>
            </div>
            <div className="rounded-2xl bg-blue-50 px-5 py-4">
              <div className="text-xs text-blue-700">Available balance</div>
              <div className="mt-1 text-2xl font-bold text-blue-900">
                {me?.balance ?? 0}
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <div className="md:col-span-2">
              <label className="text-xs font-medium text-slate-600">Recipient username</label>
              <input
                className="mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                value={toUser}
                onChange={(e) => setToUser(e.target.value)}
                placeholder="e.g. hieuny"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600">Amount</label>
              <input
                className="mt-1 w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="1000"
              />
            </div>
          </div>

          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={doTransfer}
              className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700"
            >
              Transfer
            </button>
            <button
              type="button"
              onClick={load}
              className="rounded-xl border px-5 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Refresh
            </button>
          </div>

          {txMsg && (
            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {txMsg}
            </div>
          )}
          {txErr && (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {txErr}
            </div>
          )}
        </Card>
      </div>

      <div className="space-y-6">
        <Card
          title="Notifications"
          desc="Incoming transfer notifications in realtime (WebSocket)."
          footer={`${notifs.length} items`}
        >
          <div className="space-y-3">
            {notifs.length === 0 && (
              <div className="rounded-xl border bg-slate-50 px-4 py-3 text-sm text-slate-600">
                No notifications yet.
              </div>
            )}

            {notifs.map((n, idx) => (
              <div key={idx} className="rounded-xl border px-4 py-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-semibold text-slate-800">
                    {n.type || "notification"}
                  </div>
                  <div className="text-xs text-slate-500">
                    {n.ts ? new Date(n.ts).toLocaleString() : ""}
                  </div>
                </div>
                <div className="mt-1 text-sm text-slate-600">
                  {n.msg || (n.from_username ? `From ${n.from_username}: +${n.amount}` : JSON.stringify(n))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
