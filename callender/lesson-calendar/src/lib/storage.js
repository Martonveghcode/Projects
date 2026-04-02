const CFG_KEY = "cfg.v1";
const LESSONS_KEY = "lessons.v1";
const PREFS_KEY = "prefs.v1";

const hasStorage = typeof window !== "undefined" && typeof window.localStorage !== "undefined";

function read(key, fallback) {
  if (!hasStorage) return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw);
  } catch (error) {
    console.warn(`[storage] Failed to parse ${key}`, error);
    return fallback;
  }
}

function write(key, value) {
  if (!hasStorage) return;
  try {
    if (value === undefined || value === null) {
      window.localStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, JSON.stringify(value));
    }
  } catch (error) {
    console.warn(`[storage] Failed to write ${key}`, error);
  }
}

export function getCfg() {
  return read(CFG_KEY, null);
}

export function setCfg(value) {
  write(CFG_KEY, value);
}

export function getLessons() {
  return read(LESSONS_KEY, []);
}

export function setLessons(value) {
  write(LESSONS_KEY, value);
}

export function getPrefs() {
  return read(PREFS_KEY, null);
}

export function setPrefs(value) {
  write(PREFS_KEY, value);
}
