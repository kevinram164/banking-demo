/**
 * Load test — Transfer service
 * Hai user chuyển tiền qua lại (1 đơn vị) → tăng RPS transfer-service.
 *
 * Chạy: k6 run --vus 10 --duration 2m k6-transfer.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const HOST_HEADER = __ENV.HOST_HEADER || ''; // Khi gọi bằng IP, set HOST_HEADER=npd-banking.co để Ingress route đúng
const VUS = __ENV.VUS ? parseInt(__ENV.VUS, 10) : 10;
const DURATION = __ENV.DURATION || '2m';

function headers(extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra };
  if (HOST_HEADER) h['Host'] = HOST_HEADER;
  return h;
}

export const options = {
  vus: VUS,
  duration: DURATION,
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<5000'],
  },
};

const U1 = { username: 'loadtest1', password: 'loadtest1' };
const U2 = { username: 'loadtest2', password: 'loadtest2' };

export function setup() {
  for (const u of [U1, U2]) {
    const r = http.post(`${BASE_URL}/api/auth/register`, JSON.stringify(u), { headers: headers() });
    if (r.status !== 200 && r.status !== 409) console.warn(`register ${u.username}: ${r.status}`);
  }
  return {};
}

function login(u) {
  const r = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify(u), { headers: headers() });
  return r.status === 200 ? r.json('session') : null;
}

export default function () {
  const s1 = login(U1);
  const s2 = login(U2);
  if (!s1 || !s2) return;

  const tr = http.post(
    `${BASE_URL}/api/transfer/transfer`,
    JSON.stringify({ to_username: U2.username, amount: 1 }),
    { headers: headers({ 'X-Session': s1 }) }
  );
  check(tr, { 'transfer 1->2 ok': (r) => r.status === 200 });
  sleep(0.2);

  const tr2 = http.post(
    `${BASE_URL}/api/transfer/transfer`,
    JSON.stringify({ to_username: U1.username, amount: 1 }),
    { headers: headers({ 'X-Session': s2 }) }
  );
  check(tr2, { 'transfer 2->1 ok': (r) => r.status === 200 });
  sleep(0.2);
}
