import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { readStore, writeStore } from '../lib/storage.js';

const SCOPE_KEY = 'documind.scope';
const ScopeContext = createContext(null);

function initialScope() {
  try {
    const parsed = JSON.parse(readStore('session', SCOPE_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === 'string') : [];
  } catch {
    return [];
  }
}

/**
 * Document ids the user narrowed questions to. An empty selection means
 * "all documents", which is what the API does when doc_ids is omitted.
 */
export function ScopeProvider({ children }) {
  const [ids, setIds] = useState(initialScope);

  useEffect(() => {
    writeStore('session', SCOPE_KEY, JSON.stringify(ids));
  }, [ids]);

  const toggle = useCallback((id) => {
    setIds((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]));
  }, []);

  const setMany = useCallback((next) => setIds([...new Set(next)]), []);
  const clear = useCallback(() => setIds([]), []);

  const prune = useCallback((existing) => {
    setIds((current) => {
      const kept = current.filter((id) => existing.has(id));
      return kept.length === current.length ? current : kept;
    });
  }, []);

  const value = useMemo(() => ({ ids, toggle, setMany, clear, prune }), [ids, toggle, setMany, clear, prune]);
  return <ScopeContext.Provider value={value}>{children}</ScopeContext.Provider>;
}

export function useScope() {
  return useContext(ScopeContext);
}
