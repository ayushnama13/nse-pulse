import type { CSSProperties, ReactNode } from 'react'

/**
 * Obsidian Glass primitives — the logomark, bespoke empty states, and the
 * pulse loader. These replace stock antd Empty/Spin everywhere so waiting
 * and emptiness feel designed, not default.
 */

/** Geometric pulse-wave logomark: an EKG beat inside an etched glass tile. */
export function Logo({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="oip-lg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#22d3ee" />
          <stop offset="1" stopColor="#a78bfa" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="30" height="30" rx="9.5" stroke="url(#oip-lg)" strokeOpacity="0.5" strokeWidth="1.5" />
      <path
        d="M6.5 17h4l2.2-7 4.6 12.5 2.4-8 1.8 2.5h4"
        stroke="url(#oip-lg)"
        strokeWidth="2.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="25.5" cy="17" r="1.6" fill="#22d3ee" />
    </svg>
  )
}

/** Designed empty state — ghosted logomark over a quiet hint. */
export function GlassEmpty({ description, style }: { description?: ReactNode; style?: CSSProperties }) {
  return (
    <div className="glass-empty" style={style}>
      <span className="ghost-mark">
        <Logo size={34} />
      </span>
      <span className="empty-hint">{description ?? 'No data yet'}</span>
    </div>
  )
}

/** Breathing-pulse loader — the signature motif doing the waiting. */
export function GlassLoader({ pad = 28 }: { pad?: number }) {
  return (
    <div className="glass-loader" style={{ padding: `${pad}px 0` }}>
      <span className="pulse-core" />
    </div>
  )
}
