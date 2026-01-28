const API = ""; // dùng cùng origin

export function setSession(session) {
  localStorage.setItem("session", session);
}

export function getSession() {
  return localStorage.getItem("session");
}

export function clearSession() {
  localStorage.removeItem("session");
}

async function req(path, { method = "GET", body } = {}) {
  const session = getSession();

  const res = await fetch(API + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { "X-Session": session } : {})
    },
    body: body ? JSON.stringify(body) : undefined
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

export const api = {
  register: (phone, username, password) =>
    req("/api/auth/register", {
      method: "POST",
      body: { phone, username, password }
    }),

  login: (phone, password) =>
    req("/api/auth/login", {
      method: "POST",
      body: { phone, password }
    }),

  me: () => req("/api/account/me"),

  lookupAccount: (account_number) =>
    req(`/api/account/lookup?account_number=${encodeURIComponent(account_number)}`),

  transfer: (to_account_number, amount) =>
    req("/api/transfer/transfer", {
      method: "POST",
      body: { to_account_number, amount: Number(amount) }
    }),

  notifications: () => req("/api/notifications/notifications")
};
