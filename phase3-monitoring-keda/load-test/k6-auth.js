/**
 * Load test — Auth service (login)
 * Tăng RPS lên /login để KEDA scale auth-service.
 *
 * Chạy: k6 run --vus 10 --duration 2m k6-auth.js
 * Hoặc: BASE_URL=https://npd-banking.co VUS=20 DURATION=3m k6 run k6-auth.js
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

// Kong route: /api/auth → auth-service (strip_path), nên gọi /api/auth/register, /api/auth/login
const REGISTER_PATH = __ENV.AUTH_PATH || '/api/auth/register';
const LOGIN_PATH = __ENV.AUTH_LOGIN_PATH || '/api/auth/login';

export function setup() {
  const reg = http.post(`${BASE_URL}${REGISTER_PATH}`, JSON.stringify(USER), {
    headers: { 'Content-Type': 'application/json' },
  });
  if (reg.status !== 200 && reg.status !== 409) {
    console.warn(`register failed: ${reg.status} ${reg.body}`);
  }
  return {};
}

export default function () {
  const res = http.post(`${BASE_URL}${LOGIN_PATH}`, JSON.stringify(USER), {
    headers: { 'Content-Type': 'application/json' },
  });
  check(res, { 'login ok': (r) => r.status === 200 });
  sleep(0.1);
}
