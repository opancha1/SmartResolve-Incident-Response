export function resolveTheme(savedTheme, prefersDark = false) {
  if (savedTheme === 'light' || savedTheme === 'dark') return savedTheme;
  return prefersDark ? 'dark' : 'light';
}

export function getInitialTheme() {
  const saved = window.localStorage.getItem('sr_theme');
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  return resolveTheme(saved, prefersDark);
}
