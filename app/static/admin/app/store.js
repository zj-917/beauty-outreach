/* 全局数据缓存：总览只保留很短时间，写操作后主动失效。 */

import { api } from "./api.js";

let overview = null;
let loadedAt = 0;
let inflight = null;
const listeners = new Set();

export async function loadOverview(force = false) {
  const fresh = overview && Date.now() - loadedAt < 15000;
  if (fresh && !force) return overview;
  if (inflight && !force) return inflight;
  inflight = api("/stats/overview")
    .then((data) => {
      overview = data;
      loadedAt = Date.now();
      notify();
      return data;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

export function cachedOverview() {
  return overview;
}

export function invalidateOverview() {
  overview = null;
  loadedAt = 0;
}

export function onOverviewChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify() {
  for (const fn of listeners) {
    try {
      fn(overview);
    } catch (error) {
      /* 单个订阅者出错不影响其他页面。 */
    }
  }
}
