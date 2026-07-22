import { type CSSProperties, type ReactNode, useState } from 'react';
import { FONT_SIZE } from '../tokens';
import { usePalette } from '../theme-context';
import { type Palette } from '../palette';

type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'sm' | 'md';

interface ButtonProps {
  variant?: Variant;
  size?: Size;
  active?: boolean;
  onClick?: () => void;
  title?: string;
  style?: CSSProperties;
  children: ReactNode;
}

const HEIGHT: Record<Size, number> = { sm: 32, md: 40 };
const PADDING: Record<Size, number> = { sm: 12, md: 16 };
const FONT: Record<Size, number> = { sm: FONT_SIZE.sm, md: FONT_SIZE.md };

function background(p: Palette, variant: Variant, filled: boolean): string {
  if (variant === 'primary') return p.primary;
  if (variant === 'ghost') return filled ? p.hover : 'transparent';
  return filled ? p.hover : p.inputBg;
}

export function Button({
  variant = 'secondary',
  size = 'md',
  active = false,
  onClick,
  title,
  style,
  children,
}: ButtonProps): ReactNode {
  const p = usePalette();
  const [hover, setHover] = useState(false);
  const solid = variant === 'primary';
  const filled = active || (variant !== 'ghost' && hover);
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      onMouseEnter={() => { setHover(true); }}
      onMouseLeave={() => { setHover(false); }}
      style={{
        height: HEIGHT[size],
        padding: `0 ${String(PADDING[size])}px`,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        borderRadius: 999,
        border: variant === 'primary' ? 'none' : `1px solid ${active ? p.text : p.border}`,
        background: background(p, variant, filled),
        color: solid ? p.onPrimary : active ? p.head : p.text,
        fontFamily: p.fontHead,
        fontWeight: 600,
        fontSize: FONT[size],
        cursor: 'pointer',
        whiteSpace: 'nowrap',
        transition: 'background 0.12s ease, color 0.12s ease',
        ...style,
      }}
    >
      {children}
    </button>
  );
}
