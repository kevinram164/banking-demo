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

async function req(path, { method = "GET", body, headers = {} } = {}) {
  const session = getSession();

  const res = await fetch(API + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { "X-Session": session } : {}),
      ...headers,
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

  notifications: () => req("/api/notifications/notifications"),

  adminStats: (secret) =>
    req("/api/account/admin/stats", { headers: { "X-Admin-Secret": secret } }),

  adminUsers: (secret, page = 1, size = 20, search = "") =>
    req(`/api/account/admin/users?page=${page}&size=${size}&search=${encodeURIComponent(search)}`, {
      headers: { "X-Admin-Secret": secret },
    }),

  adminUserDetail: (secret, userId) =>
    req(`/api/account/admin/users/${userId}`, {
      headers: { "X-Admin-Secret": secret },
    }),

  adminTransfers: (secret, page = 1, size = 20) =>
    req(`/api/account/admin/transfers?page=${page}&size=${size}`, {
      headers: { "X-Admin-Secret": secret },
    }),

  adminNotifications: (secret, page = 1, size = 20, userId = "") =>
    req(`/api/account/admin/notifications?page=${page}&size=${size}${userId ? `&user_id=${userId}` : ""}`, {
      headers: { "X-Admin-Secret": secret },
    }),

  // Health check notification service (no auth required) — returns { status, ... } or { error }
  async notificationServiceHealth() {
    try {
      return await req("/api/notifications/health");
    } catch (e) {
      return { error: e.message || "Unreachable" };
    }
  },
};
