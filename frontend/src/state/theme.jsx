import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { readStore, writeStore } from '../lib/storage.js';

const THEME_KEY = 'documind.theme';
const THEME_COLORS = { dark: '#0b1017', light: '#edf2f6' };
const ThemeContext = createContext(null);

function initialTheme() {
  const saved = readStore('local', THEME_KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  return 'dark';
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(initialTheme);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLORS[theme]);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark';
      writeStore('local', THEME_KEY, next);
      return next;
    });
  }, []);

  const value = useMemo(() => ({ theme, toggle }), [theme, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
