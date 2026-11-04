import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../state/theme.jsx';

export default function ThemeToggle({ className = 'btn btn--ghost btn--sm' }) {
  const { theme, toggle } = useTheme();
  const Icon = theme === 'dark' ? Sun : Moon;
  return (
    <button type="button" className={className} onClick={toggle} title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'} aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
      <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
      {theme === 'dark' ? 'Light theme' : 'Dark theme'}
    </button>
  );
}
