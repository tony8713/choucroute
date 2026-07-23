import { type KitPalette } from '@stage-labs/kit/react-native/theme-context';
import { semanticPalette } from '@stage-labs/kit/tokens';

export type ThemePreference = 'system' | 'light' | 'dark';

export function resolveScheme(preference: ThemePreference): 'light' | 'dark' {
  if (preference !== 'system') return preference;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function buildPalette(scheme: 'light' | 'dark'): KitPalette {
  const s = semanticPalette(scheme);
  return {
    bg: s.bgColor,
    border: s.borderColor,
    text: s.textColor,
    sub: s.subColor,
    link: s.linkColor,
    primary: s.primaryColor,
    danger: s.dangerColor,
    success: s.successColor,
    inputBg: s.inputBgColor,
    toolbarBg: s.toolbarBgColor,
  };
}
