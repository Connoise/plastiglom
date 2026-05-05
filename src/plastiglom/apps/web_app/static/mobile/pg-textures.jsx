// Plastiglom textures — circuitry-edition.
// Asset library mapping:
//   PGGrain       — micro-grid + LCD speckle substrate
//   PGTraces      — orthogonal circuit-trace network behind panels
//   PGSeam        — translucent amber resin/heat-weld seam
//   PGFlecks      — faint pixel dust / embedded conductive points
//   PGMark        — "Core Mark" 8-point starburst emblem
//   PGFragment    — large emblem (octagonal device-shell silhouette)
//   PGFusedPanel  — rounded-octagon laminated polymer panel with corner notch

// ─── Tokens ──────────────────────────────────────────────────────────
const PG_TOKENS = {
  light: {
    bgBase: '#F3F4F6',
    bgPanel: '#E9EAED',
    bgElev: '#F8F8F6',
    polymerBone: '#ECEDEB',
    polymerBeige: '#E6E3DE',
    smokedGray: '#C9CDD1',
    graphiteMist: '#8E9499',
    sage: '#AEB5AF',
    lilac: '#D9D6E7',
    amber: '#FFC35C',
    amberDim: '#E0A040',
    text: '#15181D',
    textSec: '#4F5660',
    textMuted: '#8E9499',
    border: 'rgba(40,46,54,0.14)',
    borderSoft: 'rgba(40,46,54,0.08)',
    traceBase: 'rgba(60,72,90,0.18)',
    traceSoft: 'rgba(60,72,90,0.10)',
    gridLine: 'rgba(60,72,90,0.07)',
  },
  dark: {
    bgBase: '#060709',
    bgPanel: '#0E1216',
    bgElev: '#161B21',
    polymerBone: '#1B2128',
    polymerBeige: '#22272F',
    smokedGray: '#2F363F',
    graphiteMist: '#3A424C',
    sage: '#383851',
    lilac: '#4D4865',
    amber: '#FFB23A',
    amberDim: '#9A641D',
    text: '#F3F4F6',
    textSec: '#B7BBC2',
    textMuted: '#7B838E',
    border: 'rgba(220,225,235,0.10)',
    borderSoft: 'rgba(220,225,235,0.05)',
    traceBase: 'rgba(255,180,90,0.18)',
    traceSoft: 'rgba(180,200,225,0.06)',
    gridLine: 'rgba(180,200,225,0.05)',
  },
};

// ─── Substrate: micro-grid + dust ────────────────────────────────────
function PGGrain({ opacity = 0.5, dark = false, seed = 7, gridStep = 8 }) {
  const t = dark ? PG_TOKENS.dark : PG_TOKENS.light;
  const id = `pg-grain-${seed}`;
  return (
    <svg
      style={{
        position: 'absolute', inset: 0, width: '100%', height: '100%',
        pointerEvents: 'none', opacity,
      }}
    >
      <defs>
        <pattern id={`${id}-grid`} width={gridStep} height={gridStep} patternUnits="userSpaceOnUse">
          <path d={`M ${gridStep} 0 L 0 0 0 ${gridStep}`} fill="none" stroke={t.gridLine} strokeWidth="0.5" />
        </pattern>
        <filter id={`${id}-noise`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.92" numOctaves="2" seed={seed} stitchTiles="stitch" />
          <feColorMatrix values={dark
            ? "0 0 0 0 0.65  0 0 0 0 0.7  0 0 0 0 0.78  0 0 0 0.10 0"
            : "0 0 0 0 0.30  0 0 0 0 0.32  0 0 0 0 0.36  0 0 0 0.10 0"} />
        </filter>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id}-grid)`} />
      <rect width="100%" height="100%" filter={`url(#${id}-noise)`} opacity="0.5" />
    </svg>
  );
}

