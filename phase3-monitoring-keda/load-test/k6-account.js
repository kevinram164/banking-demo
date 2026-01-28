/**
 * Load test — Account service (/me)
 * Mỗi VU login 1 lần, cache session, rồi gọi GET /api/account/me lặp lại → tăng RPS account-service.
 *
 * Chạy: k6 run --vus 10 --duration 2m k6-account.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const VUS = __ENV.VUS ? parseInt(__ENV.VUS, 10) : 10;
const DURATION = __ENV.DURATION || '2m';

export const options = {
  vus: VUS,
  duration: DURATION,
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<3000'],
  },
};

const USER = { username: 'loadtest1', password: 'loadtest1' };

export function setup() {
  http.post(`${BASE_URL}/api/auth/register`, JSON.stringify(USER), {
    headers: { 'Content-Type': 'application/json' },
  });
  return {};
}

let session = null;

export default function () {
  if (!session) {
    const r = http.post(`${BASE_URL}/api/auth/login`, JSON.stringify(USER), {
      headers: { 'Content-Type': 'application/json' },
    });
    if (r.status !== 200) return;
    session = r.json('session');
  }
  const meRes = http.get(`${BASE_URL}/api/account/me`, {
    headers: { 'X-Session': session },
  });
  check(meRes, { 'me ok': (r) => r.status === 200 });
  sleep(0.1);
}
