import React from "react";

export default function Card({ title, desc, right, children }) {
  return (
    <div className="rounded-2xl border bg-white p-5 shadow-sm">
      {(title || desc || right) && (
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <div className="text-sm font-semibold text-slate-900">{title}</div>}
            {desc && <div className="mt-1 text-xs text-slate-500">{desc}</div>}
          </div>
          {right}
        </div>
      )}
      {children}
    </div>
  );
}
