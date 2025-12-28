import React from "react";

export default function Card({ title, desc, children, footer }) {
  return (
    <div className="rounded-2xl border bg-white shadow-sm">
      <div className="p-6">
        {(title || desc) && (
          <div className="mb-5">
            {title && <h3 className="text-base font-semibold">{title}</h3>}
            {desc && <p className="mt-1 text-sm text-slate-500">{desc}</p>}
          </div>
        )}
        {children}
      </div>
      {footer && <div className="border-t bg-slate-50 px-6 py-3 text-sm text-slate-600">{footer}</div>}
    </div>
  );
}
