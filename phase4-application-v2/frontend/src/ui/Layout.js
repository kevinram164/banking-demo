import React from "react";

export default function Layout({ user, env = "LAB", onLogout, onBack, onGoAdmin, activePage = "dashboard", adminSubPage, onAdminSubPage, children }) {
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
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
              env === "ADMIN" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-700"
            }`}>
              {env}
            </span>
            {user && (
              <span className="text-xs text-slate-600">
                Signed in as <span className="font-semibold text-slate-900">{user}</span>
              </span>
            )}
            {onBack && (
              <button
                onClick={onBack}
                className="rounded-xl border px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Back
              </button>
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
              <div className={`rounded-xl px-3 py-2 font-semibold ${activePage === "dashboard" ? "bg-blue-50 text-blue-700" : "text-slate-700 hover:bg-slate-50"}`}>Dashboard</div>
              {env === "ADMIN" && onAdminSubPage ? (
                <>
                  <div
                    onClick={() => onAdminSubPage("overview")}
                    className={`rounded-xl px-3 py-2 font-semibold cursor-pointer ${adminSubPage === "overview" ? "bg-amber-50 text-amber-700" : "text-slate-700 hover:bg-amber-50"}`}
                  >
                    Overview
                  </div>
                  <div
                    onClick={() => onAdminSubPage("transfers")}
                    className={`rounded-xl px-3 py-2 font-semibold cursor-pointer ${adminSubPage === "transfers" ? "bg-amber-50 text-amber-700" : "text-slate-700 hover:bg-amber-50"}`}
                  >
                    Transfers History
                  </div>
                  <div
                    onClick={() => onAdminSubPage("notifications")}
                    className={`rounded-xl px-3 py-2 font-semibold cursor-pointer ${adminSubPage === "notifications" ? "bg-amber-50 text-amber-700" : "text-slate-700 hover:bg-amber-50"}`}
                  >
                    Notifications
                  </div>
                  <div
                    onClick={() => onAdminSubPage("health")}
                    className={`rounded-xl px-3 py-2 font-semibold cursor-pointer ${adminSubPage === "health" ? "bg-amber-50 text-amber-700" : "text-slate-700 hover:bg-amber-50"}`}
                  >
                    Service Health
                  </div>
                </>
              ) : (
                <>
                  <div className="rounded-xl px-3 py-2 text-slate-700">Transfers</div>
                  <div className="rounded-xl px-3 py-2 text-slate-700">Notifications</div>
                </>
              )}
              {onGoAdmin && !(env === "ADMIN" && onAdminSubPage) && (
                <div
                  onClick={onGoAdmin}
                  className={`rounded-xl px-3 py-2 font-semibold cursor-pointer ${activePage === "admin" ? "bg-amber-50 text-amber-700" : "text-slate-700 hover:bg-amber-50"}`}
                >
                  Admin Panel
                </div>
              )}
              {activePage === "admin" && !onGoAdmin && (
                <div className="rounded-xl bg-amber-50 px-3 py-2 font-semibold text-amber-700">Admin Panel</div>
              )}
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
