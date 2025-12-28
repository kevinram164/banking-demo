import React from "react";

export default function Layout({ title, subtitle, right, children }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Top bar */}
      <div className="border-b bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold">
              B
            </div>
            <div>
              <div className="text-sm font-semibold">{title}</div>
              {subtitle && <div className="text-xs text-slate-500">{subtitle}</div>}
            </div>
          </div>
          <div>{right}</div>
        </div>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-6xl px-4 py-8">
        {children}
        <div className="mt-10 text-center text-xs text-slate-400">
          © Banking Demo Lab • Postgres + Redis
        </div>
      </div>
    </div>
  );
}
