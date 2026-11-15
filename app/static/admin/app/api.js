/* 统一 API 客户端：鉴权头、查询串、错误归一化与 401 事件。 */

const TOKEN_KEY = "bo.token";
const OPERATOR_KEY = "bo.operator";

const auth = {
  token: sessionStorage.getItem(TOKEN_KEY) || "",
  operator: sessionStorage.getItem(OPERATOR_KEY) || "admin",
};

export function getAuth() {
  return { ...auth };
}

export function setAuth(token, operator) {
  auth.token = (token || "").trim();
  auth.operator = (operator || "admin").trim() || "admin";
  sessionStorage.setItem(TOKEN_KEY, auth.token);
  sessionStorage.setItem(OPERATOR_KEY, auth.operator);
}

export function clearAuth() {
  auth.token = "";
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(OPERATOR_KEY);
}

export class ApiError extends Error {
  constructor(code, message, requestId, status, details) {
    super(message || code);
    this.name = "ApiError";
    this.code = code || "UNKNOWN";
    this.requestId = requestId || null;
    this.status = status || 0;
    this.details = details || null;
  }
}

function buildHeaders(payload) {
  const headers = {
    "X-Admin-Token": auth.token,
    "X-Operator": auth.operator,
  };
  /* FormData 由浏览器自带 multipart boundary，不能手动设置 Content-Type。 */
  if (payload !== undefined && !(payload instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

export function buildQuery(query) {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined || value === "") continue;
    params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

async function parseError(response) {
  let detail = {
    code: String(response.status),
    message: response.statusText || "请求失败",
    request_id: null,
  };
  try {
    const parsed = await response.json();
    if (parsed && parsed.error) detail = parsed.error;
  } catch (error) {
    /* 非 JSON 响应沿用默认说明。 */
  }
  return new ApiError(
    detail.code,
    detail.message,
    detail.request_id,
    response.status,
    detail.details || null
  );
}

async function request(base, path, { method = "GET", body, form, query } = {}) {
  let payload;
  if (form) payload = form;
  else if (body !== undefined) payload = JSON.stringify(body);
  let response;
  try {
    response = await fetch(base + path + buildQuery(query), {
      method,
      headers: buildHeaders(payload),
      body: payload,
    });
  } catch (error) {
    throw new ApiError("NETWORK_ERROR", "无法连接服务器，请确认服务已启动。", null, 0);
  }
  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent("bo:unauthorized"));
    throw new ApiError("UNAUTHORIZED", "访问口令无效或已失效。", null, 401);
  }
  if (!response.ok) throw await parseError(response);
  return response.status === 204 ? null : response.json();
}

export const api = (path, options) => request("/api/v1", path, options);
export const demo = (path, options) => request("/demo", path, options);

export async function probeDemo() {
  try {
    const response = await fetch("/demo/flush-receipts", {
      method: "GET",
      headers: buildHeaders(),
    });
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent("bo:unauthorized"));
      return false;
    }
    return response.status !== 404;
  } catch (error) {
    return false;
  }
}

export async function checkHealth() {
  const response = await fetch("/healthz");
  if (!response.ok) throw new ApiError("HEALTH_ERROR", "系统健康检查失败。", null, response.status);
  return response.json();
}

export function errorText(error) {
  const request = error && error.requestId ? ` · 请求编号 ${error.requestId}` : "";
  if (error instanceof ApiError) {
    return `${error.message}（错误码 ${error.code}）${request}`;
  }
  return `操作失败：${String(error)}`;
}
