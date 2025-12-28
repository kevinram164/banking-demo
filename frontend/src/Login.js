export default function Login({ onOk, onGoRegister }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <div className="w-full max-w-md bg-white shadow-lg rounded-xl p-8">
        <h1 className="text-2xl font-bold text-slate-800 mb-2">
          NPD Banking
        </h1>
        <p className="text-sm text-slate-500 mb-6">
          Corporate UI – Transfers & Notifications (LAB)
        </p>

        <div className="space-y-4">
          <input
            className="w-full border rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500"
            placeholder="Username"
          />
          <input
            type="password"
            className="w-full border rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500"
            placeholder="Password"
          />
        </div>

        <div className="mt-6 flex gap-3">
          <button className="flex-1 bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700">
            Sign in
          </button>
          <button
            onClick={onGoRegister}
            className="flex-1 border border-blue-600 text-blue-600 py-2 rounded-lg hover:bg-blue-50"
          >
            Create
          </button>
        </div>

        <p className="text-xs text-slate-400 mt-4">
          © Banking Demo Lab • Postgres + Redis
        </p>
      </div>
    </div>
  );
}
