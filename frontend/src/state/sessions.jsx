import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client.js';

const SessionsContext = createContext(null);

export function SessionsProvider({ children }) {
  const [sessions, setSessions] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setSessions(await api.listSessions());
      setStatus('ready');
      setError(null);
    } catch (err) {
      setStatus('error');
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const create = useCallback(async () => {
    const session = await api.createSession();
    setSessions((current) => [session, ...current]);
    return session;
  }, []);

  const rename = useCallback(async (id, title) => {
    const updated = await api.renameSession(id, title);
    setSessions((current) => current.map((s) => (s.id === id ? updated : s)));
  }, []);

  const remove = useCallback(async (id) => {
    await api.deleteSession(id);
    setSessions((current) => current.filter((s) => s.id !== id));
  }, []);

  const value = useMemo(
    () => ({ sessions, status, error, refresh, create, rename, remove }),
    [sessions, status, error, refresh, create, rename, remove],
  );
  return <SessionsContext.Provider value={value}>{children}</SessionsContext.Provider>;
}

export function useSessions() {
  return useContext(SessionsContext);
}