// ─── Circuit traces — orthogonal network with occasional 45° join ────
function PGTraces({
  dark = false, opacity = 0.7, seed = 1,
  density = 7, anchor = 'br',
  litPoints = 2, // small amber endpoints
}) {
  const t = dark ? PG_TOKENS.dark : PG_TOKENS.light;
  const stroke = t.traceBase;
  const strokeSoft = t.traceSoft;
  const lit = t.amber;

  const rng = (n) => { let s = seed * 9301 + n * 49297; s = (s % 233280) / 233280; return s; };
  const segs = [];
  // Build a network: pick random grid points and trace L-shaped paths.
  const W = 360, H = 400;
  const grid = 16;
  for (let i = 0; i < density; i++) {
    const sx = Math.round(rng(i * 7) * (W / grid)) * grid;
    const sy = Math.round(rng(i * 7 + 1) * (H / grid)) * grid;
    const ex = Math.round(rng(i * 7 + 2) * (W / grid)) * grid;
    const ey = Math.round(rng(i * 7 + 3) * (H / grid)) * grid;
    const bend = rng(i * 7 + 4) > 0.5;
    // L path with optional 45° corner
    const corner = 4;
    const dx = Math.sign(ex - sx) * corner;
    const dy = Math.sign(ey - sy) * corner;
    let d;
    if (bend) {
      d = `M ${sx} ${sy} L ${ex - dx} ${sy} L ${ex} ${sy + dy} L ${ex} ${ey}`;
    } else {
      d = `M ${sx} ${sy} L ${sx} ${ey - dy} L ${sx + dx} ${ey} L ${ex} ${ey}`;
    }
    const thick = rng(i * 7 + 5) > 0.6;
    segs.push(
      <path key={`p${i}`} d={d} fill="none"
            stroke={thick ? stroke : strokeSoft}
            strokeWidth={thick ? 0.9 : 0.6}
            strokeLinecap="square" />
    );
    // small junction dot
    segs.push(<circle key={`j${i}`} cx={ex} cy={ey} r={thick ? 1.2 : 0.8}
                      fill={stroke} opacity="0.55" />);
  }
  // Lit amber endpoints
  for (let i = 0; i < litPoints; i++) {
    const x = Math.round(rng(100 + i * 5) * (W / grid)) * grid;
    const y = Math.round(rng(100 + i * 5 + 1) * (H / grid)) * grid;
    segs.push(
      <g key={`lit${i}`}>
        <circle cx={x} cy={y} r="3" fill={lit} opacity="0.18" />
        <circle cx={x} cy={y} r="1.4" fill={lit} />
      </g>
    );
  }
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%',
               pointerEvents: 'none', opacity }}>
      {segs}
    </svg>
  );
}

// ─── Resin / heat-weld seam ──────────────────────────────────────────
function PGSeam({ d, dark = false, weight = 1.1, opacity = 1 }) {
  const t = dark ? PG_TOKENS.dark : PG_TOKENS.light;
  const c = dark ? t.amber : 'rgba(176,122,46,0.55)';
  return (
    <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%',
                  pointerEvents: 'none', overflow: 'visible' }}>
      <path d={d} fill="none" stroke={c} strokeWidth={weight}
            strokeLinecap="round" strokeLinejoin="round" opacity={opacity} />
      {dark && (
        <path d={d} fill="none" stroke={c} strokeWidth={weight * 0.4}
              strokeLinecap="round" opacity={opacity * 0.7}
              style={{ filter: 'drop-shadow(0 0 1.5px rgba(255,180,80,0.6))' }} />
      )}
    </svg>
  );
}

// ─── Pixel-dust / embedded conductive flecks ────────────────────────
function PGFlecks({ count = 14, dark = false, seed = 4, color }) {
  const rng = (n) => { let s = seed * 7919 + n * 1031; s = (s % 233280) / 233280; return s; };
  const t = dark ? PG_TOKENS.dark : PG_TOKENS.light;
  const fill = color || (dark ? 'rgba(220,230,240,0.45)' : 'rgba(40,46,54,0.4)');
  const items = [];
  for (let i = 0; i < count; i++) {
    const x = rng(i * 3) * 100;
    const y = rng(i * 3 + 1) * 100;
    const s = 0.35 + rng(i * 3 + 2) * 1.0;
    if (i % 4 === 0) items.push(<rect key={i} x={`${x}%`} y={`${y}%`} width={s} height={s} fill={fill} />);
    else items.push(<circle key={i} cx={`${x}%`} cy={`${y}%`} r={s * 0.5} fill={fill} opacity="0.7" />);
  }
  // a couple amber pinlights
  for (let i = 0; i < 2; i++) {
    const x = rng(i * 11 + 90) * 100;
    const y = rng(i * 11 + 91) * 100;
    items.push(
      <circle key={`a${i}`} cx={`${x}%`} cy={`${y}%`} r="0.9"
              fill={t.amber} opacity="0.55" />
    );
  }
  return (
    <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%',
                  pointerEvents: 'none' }}>
      {items}
    </svg>
  );
}

// ─── App emblem: 8-point starburst on octagonal shell ───────────────
function PGMark({ size = 22, dark = false, color }) {
  const t = dark ? PG_TOKENS.dark : PG_TOKENS.light;
  const c = color || t.text;
  const amber = t.amber;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ flexShrink: 0 }}>
      {/* device-shell octagon */}
      <path d="M7 3 L17 3 L21 7 L21 17 L17 21 L7 21 L3 17 L3 7 Z"
            fill="none" stroke={c} strokeWidth="0.8" opacity="0.45" />
      {/* starburst */}
      <path d="M12 5 L12 19 M5 12 L19 12 M7.2 7.2 L16.8 16.8 M7.2 16.8 L16.8 7.2"
            stroke={c} strokeWidth="1.0" strokeLinecap="round" />
      <circle cx="12" cy="12" r="1.6" fill={amber} />
    </svg>
  );
}

