export function BalanceCard({ amount }) {
  return (
    <div className="bg-white rounded-xl shadow p-6">
      <p className="text-sm text-slate-500">Account Balance</p>
      <p className="text-3xl font-bold text-slate-800 mt-2">
        {amount.toLocaleString()} ₫
      </p>
    </div>
  );
}
