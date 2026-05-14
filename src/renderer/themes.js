export const themes = {
  midnight: { name: 'Midnight', bg: '#0b1220', surface: '#111827', surface2: '#172033', surface3: '#1f2a44', accent: '#38bdf8', accent2: '#7dd3fc', text: '#e5e7eb', muted: '#94a3b8', danger: '#fb7185', success: '#34d399', border: '#5a6d95', termBg: '#050816', termFg: '#d1d5db' },
  graphite: { name: 'Graphite', bg: '#111111', surface: '#1b1b1f', surface2: '#24242a', surface3: '#303039', accent: '#a3e635', accent2: '#bef264', text: '#f3f4f6', muted: '#a1a1aa', danger: '#f87171', success: '#4ade80', border: '#73737d', termBg: '#080808', termFg: '#e4e4e7' },
  nord: { name: 'Nord', bg: '#2e3440', surface: '#3b4252', surface2: '#434c5e', surface3: '#4c566a', accent: '#88c0d0', accent2: '#8fbcbb', text: '#eceff4', muted: '#d8dee9', danger: '#bf616a', success: '#a3be8c', border: '#81a1c1', termBg: '#242933', termFg: '#eceff4' },
  dracula: { name: 'Dracula', bg: '#282a36', surface: '#343746', surface2: '#3d4053', surface3: '#44475a', accent: '#bd93f9', accent2: '#ff79c6', text: '#f8f8f2', muted: '#cfcfe6', danger: '#ff5555', success: '#50fa7b', border: '#8be9fd', termBg: '#1e1f29', termFg: '#f8f8f2' },
  solarized: { name: 'Solarized Dark', bg: '#002b36', surface: '#073642', surface2: '#0b3f4d', surface3: '#124b5b', accent: '#268bd2', accent2: '#2aa198', text: '#eee8d5', muted: '#93a1a1', danger: '#dc322f', success: '#859900', border: '#839496', termBg: '#001f27', termFg: '#eee8d5' }
};
export function resolveTheme(settings) {
  if (settings.theme === 'custom' && settings.customTheme) return { ...themes.midnight, ...settings.customTheme, name: 'Custom' };
  return themes[settings.theme] || themes.midnight;
}
export function applyTheme(theme) {
  const root = document.documentElement;
  Object.entries(theme).forEach(([key, value]) => root.style.setProperty(`--${key}`, value));
}