// ─── Larger emblem ─────────────────────────────────────────────────
function PGFragment({ size = 80, dark = false }) {
  const t = dark ? PG_TOKENS.dark : PG_TOKENS.light;
  const c = t.text;
  const amber = t.amber;
  const innerFill = dark ? 'rgba(40,48,58,0.9)' : 'rgba(255,255,255,0.55)';
  return (
    <svg width={size} height={size} viewBox="0 0 100 100">
      <defs>
        <radialGradient id={`pg-frag-${dark ? 'd' : 'l'}`} cx="0.4" cy="0.4" r="0.8">
          <stop offset="0%" stopColor={dark ? '#1a2028' : '#FAFBFC'} />
          <stop offset="100%" stopColor={dark ? '#0a0d10' : '#D5D8DD'} />
        </radialGradient>
      </defs>
      {/* device-shell octagon */}
      <path d="M28 10 L72 10 L90 28 L90 72 L72 90 L28 90 L10 72 L10 28 Z"
            fill={`url(#pg-frag-${dark ? 'd' : 'l'})`} stroke={c} strokeWidth="0.6" opacity="0.85" />
      {/* inner laminated layer */}
      <path d="M34 22 L66 22 L78 34 L78 66 L66 78 L34 78 L22 66 L22 34 Z"
            fill={innerFill} stroke={c} strokeWidth="0.4" opacity="0.5" />
      {/* starburst */}
      <path d="M50 18 L50 82 M18 50 L82 50 M28 28 L72 72 M28 72 L72 28"
            stroke={c} strokeWidth="1" strokeLinecap="round" opacity="0.85" />
      <circle cx="50" cy="50" r="3.5" fill={amber} />
      <circle cx="50" cy="50" r="6" fill="none" stroke={amber} strokeWidth="0.6" opacity="0.4" />
      {/* corner pin nodes */}
      {[[28,10],[72,10],[90,28],[90,72],[72,90],[28,90],[10,72],[10,28]].map(([x,y],i)=>
        <circle key={i} cx={x} cy={y} r="1" fill={c} opacity="0.7" />
      )}
    </svg>
  );
}

// ─── Fused panel — rounded-octagon laminated polymer ────────────────
// The asset library shows a soft rounded octagon (not sharp polygon),
// with a small offset slab beneath and a faint corner-notch detail.
function PGFusedPanel({
  children, dark = false, style = {}, accent = false,
  variant = 0, notch = true, traces = false,
}) {
  const t = dark ? PG_TOKENS.dark : PG_TOKENS.light;
  // 4 subtly different rounded-octagon clip paths
  const clips = [
    'polygon(8% 0, 92% 0, 100% 8%, 100% 92%, 92% 100%, 8% 100%, 0 92%, 0 8%)',
    'polygon(10% 0, 90% 0, 100% 10%, 100% 90%, 90% 100%, 10% 100%, 0 90%, 0 10%)',
    'polygon(6% 0, 94% 0, 100% 6%, 100% 94%, 88% 100%, 6% 100%, 0 88%, 0 12%)',
    'polygon(10% 0, 92% 2%, 100% 12%, 100% 88%, 90% 100%, 8% 100%, 0 92%, 0 10%)',
  ];
  const clip = clips[variant % clips.length];
  return (
    <div style={{
      position: 'relative',
      background: t.bgElev,
      clipPath: clip,
      WebkitClipPath: clip,
      ...style,
    }}>
      {/* inner laminated layer outline */}
      <div style={{
        position: 'absolute', inset: 1,
        clipPath: clip, WebkitClipPath: clip,
        boxShadow: dark
          ? `inset 0 0 0 1px ${t.borderSoft}, inset 0 1px 0 rgba(255,255,255,0.03)`
          : `inset 0 0 0 1px ${t.border}, inset 0 1px 0 rgba(255,255,255,0.6)`,
        pointerEvents: 'none',
      }} />
      {children}
      {/* corner-notch node detail (top-right) */}
      {notch && (
        <svg style={{ position: 'absolute', top: 6, right: 8, width: 18, height: 18,
                      pointerEvents: 'none' }}
             viewBox="0 0 18 18">
          <path d="M2 2 L9 2 L16 9" fill="none" stroke={t.traceBase} strokeWidth="0.7" />
          <circle cx="9" cy="2" r="1" fill={accent ? t.amber : t.traceBase} />
        </svg>
      )}
    </div>
  );
}

// ─── Archive slab — flatter horizontal slab with notch + status ─────
function PGSlab({ children, dark = false, style = {}, status = 'synced' }) {
  const t = dark ? PG_TOKENS.dark : PG_TOKENS.light;
  // horizontal slab with right-side notch
  const clip = 'polygon(2% 0, 100% 0, 100% 70%, 96% 100%, 0 100%, 0 12%)';
  return (
    <div style={{
      position: 'relative',
      background: t.bgElev,
      clipPath: clip,
      WebkitClipPath: clip,
      border: 'none',
      ...style,
    }}>
      <div style={{
        position: 'absolute', inset: 0,
        boxShadow: dark
          ? `inset 0 0 0 1px ${t.borderSoft}`
          : `inset 0 0 0 1px ${t.border}`,
        clipPath: clip, WebkitClipPath: clip,
        pointerEvents: 'none',
      }} />
      {children}
    </div>
  );
}

Object.assign(window, {
  PG_TOKENS,
  PGGrain, PGTraces, PGSeam, PGFlecks,
  PGMark, PGFragment, PGFusedPanel, PGSlab,
});
