export default function Layout({ children }) {
  return (
    <div className="min-h-screen bg-slate-100">
      <header className="bg-slate-900 text-white px-6 py-4 flex justify-between">
        <h1 className="font-semibold">NPD Banking</h1>
        <span className="text-sm text-slate-300">LAB Environment</span>
      </header>

      <div className="flex">
        <aside className="w-56 bg-white shadow h-[calc(100vh-64px)] p-4">
          <ul className="space-y-3 text-slate-700">
            <li className="font-medium">Dashboard</li>
            <li>Transfers</li>
            <li>Notifications</li>
          </ul>
        </aside>

        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
