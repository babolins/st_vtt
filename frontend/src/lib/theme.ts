export type Theme = 'light' | 'dark' | 'paper';

/** In cycle order; `paper` is the printed-sheet look (see app.css). */
export const THEMES: Theme[] = ['light', 'dark', 'paper'];

export const THEME_GLYPH: Record<Theme, string> = { light: '\u2600', dark: '\u263e', paper: '\u25a4' };

export function currentTheme(): Theme {
  const t = document.documentElement.dataset.theme as Theme;
  return THEMES.includes(t) ? t : 'light';
}

export function setTheme(t: Theme): void {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem('theme', t); } catch {}
}

export function nextTheme(): Theme {
  const t = THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
  setTheme(t);
  return t;
}
