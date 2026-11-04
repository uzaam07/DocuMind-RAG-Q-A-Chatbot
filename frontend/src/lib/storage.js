function area(kind) {
  return kind === 'session' ? window.sessionStorage : window.localStorage;
}

export function readStore(kind, key) {
  try {
    return area(kind).getItem(key);
  } catch {
    return null;
  }
}

export function writeStore(kind, key, value) {
  try {
    area(kind).setItem(key, value);
  } catch {
    /* storage unavailable: the app works without persistence */
  }
}

export function removeStore(kind, key) {
  try {
    area(kind).removeItem(key);
  } catch {
    /* storage unavailable */
  }
}
