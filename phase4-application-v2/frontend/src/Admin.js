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
  }, [authed, page, search, secret, loadStats, loadUsers]);

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

  return (
    <Layout user="Admin" env="ADMIN" onLogout={logout} onBack={onBack} activePage="admin">
      <div className="space-y-6">
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
      </div>

      {selectedUser && (
        <UserDetailModal user={selectedUser} secret={secret} onClose={() => setSelectedUser(null)} />
      )}
    </Layout>
  );
}
