import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, setUnauthorizedHandler, tokenStore } from '../api/client.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => tokenStore.get());
  const [user, setUser] = useState(null);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setToken(null);
      setUser(null);
    });
  }, []);

  useEffect(() => {
    if (!token) return undefined;
    const controller = new AbortController();
    api.me(controller.signal).then(setUser).catch(() => {
      /* a 401 is handled globally; other failures only leave the email blank */
    });
    return () => controller.abort();
  }, [token]);

  const signIn = useCallback((response) => {
    tokenStore.set(response.access_token);
    setToken(response.access_token);
    setUser(response.user);
  }, []);

  const signOut = useCallback(() => {
    tokenStore.clear();
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ token, user, signIn, signOut }), [token, user, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
