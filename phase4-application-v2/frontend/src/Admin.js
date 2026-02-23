import React, { useCallback, useEffect, useState } from "react";
import Layout from "./ui/Layout";
import Card from "./ui/Card";
import { api } from "./api";

const SECRET_KEY = "admin_secret";

function AdminLogin({ onAuth }) {
  const [secret, setSecret] = useState("");
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      await api.adminStats(secret);
      localStorage.setItem(SECRET_KEY, secret);
      onAuth(secret);
    } catch {
      setErr("Invalid admin secret");
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="w-full max-w-sm rounded-2xl border bg-white p-8 shadow-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-xl bg-amber-600 text-white font-bold text-lg">
            A
          </div>
          <h1 className="text-lg font-bold text-slate-900">Admin Panel</h1>
          <p className="text-sm text-slate-500">Enter admin secret to continue</p>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <input
            type="password"
            className="w-full rounded-xl border px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-amber-500"
            placeholder="Admin secret"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            autoFocus
          />
          <button
            type="submit"
            className="w-full rounded-xl bg-amber-600 px-4 py-3 text-sm font-semibold text-white hover:bg-amber-700"
          >
            Login
          </button>
          {err && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>
          )}
        </form>
      </div>
    </div>
  );
}

function StatsCards({ stats }) {
  const items = [
    { label: "Total Users", value: stats.total_users?.toLocaleString(), color: "blue" },
    { label: "Total Balance", value: `${stats.total_balance?.toLocaleString()} ₫`, color: "emerald" },
    { label: "Total Transfers", value: stats.total_transfers?.toLocaleString(), color: "violet" },
    { label: "Transfer Volume", value: `${stats.total_transfer_amount?.toLocaleString()} ₫`, color: "amber" },
    { label: "Notifications", value: stats.total_notifications?.toLocaleString(), color: "slate" },
  ];

  const colorMap = {
    blue: "bg-blue-50 text-blue-700",
    emerald: "bg-emerald-50 text-emerald-700",
    violet: "bg-violet-50 text-violet-700",
    amber: "bg-amber-50 text-amber-700",
    slate: "bg-slate-100 text-slate-700",
  };

  return (
    <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {items.map((it) => (
        <div key={it.label} className={`rounded-2xl p-4 ${colorMap[it.color]}`}>
          <div className="text-xs font-medium opacity-70">{it.label}</div>
          <div className="mt-1 text-xl font-bold">{it.value ?? "—"}</div>
        </div>
      ))}
    </div>
  );
}

