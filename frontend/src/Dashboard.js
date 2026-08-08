import React, { useEffect, useMemo, useState } from "react";
import Layout from "./ui/Layout";
import Card from "./ui/Card";
import { api, getSession, clearSession } from "./api";

function statusClass(status) {
  if (status === "PENDING") return "bg-amber-50 text-amber-800 border-amber-200";
  if (status === "SUCCESS") return "bg-emerald-50 text-emerald-800 border-emerald-200";
  if (status === "CANCELLED") return "bg-slate-100 text-slate-600 border-slate-200";
  if (status === "FAILED") return "bg-red-50 text-red-700 border-red-200";
  return "bg-slate-50 text-slate-700 border-slate-200";
}

export default function Dashboard({ onLogout, onGoAdmin }) {
  const [me, setMe] = useState(null);
  const [transfers, setTransfers] = useState([]);
  const [toAccount, setToAccount] = useState("");
  const [toName, setToName] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [purpose, setPurpose] = useState("");
  const [txnType, setTxnType] = useState("P2P");
  const [notifs, setNotifs] = useState([]);
  const [wsStatus, setWsStatus] = useState("disconnected");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busyId, setBusyId] = useState(null);

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
    const hist = await api.myTransfers(1, 20).catch(() => ({ transfers: [] }));
    setTransfers(hist.transfers || []);
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
        load().catch(() => {});
      } catch {}
    };

    return () => {
      try { ws && ws.close(); } catch {}
    };
  }, [wsUrl, session]);

  const doTransfer = async () => {
    setErr(""); setMsg("");

    if (!toAccount || !toAccount.trim()) {
      setErr("Please enter recipient account number");
      return;
    }

    const amountNum = Number(amount);
    if (!amount || isNaN(amountNum) || amountNum <= 0) {
      setErr("Please enter a valid amount greater than 0");
      return;
    }

    if (!Number.isInteger(amountNum)) {
      setErr("Amount must be a whole number");
      return;
    }

    try {
      const r = await api.transfer(toAccount.trim(), amountNum, note.trim(), {
        txn_type: txnType,
        purpose: purpose.trim() || undefined,
        channel: "mobile",
      });
      setMsg(
        `${r.status || "PENDING"}: ${r.amount} → ${r.to} (${r.to_account_number})` +
          (r.txn_type ? ` · ${r.txn_type}` : "") +
          (r.note ? ` · ${r.note}` : "") +
          (r.transfer_id ? ` · #${r.transfer_id}` : "")
      );
      setToAccount(""); setToName(""); setAmount(""); setNote(""); setPurpose("");
      await load();
    } catch (e) {
      setErr(e.message);
    }
  };

  const confirmOne = async (id) => {
    setErr(""); setMsg(""); setBusyId(id);
    try {
      const r = await api.confirmTransfer(id);
      setMsg(`Confirmed #${r.transfer_id}: ${r.status}`);
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const cancelOne = async (id) => {
    setErr(""); setMsg(""); setBusyId(id);
    try {
      const r = await api.cancelTransfer(id);
      setMsg(`Cancelled #${r.transfer_id}: ${r.status}`);
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyId(null);
    }
  };

  const lookup = async (acct) => {
    const v = (acct || "").trim();
    setToName("");
    if (!v) return;
    try {
      const r = await api.lookupAccount(v);
      setToName(r.username || "");
    } catch {
      setToName("");
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

  const available = me?.available ?? me?.balance ?? 0;
  const held = me?.held_balance ?? 0;

  return (
    <Layout user={me?.username} env="LAB" onLogout={logout} onGoAdmin={onGoAdmin} activePage="dashboard">
      <div className="space-y-6">
        <div className="grid gap-6 md:grid-cols-3">
          <Card
            title="Account"
            desc="Số dư & phong tỏa (hold)"
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
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-2xl bg-slate-50 p-4">
                  <div className="text-xs text-slate-500">Phone</div>
                  <div className="mt-1 text-sm font-semibold text-slate-900">{me?.phone || "-"}</div>
                </div>
                <div className="rounded-2xl bg-slate-50 p-4">
                  <div className="text-xs text-slate-500">Account number</div>
                  <div className="mt-1 text-sm font-semibold text-slate-900">{me?.account_number || "-"}</div>
                </div>
              </div>
              <div className="rounded-2xl bg-blue-50 p-4">
                <div className="text-xs text-blue-700">Available</div>
                <div className="mt-1 text-2xl font-bold text-blue-900">
                  {Number(available).toLocaleString()} ₫
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-2xl bg-slate-50 p-3">
                  <div className="text-xs text-slate-500">Ledger balance</div>
                  <div className="mt-1 text-sm font-semibold">{Number(me?.balance ?? 0).toLocaleString()} ₫</div>
                </div>
                <div className="rounded-2xl bg-amber-50 p-3">
                  <div className="text-xs text-amber-700">Held</div>
                  <div className="mt-1 text-sm font-semibold text-amber-900">{Number(held).toLocaleString()} ₫</div>
                </div>
              </div>
            </div>
          </Card>

          <Card title="Transfer" desc="Tạo PENDING + hold → Confirm để settle">
            <div className="space-y-3">
              <input
                className="w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Recipient account number"
                inputMode="numeric"
                value={toAccount}
                onChange={(e) => setToAccount(e.target.value)}
                onBlur={(e) => lookup(e.target.value)}
              />
              <div className={`rounded-xl border px-4 py-3 text-sm ${toName ? "bg-emerald-50 text-emerald-800 border-emerald-200" : "bg-slate-50 text-slate-700"}`}>
                Receiver: <span className="font-semibold">{toName || "—"}</span>
              </div>
              <select
                className="w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                value={txnType}
                onChange={(e) => setTxnType(e.target.value)}
              >
                <option value="P2P">P2P</option>
                <option value="DISBURSEMENT">DISBURSEMENT</option>
                <option value="REPAYMENT">REPAYMENT</option>
                <option value="BILL_PAY">BILL_PAY</option>
                <option value="FEE">FEE</option>
                <option value="MERCHANT_PAY">MERCHANT_PAY</option>
              </select>
              <input
                className="w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Amount"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
              <input
                className="w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Purpose (vd: trả góp kỳ 3)"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                maxLength={128}
              />
              <input
                className="w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Note (vd NOLI-XXXX khi thanh toán shop)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={64}
              />
              <div className="flex gap-3">
                <button
                  onClick={doTransfer}
                  className="flex-1 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  Create hold
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

          <Card title="Demo notes" desc="Mcredit lab narrative">
            <ul className="list-disc pl-5 text-sm text-slate-700 space-y-2">
              <li>Transfer → <b>PENDING</b> + hold (available giảm)</li>
              <li>Confirm → <b>SUCCESS</b> settle; Cancel/expire → nhả hold</li>
              <li>Shop NOLI chỉ báo khi SUCCESS</li>
              <li>Mess queue quá hạn → MESSAGE_EXPIRED (không trừ tiền muộn)</li>
            </ul>
          </Card>
        </div>

        <Card title="Statement" desc="Sao kê gần đây (status / type / purpose)">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-semibold text-slate-500">
                  <th className="px-2 py-2">ID</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2">Type</th>
                  <th className="px-2 py-2">Counterparty</th>
                  <th className="px-2 py-2 text-right">Amount</th>
                  <th className="px-2 py-2">Purpose</th>
                  <th className="px-2 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {transfers.map((t) => {
                  const peer = t.direction === "out" ? t.to_username : t.from_username;
                  return (
                    <tr key={t.id} className="border-b hover:bg-slate-50">
                      <td className="px-2 py-2 text-slate-500">#{t.id}</td>
                      <td className="px-2 py-2">
                        <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${statusClass(t.status)}`}>
                          {t.status}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-xs">{t.txn_type}</td>
                      <td className="px-2 py-2">
                        <span className="text-xs text-slate-400">{t.direction === "out" ? "→" : "←"}</span> {peer}
                      </td>
                      <td className="px-2 py-2 text-right font-semibold">{Number(t.amount).toLocaleString()} ₫</td>
                      <td className="px-2 py-2 text-xs text-slate-600 max-w-[10rem] truncate" title={t.purpose || t.note}>
                        {t.purpose || t.note || "—"}
                      </td>
                      <td className="px-2 py-2">
                        {t.status === "PENDING" && t.direction === "out" ? (
                          <div className="flex gap-1">
                            <button
                              disabled={busyId === t.id}
                              onClick={() => confirmOne(t.id)}
                              className="rounded-lg bg-emerald-600 px-2 py-1 text-xs font-semibold text-white disabled:opacity-40"
                            >
                              Confirm
                            </button>
                            <button
                              disabled={busyId === t.id}
                              onClick={() => cancelOne(t.id)}
                              className="rounded-lg border px-2 py-1 text-xs font-semibold text-slate-700 disabled:opacity-40"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">
                            {t.created_at ? new Date(t.created_at).toLocaleString() : ""}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {transfers.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-6 text-center text-slate-400">No transfers yet</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>

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
