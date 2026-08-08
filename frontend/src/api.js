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
  if (!res.ok) {
    const code = data.error_code ? `[${data.error_code}] ` : "";
    throw new Error(code + (data.detail || "Request failed"));
  }
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

  myTransfers: (page = 1, size = 20) =>
    req(`/api/account/me/transfers?page=${page}&size=${size}`),

  lookupAccount: (account_number) =>
    req(`/api/account/lookup?account_number=${encodeURIComponent(account_number)}`),

  transfer: (to_account_number, amount, note = "", extra = {}) =>
    req("/api/transfer/transfer", {
      method: "POST",
      body: {
        to_account_number,
        amount: Number(amount),
        ...(note ? { note: String(note).trim() } : {}),
        ...extra,
      },
    }),

  confirmTransfer: (transfer_id) =>
    req("/api/transfer/confirm", {
      method: "POST",
      body: { transfer_id: Number(transfer_id) },
    }),

  cancelTransfer: (transfer_id) =>
    req("/api/transfer/cancel", {
      method: "POST",
      body: { transfer_id: Number(transfer_id) },
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

  async authServiceHealth() {
    try { return await req("/api/auth/health"); } catch (e) { return { error: e.message || "Unreachable" }; }
  },
  async accountServiceHealth() {
    try { return await req("/api/account/health"); } catch (e) { return { error: e.message || "Unreachable" }; }
  },
  async transferServiceHealth() {
    try { return await req("/api/transfer/health"); } catch (e) { return { error: e.message || "Unreachable" }; }
  },
  async notificationServiceHealth() {
    try { return await req("/api/notifications/health"); } catch (e) { return { error: e.message || "Unreachable" }; }
  },
};