function UserDetailModal({ user, secret, onClose }) {
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    api.adminUserDetail(secret, user.id).then(setDetail).catch(() => {});
  }, [user.id, secret]);

  if (!detail) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
        <div className="rounded-2xl bg-white p-6 text-sm text-slate-600">Loading...</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="mx-4 w-full max-w-lg rounded-2xl border bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-900">User #{detail.id}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl leading-none">&times;</button>
        </div>

        <div className="mb-4 grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-xl bg-slate-50 p-3">
            <div className="text-xs text-slate-500">Username</div>
            <div className="font-semibold">{detail.username}</div>
          </div>
          <div className="rounded-xl bg-slate-50 p-3">
            <div className="text-xs text-slate-500">Phone</div>
            <div className="font-semibold">{detail.phone}</div>
          </div>
          <div className="rounded-xl bg-slate-50 p-3">
            <div className="text-xs text-slate-500">Account Number</div>
            <div className="font-semibold">{detail.account_number}</div>
          </div>
          <div className="rounded-xl bg-blue-50 p-3">
            <div className="text-xs text-blue-700">Balance</div>
            <div className="font-bold text-blue-900">{detail.balance?.toLocaleString()} ₫</div>
          </div>
        </div>

        <h4 className="mb-2 text-sm font-semibold text-slate-700">Recent Transfers</h4>
        {detail.transfers.length === 0 ? (
          <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-500">No transfers yet</div>
        ) : (
          <div className="max-h-60 space-y-2 overflow-y-auto">
            {detail.transfers.map((t) => (
              <div
                key={t.id}
                className={`flex items-center justify-between rounded-xl border px-4 py-2 text-sm ${
                  t.direction === "in"
                    ? "border-emerald-200 bg-emerald-50"
                    : "border-red-200 bg-red-50"
                }`}
              >
                <div>
                  <span className={`font-semibold ${t.direction === "in" ? "text-emerald-700" : "text-red-700"}`}>
                    {t.direction === "in" ? "+" : "-"}{t.amount?.toLocaleString()} ₫
                  </span>
                  <span className="ml-2 text-xs text-slate-500">
                    {t.direction === "in" ? `from user #${t.from_user}` : `to user #${t.to_user}`}
                  </span>
                </div>
                <div className="text-xs text-slate-400">
                  {t.created_at ? new Date(t.created_at).toLocaleString() : ""}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Admin({ onBack }) {
  const [secret, setSecret] = useState(localStorage.getItem(SECRET_KEY) || "");
  const [authed, setAuthed] = useState(false);
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [selectedUser, setSelectedUser] = useState(null);
  const [transfers, setTransfers] = useState([]);
  const [transfersTotal, setTransfersTotal] = useState(0);
  const [transfersPages, setTransfersPages] = useState(0);
  const [transfersPage, setTransfersPage] = useState(1);
  const [notifications, setNotifications] = useState([]);
  const [notificationsTotal, setNotificationsTotal] = useState(0);
  const [notificationsPages, setNotificationsPages] = useState(0);
  const [notificationsPage, setNotificationsPage] = useState(1);
  const [notificationServiceStatus, setNotificationServiceStatus] = useState(null);
  const [authServiceStatus, setAuthServiceStatus] = useState(null);
  const [accountServiceStatus, setAccountServiceStatus] = useState(null);
  const [transferServiceStatus, setTransferServiceStatus] = useState(null);
  const [adminSubPage, setAdminSubPage] = useState("overview");

  const loadStats = useCallback(async (s) => {
    try {
      const data = await api.adminStats(s);
      setStats(data);
    } catch {
      setStats(null);
    }
  }, []);

  const loadUsers = useCallback(async (s, p, q) => {
    try {
      const data = await api.adminUsers(s, p, 20, q);
      setUsers(data.users);
      setTotal(data.total);
      setPages(data.pages);
    } catch {
      setUsers([]);
    }
  }, []);

  const loadTransfers = useCallback(async (s, p) => {
    try {
      const data = await api.adminTransfers(s, p, 20);
      setTransfers(data.transfers);
      setTransfersTotal(data.total);
      setTransfersPages(data.pages);
    } catch {
      setTransfers([]);
    }
  }, []);

  const loadNotifications = useCallback(async (s, p) => {
    try {
      const data = await api.adminNotifications(s, p, 20);
      setNotifications(data.notifications);
      setNotificationsTotal(data.total);
      setNotificationsPages(data.pages);
    } catch {
      setNotifications([]);
    }
  }, []);

  const loadAllServiceHealth = useCallback(async () => {
    const [auth, account, transfer, notif] = await Promise.all([
      api.authServiceHealth(),
      api.accountServiceHealth(),
      api.transferServiceHealth(),
      api.notificationServiceHealth(),
    ]);
    setAuthServiceStatus(auth);
    setAccountServiceStatus(account);
    setTransferServiceStatus(transfer);
    setNotificationServiceStatus(notif);
  }, []);

  useEffect(() => {
    if (!authed) {
      if (secret) {
        api.adminStats(secret)
          .then((data) => {
            setAuthed(true);
            setStats(data);
          })
          .catch(() => setSecret(""));
      }
      return;
    }
    loadStats(secret);
    loadUsers(secret, page, search);
    loadTransfers(secret, transfersPage);
    loadNotifications(secret, notificationsPage);
    loadAllServiceHealth();
  }, [authed, page, search, secret, transfersPage, notificationsPage, loadStats, loadUsers, loadTransfers, loadNotifications, loadAllServiceHealth]);

  const doSearch = (e) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  const logout = () => {
    localStorage.removeItem(SECRET_KEY);
    setSecret("");
    setAuthed(false);
  };

  if (!authed) {
    return <AdminLogin onAuth={(s) => { setSecret(s); setAuthed(true); }} />;
  }

  const renderServiceStatus = (name, status) => {
    const ok = status?.status === "healthy";
    return (
      <div key={name} className="flex items-center gap-2 flex-wrap">
        <span className={`inline-block h-3 w-3 rounded-full shrink-0 ${
          status === null ? "bg-slate-300 animate-pulse" : ok ? "bg-emerald-500" : "bg-red-500"
        }`} />
        <span className="text-sm font-semibold">
          {name}: {status === null ? "Checking..." : ok ? "OK" : status?.error || "Unhealthy"}
        </span>
        {ok && (
          <span className="text-sm font-semibold text-slate-600">
            · <span className="font-bold">DB:</span> {status?.database} · <span className="font-bold">Redis:</span> {status?.redis}
          </span>
        )}
      </div>
    );
  };

  return (
    <Layout user="Admin" env="ADMIN" onLogout={logout} onBack={onBack} activePage="admin" adminSubPage={adminSubPage} onAdminSubPage={setAdminSubPage}>
      <div className="space-y-6">
        {adminSubPage === "overview" && (
          <>
            {stats && <StatsCards stats={stats} />}
            <Card title="Users" desc={`${total} total users`}>
          <form onSubmit={doSearch} className="mb-4 flex gap-2">
            <input
              className="flex-1 rounded-xl border px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="Search by name, phone, or account number..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
            <button
              type="submit"
              className="rounded-xl bg-amber-600 px-5 py-2 text-sm font-semibold text-white hover:bg-amber-700"
            >
              Search
            </button>
            {search && (
              <button
                type="button"
                onClick={() => { setSearchInput(""); setSearch(""); setPage(1); }}
                className="rounded-xl border px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50"
              >
                Clear
              </button>
            )}
          </form>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-semibold text-slate-500">
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">Username</th>
                  <th className="px-3 py-2">Phone</th>
                  <th className="px-3 py-2">Account</th>
                  <th className="px-3 py-2 text-right">Balance</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b hover:bg-slate-50">
                    <td className="px-3 py-2 text-slate-500">{u.id}</td>
                    <td className="px-3 py-2 font-semibold text-slate-900">{u.username}</td>
                    <td className="px-3 py-2 text-slate-600">{u.phone}</td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-500">{u.account_number}</td>
                    <td className="px-3 py-2 text-right font-semibold text-blue-700">{u.balance?.toLocaleString()} ₫</td>
                    <td className="px-3 py-2">
                      <button
                        onClick={() => setSelectedUser(u)}
                        className="rounded-lg bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-200"
                      >
                        Detail
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-slate-400">
                      No users found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {pages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <div className="text-xs text-slate-500">
                Page {page} of {pages} ({total} users)
              </div>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="rounded-lg border px-3 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  Prev
                </button>
                <button
                  disabled={page >= pages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-lg border px-3 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </Card>
          </>
        )}

        {adminSubPage === "transfers" && (
        <Card title="Transfers History" desc={`${transfersTotal} total transfers`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-semibold text-slate-500">
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">From</th>
                  <th className="px-3 py-2">To</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                  <th className="px-3 py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {transfers.map((t) => (
                  <tr key={t.id} className="border-b hover:bg-slate-50">
                    <td className="px-3 py-2 text-slate-500">{t.id}</td>
                    <td className="px-3 py-2">{t.from_username} <span className="text-slate-400">#{t.from_user}</span></td>
                    <td className="px-3 py-2">{t.to_username} <span className="text-slate-400">#{t.to_user}</span></td>
                    <td className="px-3 py-2 text-right font-semibold text-emerald-700">{t.amount?.toLocaleString()} ₫</td>
                    <td className="px-3 py-2 text-xs text-slate-500">{t.created_at ? new Date(t.created_at).toLocaleString() : ""}</td>
                  </tr>
                ))}
                {transfers.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-slate-400">No transfers yet</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {transfersPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <div className="text-xs text-slate-500">Page {transfersPage} of {transfersPages}</div>
              <div className="flex gap-2">
                <button
                  disabled={transfersPage <= 1}
                  onClick={() => setTransfersPage((p) => Math.max(1, p - 1))}
                  className="rounded-lg border px-3 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  Prev
                </button>
                <button
                  disabled={transfersPage >= transfersPages}
                  onClick={() => setTransfersPage((p) => p + 1)}
                  className="rounded-lg border px-3 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </Card>
        )}

        {adminSubPage === "notifications" && (
        <Card title="Notifications" desc={`${notificationsTotal} total notifications`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-semibold text-slate-500">
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">User</th>
                  <th className="px-3 py-2">Message</th>
                  <th className="px-3 py-2">Read</th>
                  <th className="px-3 py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {notifications.map((n) => (
                  <tr key={n.id} className="border-b hover:bg-slate-50">
                    <td className="px-3 py-2 text-slate-500">{n.id}</td>
                    <td className="px-3 py-2">{n.username} <span className="text-slate-400">#{n.user_id}</span></td>
                    <td className="px-3 py-2 max-w-xs truncate">{n.message}</td>
                    <td className="px-3 py-2">{n.is_read ? "✓" : "—"}</td>
                    <td className="px-3 py-2 text-xs text-slate-500">{n.created_at ? new Date(n.created_at).toLocaleString() : ""}</td>
                  </tr>
                ))}
                {notifications.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-slate-400">No notifications yet</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {notificationsPages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <div className="text-xs text-slate-500">Page {notificationsPage} of {notificationsPages}</div>
              <div className="flex gap-2">
                <button
                  disabled={notificationsPage <= 1}
                  onClick={() => setNotificationsPage((p) => Math.max(1, p - 1))}
                  className="rounded-lg border px-3 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  Prev
                </button>
                <button
                  disabled={notificationsPage >= notificationsPages}
                  onClick={() => setNotificationsPage((p) => p + 1)}
                  className="rounded-lg border px-3 py-1 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </Card>
        )}

        {adminSubPage === "health" && (
        <Card title="Service Health" desc="All backend services status">
          <div className="space-y-4">
            <div className="space-y-3">
              {renderServiceStatus("Auth Service", authServiceStatus)}
              {renderServiceStatus("Account Service", accountServiceStatus)}
              {renderServiceStatus("Transfer Service", transferServiceStatus)}
              {renderServiceStatus("Notification Service", notificationServiceStatus)}
            </div>
            <button
              onClick={loadAllServiceHealth}
              className="rounded-lg border px-3 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              Refresh
            </button>
          </div>
        </Card>
        )}
      </div>

      {selectedUser && (
        <UserDetailModal user={selectedUser} secret={secret} onClose={() => setSelectedUser(null)} />
      )}
    </Layout>
  );
}
