import { useEffect } from 'react';

/**
 * ThemeToggle — dark mode only.
 * Ensures dark theme is always active and clears any stale light-mode preference.
 * Renders nothing (no toggle button).
 */
const ThemeToggle = () => {
  useEffect(() => {
    document.documentElement.classList.remove('light');
    localStorage.setItem('lumos-theme', 'dark');
  }, []);

  return null;
};

export default ThemeToggle;
