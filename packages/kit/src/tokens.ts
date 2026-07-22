export const colors = {
  'bg-dark': '#0e0f10',
  'bg-light': '#ffffff',
  'surface-dark': '#282a2d',
  'surface-light': '#e4e4e5',
  'input-bg-dark': '#1c1d1f',
  'input-bg-light': '#f2f2f3',
  'toolbar-bg-dark': '#0e0f10',
  'toolbar-bg-light': '#ffffff',
  'hover-dark': '#1c1d1f',
  'hover-light': '#f2f2f3',
  'fg-dark': '#9f9fa3',
  'fg-light': '#57606a',
  'sub-dark': '#7a7a7e',
  'sub-light': '#8a929d',
  'head-dark': '#ffffff',
  'head-light': '#000000',
  'border-dark': '#282a2d',
  'border-light': '#e4e4e5',
  accent: '#ffffff',
  'accent-hover': '#cccccc',
  ok: '#83c989',
  warn: '#c0a06e',
  err: '#d96868',
  'danger-dark': '#eb4c5b',
  'danger-light': '#eb4c5b',
  'success-dark': '#57b375',
  'success-light': '#57b375',
  'primary-dark': '#ffffff',
  'primary-light': '#000000',
  'link-dark': '#ffffff',
  'link-light': '#000000',
} as const;

export const semanticColors = {
  bgColor: { dark: colors['bg-dark'], light: colors['bg-light'] },
  borderColor: { dark: colors['border-dark'], light: colors['border-light'] },
  textColor: { dark: colors['fg-dark'], light: colors['fg-light'] },
  subColor: { dark: colors['sub-dark'], light: colors['sub-light'] },
  linkColor: { dark: colors['link-dark'], light: colors['link-light'] },
  primaryColor: { dark: colors['primary-dark'], light: colors['primary-light'] },
  dangerColor: { dark: colors['danger-dark'], light: colors['danger-light'] },
  successColor: { dark: colors['success-dark'], light: colors['success-light'] },
  inputBgColor: { dark: colors['input-bg-dark'], light: colors['input-bg-light'] },
  toolbarBgColor: { dark: colors['toolbar-bg-dark'], light: colors['toolbar-bg-light'] },
} as const;

export type Scheme = 'light' | 'dark';

export function semanticPalette(scheme: Scheme): {
  bgColor: string; borderColor: string; textColor: string; subColor: string;
  linkColor: string; primaryColor: string;
  dangerColor: string; successColor: string;
  inputBgColor: string; toolbarBgColor: string;
} {
  return {
    bgColor: semanticColors.bgColor[scheme],
    borderColor: semanticColors.borderColor[scheme],
    textColor: semanticColors.textColor[scheme],
    subColor: semanticColors.subColor[scheme],
    linkColor: semanticColors.linkColor[scheme],
    primaryColor: semanticColors.primaryColor[scheme],
    dangerColor: semanticColors.dangerColor[scheme],
    successColor: semanticColors.successColor[scheme],
    inputBgColor: semanticColors.inputBgColor[scheme],
    toolbarBgColor: semanticColors.toolbarBgColor[scheme],
  };
}

export function readableForeground(hex: string): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  const group = m?.[1];
  if (group === undefined) return '#ffffff';
  const n = Number.parseInt(group, 16);
  const r = (n >> 16) & 0xff;
  const g = (n >> 8) & 0xff;
  const b = n & 0xff;
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? '#000000' : '#ffffff';
}

export interface SchemePalette {
  head: string;
  text: string;
  sub: string;
  surface: string;
  pressed: string;
  border: string;
}

export function schemePalette(dark: boolean): SchemePalette {
  const k = dark ? 'dark' : 'light';
  return {
    head: colors[`head-${k}`],
    text: colors[`fg-${k}`],
    sub: colors[`sub-${k}`],
    surface: colors[`hover-${k}`],
    pressed: colors[`hover-${k}`],
    border: colors[`border-${k}`],
  };
}

export type FontSizeName =
  | '3xs'
  | '2xs'
  | 'xs'
  | 'sm'
  | 'md'
  | 'lg'
  | 'xl'
  | '2xl'
  | '3xl'
  | '4xl'
  | '5xl'
  | '6xl'
  | '7xl';

export const FONT_SIZE: Record<FontSizeName, number> = {
  '3xs': 11,
  '2xs': 12,
  xs: 13,
  sm: 14,
  md: 15,
  lg: 16,
  xl: 17,
  '2xl': 18,
  '3xl': 19,
  '4xl': 20,
  '5xl': 24,
  '6xl': 32,
  '7xl': 40,
} as const;

export function fontSize(name: FontSizeName): number {
  return FONT_SIZE[name];
}

export const fontFamily = {
  sans: ['Calibre-Medium', 'system-ui', 'sans-serif'],
  head: ['Calibre-Semibold', 'system-ui', 'sans-serif'],
  mono: ['Menlo', 'ui-monospace', 'monospace'],
} as const;

export type RadiusName = 'pill' | 'round' | 'soft' | 'sharp';

export const RADIUS_SCALE: Record<RadiusName, number> = {
  pill: 999,
  round: 16,
  soft: 12,
  sharp: 0,
} as const;

export const RADIUS_NAME_DEFAULT: RadiusName = 'pill';

export {
  type RadiusValue,
  BOX_RADIUS_SCALE,
  isRadiusValue,
  resolveBoxRadius,
} from './radius';

export type Density = 'compact' | 'normal' | 'spacious';

export const DENSITY_SCALE: Record<Density, { paddingX: number; paddingY: number; gap: number }> = {
  compact: { paddingX: 10, paddingY: 6, gap: 6 },
  normal: { paddingX: 14, paddingY: 10, gap: 10 },
  spacious: { paddingX: 18, paddingY: 14, gap: 14 },
} as const;

export const DENSITY_DEFAULT: Density = 'normal';
