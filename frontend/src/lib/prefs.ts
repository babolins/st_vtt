// Per-viewer UI preferences (collapsed sections etc.) in localStorage.
const KEY = 'st_vtt.prefs';
let cache: Record<string, unknown> | null = null;

function load(): Record<string, unknown> {
  if (cache) return cache;
  try {
    cache = JSON.parse(localStorage.getItem(KEY) || '{}');
  } catch {
    cache = {};
  }
  return cache!;
}

export function getPref<T>(key: string, fallback: T): T {
  const v = load()[key];
  return v === undefined ? fallback : (v as T);
}

export function setPref(key: string, value: unknown): void {
  const p = load();
  p[key] = value;
  try {
    localStorage.setItem(KEY, JSON.stringify(p));
  } catch {}
}
