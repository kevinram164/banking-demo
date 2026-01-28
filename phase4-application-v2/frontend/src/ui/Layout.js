import React from "react";

export default function Layout({ user, env = "LAB", onLogout, children }) {
  return (
    <div className="min-h-screen bg-slate-50">
      {/* Topbar */}
      <header className="sticky top-0 z-10 border-b bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-blue-600 text-white font-bold">
              B
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900">NPD Banking</div>
              <div className="text-xs text-slate-500">Postgres • Redis Session • WebSocket Notify</div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
              {env}
            </span>
            {user && (
              <span className="text-xs text-slate-600">
                Signed in as <span className="font-semibold text-slate-900">{user}</span>
              </span>
            )}
            <button
              onClick={onLogout}
              className="rounded-xl border px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 py-6 lg:grid-cols-12">
        {/* Sidebar */}
        <aside className="lg:col-span-3">
          <div className="rounded-2xl border bg-white p-4 shadow-sm">
            <div className="text-xs font-semibold text-slate-500">MENU</div>
            <div className="mt-3 space-y-2 text-sm">
              <div className="rounded-xl bg-blue-50 px-3 py-2 font-semibold text-blue-700">Dashboard</div>
              <div className="rounded-xl px-3 py-2 text-slate-700 hover:bg-slate-50">Transfers</div>
              <div className="rounded-xl px-3 py-2 text-slate-700 hover:bg-slate-50">Notifications</div>
            </div>
            <div className="mt-4 rounded-xl bg-slate-50 px-3 py-3 text-xs text-slate-600">
              Demo focus: <span className="font-semibold">Session in Redis</span>, realtime notify via{" "}
              <span className="font-semibold">WebSocket</span>.
            </div>
          </div>
        </aside>

        {/* Main */}
        <main className="lg:col-span-9">{children}</main>
      </div>
    </div>
  );
}
