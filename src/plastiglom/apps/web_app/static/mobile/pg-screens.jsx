// pg-screens.jsx — Plastiglom mobile screens, wired to live data.
// Adapted from the design canvas: design-time wrappers (DCArtboard,
// IOSDevice, TweaksPanel) are removed; screens accept data + handlers
// as props from pg-app.jsx.

// ─── Palette ─────────────────────────────────────────────────────
function pgTheme(dark) {
  if (dark) return {
    dark: true,
    bg:        '#060709',
    bgInk:     '#0E1216',
    surface:   '#161B21',
    surface2:  '#1B2128',
    surface3:  '#22272F',
    line:      '#2F363F',
    lineSoft:  'rgba(220,225,235,0.08)',
    text:      '#F3F4F6',
    textDim:   'rgba(220,225,235,0.62)',
    textFaint: 'rgba(220,225,235,0.32)',
    gold:      '#FFB23A',
    amber:     '#FFB23A',
    amberDim:  '#9A641D',
    sage:      '#9DC0A1',
    haze:      '#A8A0CC',
    chrome:    'rgba(14,18,22,0.88)',
    chromeBd:  'rgba(220,225,235,0.10)',
  };
  return {
    dark: false,
    bg:        '#F3F4F6',
    bgInk:     '#E9EAED',
    surface:   '#F8F8F6',
    surface2:  '#ECEDEB',
    surface3:  '#E6E3DE',
    line:      '#C9CDD1',
    lineSoft:  'rgba(40,46,54,0.12)',
    text:      '#15181D',
    textDim:   'rgba(21,24,29,0.64)',
    textFaint: 'rgba(21,24,29,0.36)',
    gold:      'rgba(176,122,46,0.85)',
    amber:     '#C9802C',
    amberDim:  '#B07A2E',
    sage:      '#6B8B6E',
    haze:      '#7E76A0',
    chrome:    'rgba(248,248,246,0.92)',
    chromeBd:  'rgba(40,46,54,0.10)',
  };
}

// ─── Substrate (procedural circuit-board background) ────────────
function PGSubstrate({ theme, intensity = 0.55, seed = 3 }) {
  const dark = theme.dark;
  const rng = (n) => { let s = seed * 9301 + n * 49297; s = (s % 233280) / 233280; return s; };
  const W = 402, H = 874;
  const lineColor = dark ? 'rgba(232,162,74,0.22)' : 'rgba(60,55,45,0.18)';
  const dotColor  = dark ? 'rgba(255,178,58,0.55)' : 'rgba(60,55,45,0.30)';
  const nodes = [], traces = [], hexes = [];
  for (let i = 0; i < 38; i++) {
    const x = rng(i*3) * W, y = rng(i*3+1) * H;
    const big = rng(i*3+2) > 0.85;
    nodes.push(<circle key={'n'+i} cx={x} cy={y} r={big ? 1.6 : 0.7} fill={dotColor} />);
  }
  for (let i = 0; i < 22; i++) {
    const x1 = rng(i*5) * W, y1 = rng(i*5+1) * H;
    const horizontal = rng(i*5+2) > 0.5;
    const len = 40 + rng(i*5+3) * 180;
    const x2 = horizontal ? x1 + len : x1;
    const y2 = horizontal ? y1 : y1 + len;
    const bend = rng(i*5+4) > 0.5;
    if (bend) {
      const mx = horizontal ? x2 : x1;
      const my = horizontal ? y1 : y2;
      const x3 = horizontal ? x2 : x2 + (rng(i+9) > 0.5 ? 60 : -60);
      const y3 = horizontal ? y2 + (rng(i+9) > 0.5 ? 60 : -60) : y2;
      traces.push(<path key={'t'+i}
        d={`M${x1.toFixed(1)},${y1.toFixed(1)} L${mx.toFixed(1)},${my.toFixed(1)} L${x3.toFixed(1)},${y3.toFixed(1)}`}
        stroke={lineColor} strokeWidth="0.5" fill="none" />);
    } else {
      traces.push(<line key={'t'+i} x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={lineColor} strokeWidth="0.5" />);
    }
  }
  for (let i = 0; i < 4; i++) {
    const cx = rng(i*11) * W;
    const cy = 120 + rng(i*11+1) * (H - 240);
    const r = 12 + rng(i*11+2) * 18;
    const pts = [];
    for (let k = 0; k < 6; k++) {
      const a = (Math.PI / 3) * k;
      pts.push(`${(cx + Math.cos(a)*r).toFixed(1)},${(cy + Math.sin(a)*r).toFixed(1)}`);
    }
    hexes.push(<polygon key={'h'+i} points={pts.join(' ')} fill="none" stroke={lineColor} strokeWidth="0.4" />);
  }
  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: dark
        ? 'radial-gradient(120% 80% at 30% 20%, #141B22 0%, #0A0D10 65%, #06080A 100%)'
        : 'radial-gradient(120% 80% at 30% 20%, #FAFAF8 0%, #ECEDEF 65%, #DDDFE3 100%)',
      overflow: 'hidden',
    }}>
      <svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice"
           style={{ position: 'absolute', inset: 0, opacity: intensity }}>
        {traces}{hexes}{nodes}
      </svg>
      {dark && (
        <div style={{
          position: 'absolute', inset: 0,
          background: 'radial-gradient(60px 40px at 70% 30%, rgba(255,178,58,0.18), transparent 70%),'
                    + 'radial-gradient(80px 50px at 20% 70%, rgba(255,178,58,0.10), transparent 70%),'
                    + 'radial-gradient(50px 30px at 85% 80%, rgba(255,178,58,0.14), transparent 70%)',
          pointerEvents: 'none',
        }} />
      )}
      <PGGrain dark={dark} opacity={dark ? 0.35 : 0.45} seed={seed + 1} />
    </div>
  );
}

// ─── Fused panel ────────────────────────────────────────────────
function FusedPanel({ theme, children, variant = 0, style = {}, seam = true, padded = true, notch = true }) {
  const dark = theme.dark;
  const clips = [
    'polygon(8% 0, 92% 0, 100% 8%, 100% 92%, 92% 100%, 8% 100%, 0 92%, 0 8%)',
    'polygon(10% 0, 90% 0, 100% 10%, 100% 90%, 90% 100%, 10% 100%, 0 90%, 0 10%)',
    'polygon(6% 0, 94% 0, 100% 6%, 100% 94%, 88% 100%, 6% 100%, 0 88%, 0 12%)',
    'polygon(10% 0, 92% 2%, 100% 12%, 100% 88%, 90% 100%, 8% 100%, 0 92%, 0 10%)',
    'polygon(8% 0, 92% 0, 100% 10%, 100% 90%, 92% 100%, 8% 100%, 0 90%, 0 10%)',
  ];
  const clip = clips[variant % clips.length];
  const fill = dark ? 'rgba(22,27,33,0.78)' : 'rgba(255,255,254,0.82)';
  const inner = dark
    ? '0 0 0 1px rgba(220,225,235,0.06) inset, 0 1px 0 rgba(255,255,255,0.03) inset'
    : '0 0 0 1px rgba(40,46,54,0.10) inset, 0 1px 0 rgba(255,255,255,0.7) inset';
  const seamPath = "M 8 18 C 30 24, 60 14, 96 22 S 180 38, 240 22 S 360 30, 392 18";
  return (
    <div style={{
      position: 'relative', background: fill,
      backdropFilter: 'blur(18px) saturate(140%)',
      WebkitBackdropFilter: 'blur(18px) saturate(140%)',
      clipPath: clip, WebkitClipPath: clip,
      boxShadow: inner,
      padding: padded ? '28px 24px' : 0,
      ...style,
    }}>
      {notch && (
        <svg style={{ position: 'absolute', top: 6, right: 8, width: 22, height: 22, pointerEvents: 'none' }} viewBox="0 0 22 22">
          <path d="M2 2 L11 2 L20 11" fill="none"
                stroke={dark ? 'rgba(220,225,235,0.18)' : 'rgba(40,46,54,0.18)'} strokeWidth="0.7" />
          <circle cx="11" cy="2" r="1" fill={theme.amber} opacity="0.8" />
        </svg>
      )}
      {seam && (
        <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
             preserveAspectRatio="none" viewBox="0 0 400 600">
          <path d={seamPath} fill="none" stroke={theme.gold} strokeWidth="0.8" opacity="0.55" />
        </svg>
      )}
      <div style={{ position: 'relative', zIndex: 1 }}>{children}</div>
    </div>
  );
}

function Tag({ theme, children, variant = 'default' }) {
  const dark = theme.dark;
  const bg = variant === 'amber'
    ? (dark ? 'rgba(255,178,58,0.14)' : 'rgba(201,128,44,0.12)')
    : (dark ? 'rgba(232,226,210,0.06)' : 'rgba(26,26,31,0.05)');
  const fg = variant === 'amber' ? theme.amber : theme.textDim;
  const bd = variant === 'amber'
    ? (dark ? 'rgba(255,178,58,0.30)' : 'rgba(201,128,44,0.30)')
    : theme.lineSoft;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', height: 22,
      padding: '0 9px', borderRadius: 4,
      fontFamily: 'JetBrains Mono, ui-monospace, monospace',
      fontSize: 10.5, letterSpacing: 0.4, textTransform: 'lowercase',
      background: bg, color: fg, border: `0.5px solid ${bd}`,
    }}>{children}</span>
  );
}

function PGAppBar({ theme, title, subtitle, leading, trailing, large = false }) {
  return (
    <div style={{
      position: 'relative', zIndex: 5,
      padding: large ? '54px 20px 12px' : '54px 20px 8px',
      display: 'flex', alignItems: 'flex-start', gap: 12,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        {leading || (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <PGMark size={22} dark={theme.dark} />
            <div style={{
              fontFamily: 'Fraunces, Georgia, serif',
              fontSize: large ? 26 : 22, fontWeight: 400,
              color: theme.text, letterSpacing: -0.3,
            }}>{title}</div>
          </div>
        )}
        {subtitle && (
          <div style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10.5, letterSpacing: 0.5, textTransform: 'uppercase',
            color: theme.textDim, marginTop: 6, marginLeft: 32,
          }}>{subtitle}</div>
        )}
      </div>
      {trailing}
    </div>
  );
}

function PGTabBar({ theme, active, onChange }) {
  const items = [
    { id: 'today',    label: 'Today',    Icon: IconPrompt },
    { id: 'archive',  label: 'Archive',  Icon: IconArchive },
    { id: 'analysis', label: 'Analysis', Icon: IconAnalysis },
    { id: 'settings', label: 'Settings', Icon: IconSettings },
  ];
  return (
    <div style={{
      position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 30,
      paddingBottom: 'max(16px, env(safe-area-inset-bottom))',
    }}>
      <div style={{
        margin: '0 12px',
        background: theme.chrome,
        backdropFilter: 'blur(24px) saturate(160%)',
        WebkitBackdropFilter: 'blur(24px) saturate(160%)',
        border: `0.5px solid ${theme.chromeBd}`,
        borderRadius: 18,
        padding: '10px 6px 8px',
        display: 'flex', justifyContent: 'space-around',
        boxShadow: theme.dark
          ? '0 -2px 24px rgba(0,0,0,0.5), 0 0 0 1px rgba(232,162,74,0.05) inset'
          : '0 -2px 16px rgba(0,0,0,0.06), 0 1px 0 rgba(255,255,255,0.6) inset',
      }}>
        {items.map(({ id, label, Icon }) => {
          const on = id === active;
          const c = on ? theme.amber : theme.textDim;
          return (
            <button key={id} onClick={() => onChange(id)} style={{
              position: 'relative', flex: 1,
              background: 'transparent', border: 0, padding: '6px 0 4px',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
              color: c, cursor: 'pointer',
            }}>
              {on && <div style={{
                position: 'absolute', top: -1, left: '50%', transform: 'translateX(-50%)',
                width: 22, height: 1.2, background: theme.amber, borderRadius: 1, opacity: 0.85,
              }} />}
              <div style={{ position: 'relative' }}>
                <Icon size={22} />
                {on && <div style={{
                  position: 'absolute', top: -2, right: -3,
                  width: 5, height: 5, borderRadius: 999,
                  background: theme.amber,
                  boxShadow: theme.dark ? '0 0 6px rgba(255,178,58,0.6)' : 'none',
                }} />}
              </div>
              <span style={{
                fontSize: 10, fontWeight: on ? 600 : 500, letterSpacing: 0.3,
                fontFamily: 'Inter, sans-serif',
                color: on ? theme.text : theme.textDim,
              }}>{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Helpers ────────────────────────────────────────────────────
function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' });
}
function eveningOrMorning(iso) {
  if (!iso) return '';
  const h = new Date(iso).getHours();
  return h < 12 ? 'Morning' : 'Evening';
}

// ═══ Screen 1 — Daily Exercise Prompt ═══════════════════════════
function ScreenPrompt({ theme, t, entry, loading, onOpen, onTab }) {
  return (
    <div style={{ position: 'relative', minHeight: '100vh', overflow: 'hidden' }}>
      <PGSubstrate theme={theme} intensity={t.substrate} seed={3} />

      <PGAppBar
        theme={theme}
        title="Plastiglom"
        subtitle={entry ? `Main exercise · ${eveningOrMorning(entry.timestamp_fired)}` : 'No open exercise'}
        large={true}
        trailing={
          <div style={{
            width: 38, height: 38, borderRadius: 999,
            border: `0.5px solid ${theme.lineSoft}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: theme.textDim, marginTop: 4,
            background: theme.dark ? 'rgba(20,25,32,0.5)' : 'rgba(255,255,255,0.5)',
          }}>
            <IconWaning size={18} />
          </div>
        }
      />

      <div style={{ padding: '10px 18px 0' }}>
        <FusedPanel theme={theme} variant={1} style={{ minHeight: 440, padding: '40px 28px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: 6, marginBottom: 18 }}>
            <IconStar size={22} style={{ color: theme.gold }} />
          </div>

          {loading && (
            <div style={{ textAlign: 'center', color: theme.textDim,
                          fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>
              Loading…
            </div>
          )}

          {!loading && !entry && (
            <div style={{
              textAlign: 'center', color: theme.textDim, padding: '48px 8px',
              fontFamily: 'Fraunces, Georgia, serif', fontSize: 18, lineHeight: 1.5,
            }}>
              No open prompt right now.<br/>
              <span style={{ fontSize: 14, color: theme.textFaint }}>
                The next one will fire at its scheduled time.
              </span>
            </div>
          )}

          {!loading && entry && (
            <>
              <div style={{
                fontFamily: 'Fraunces, Georgia, serif',
                fontSize: 28, fontWeight: 400, color: theme.text,
                textAlign: 'center', letterSpacing: -0.4, marginBottom: 22,
                textWrap: 'balance',
              }}>{entry.title}</div>

              {entry.prompt_snapshot.map((p, i) => (
                <div key={i} style={{
                  fontFamily: 'Fraunces, Georgia, serif',
                  fontSize: i === 0 ? 19 : 17,
                  fontWeight: 300,
                  color: i === 0 ? theme.text : theme.textDim,
                  fontStyle: i === 0 ? 'normal' : 'italic',
                  textAlign: 'center', lineHeight: 1.4,
                  textWrap: 'pretty',
                  margin: i === 0 ? '0 0 14px' : '0',
                }}>{p}</div>
              ))}

              <div style={{
                display: 'flex', justifyContent: 'center', margin: '22px 0 16px',
              }}>
                <div style={{ width: 30, height: 0.5, background: theme.gold, opacity: 0.7 }} />
              </div>

              <div style={{
                position: 'absolute', bottom: 22, left: 0, right: 0,
                display: 'flex', justifyContent: 'center', gap: 14,
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 10, letterSpacing: 0.6,
                color: theme.textFaint, textTransform: 'uppercase',
              }}>
                <span>Main</span>
                <span style={{ color: theme.gold }}>·</span>
                <span>{eveningOrMorning(entry.timestamp_fired)}</span>
                <span style={{ color: theme.gold }}>·</span>
                <span>locks {fmtTime(entry.lock_at)}</span>
              </div>
            </>
          )}
        </FusedPanel>
      </div>

      <div style={{
        margin: '24px 18px 120px',
        display: 'flex', gap: 10,
      }}>
        <button
          disabled={!entry}
          onClick={() => entry && onOpen(entry.id)}
          style={{
            flex: 1, height: 56, borderRadius: 14,
            background: theme.dark ? '#E8E2D2' : '#1A1A1F',
            color: theme.dark ? '#0A0D10' : '#F8F7F4',
            border: 0,
            fontFamily: 'Inter, sans-serif',
            fontSize: 15, fontWeight: 500, letterSpacing: 0.2,
            cursor: entry ? 'pointer' : 'not-allowed',
            opacity: entry ? 1 : 0.5,
            boxShadow: theme.dark
              ? '0 6px 18px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,178,58,0.15) inset'
              : '0 6px 18px rgba(0,0,0,0.18), 0 1px 0 rgba(255,255,255,0.15) inset',
          }}>{entry?.response ? 'Continue Exercise' : 'Open Exercise'}</button>
        <button
          onClick={() => onTab('archive')}
          style={{
            width: 56, height: 56, borderRadius: 14,
            background: theme.dark ? 'rgba(20,25,32,0.7)' : 'rgba(255,254,250,0.85)',
            border: `0.5px solid ${theme.lineSoft}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: theme.text, cursor: 'pointer',
          }}>
          <IconArchive size={22} />
        </button>
      </div>

      <PGTabBar theme={theme} active="today" onChange={onTab} />
    </div>
  );
}

// ═══ Screen 2 — Response Writing ════════════════════════════════
function ScreenResponse({ theme, t, entry, onBack, onSubmit, onTab }) {
  const [text, setText] = React.useState(entry?.response || '');
  const [savedAt, setSavedAt] = React.useState(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState(null);

  React.useEffect(() => {
    setText(entry?.response || '');
  }, [entry?.id]);

  // Local autosave to localStorage every change.
  React.useEffect(() => {
    if (!entry) return;
    const key = `pg-draft:${entry.id}`;
    if (text !== (entry.response || '')) {
      localStorage.setItem(key, text);
      setSavedAt(new Date());
    }
  }, [text, entry]);

  // Restore draft on mount.
  React.useEffect(() => {
    if (!entry) return;
    const key = `pg-draft:${entry.id}`;
    const draft = localStorage.getItem(key);
    if (draft && draft !== entry.response) setText(draft);
  }, [entry?.id]);

  const handleSubmit = async () => {
    if (!entry || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(entry.id, text);
      localStorage.removeItem(`pg-draft:${entry.id}`);
      onBack();
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (!entry) {
    return (
      <div style={{
        height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: theme.textDim, background: theme.bg,
      }}>Loading entry…</div>
    );
  }

  const locked = entry.is_locked;

  return (
    <div style={{ position: 'relative', minHeight: '100vh', overflow: 'hidden',
                  background: theme.bgInk }}>
      <PGSubstrate theme={theme} intensity={t.substrate * 0.7} seed={5} />

      <div style={{
        position: 'relative', zIndex: 5,
        padding: '54px 18px 6px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <button onClick={onBack} style={{
          width: 38, height: 38, borderRadius: 12,
          background: theme.dark ? 'rgba(20,25,32,0.6)' : 'rgba(255,255,255,0.7)',
          border: `0.5px solid ${theme.lineSoft}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: theme.text, cursor: 'pointer',
        }}>
          <IconBack size={18} />
        </button>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{
            fontFamily: 'Fraunces, Georgia, serif',
            fontSize: 17, color: theme.text, letterSpacing: -0.2,
          }}>{entry.title}</div>
          <div style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 9.5, color: theme.textDim, letterSpacing: 0.6,
            textTransform: 'uppercase', marginTop: 2,
          }}>Main · {eveningOrMorning(entry.timestamp_fired)}</div>
        </div>
        <div style={{ width: 38 }} />
      </div>

      {/* Lock-status strip */}
      <div style={{
        margin: '14px 18px 0',
        padding: '10px 14px',
        display: 'flex', alignItems: 'center', gap: 10,
        borderRadius: 12,
        background: theme.dark ? 'rgba(20,25,32,0.55)' : 'rgba(255,254,250,0.75)',
        border: `0.5px solid ${theme.lineSoft}`,
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 8,
          background: locked
            ? (theme.dark ? 'rgba(220,225,235,0.06)' : 'rgba(40,46,54,0.06)')
            : (theme.dark ? 'rgba(255,178,58,0.10)' : 'rgba(201,128,44,0.10)'),
          color: locked ? theme.textDim : theme.amber,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {locked ? <IconLocked size={15} /> : <IconUnlock size={15} />}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12.5, color: theme.text, fontWeight: 500 }}>
            {locked ? 'Locked — read only' : 'Editable until next main fire'}
          </div>
          <div style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10, color: theme.textDim, letterSpacing: 0.5,
          }}>local · {locked ? 'locked' : 'locks'} {fmtTime(entry.lock_at)}</div>
        </div>
        <div style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 13, color: locked ? theme.textDim : theme.amber, letterSpacing: 0.5,
          fontWeight: 500,
        }}>{fmtTime(entry.lock_at)}</div>
      </div>

      {/* Prompt snapshot */}
      <div style={{
        margin: '12px 18px 0',
        padding: '14px 16px',
        borderRadius: 12,
        background: theme.dark ? 'rgba(15,18,22,0.55)' : 'rgba(255,254,250,0.7)',
        border: `0.5px solid ${theme.lineSoft}`,
        fontFamily: 'Fraunces, Georgia, serif',
        fontSize: 14.5, lineHeight: 1.5, color: theme.textDim,
        fontStyle: 'italic',
      }}>
        {entry.prompt_snapshot.map((p, i) => (
          <div key={i} style={{ marginBottom: i < entry.prompt_snapshot.length - 1 ? 8 : 0 }}>{p}</div>
        ))}
      </div>

      {/* Response surface */}
      <div style={{
        margin: '12px 18px 0',
        padding: '20px 20px 16px',
        borderRadius: 16,
        background: theme.dark ? 'rgba(15,18,22,0.65)' : 'rgba(255,254,250,0.85)',
        border: `0.5px solid ${theme.lineSoft}`,
        position: 'relative',
        minHeight: 280,
      }}>
        <svg width="100%" height="14" style={{ position: 'absolute', top: 6, left: 0, opacity: 0.5 }}
             preserveAspectRatio="none" viewBox="0 0 400 14">
          <path d="M 12 8 C 60 4, 110 12, 180 7 S 320 4, 388 9"
                stroke={theme.gold} strokeWidth="0.6" fill="none" />
        </svg>

        {locked ? (
          <pre style={{
            fontFamily: 'Fraunces, Georgia, serif',
            fontSize: 16, lineHeight: 1.55, color: theme.text,
            whiteSpace: 'pre-wrap', margin: 0,
          }}>{text || '(no response)'}</pre>
        ) : (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Begin writing your response…"
            autoFocus
            style={{
              width: '100%', minHeight: 240, border: 0, background: 'transparent',
              fontFamily: 'Fraunces, Georgia, serif',
              fontSize: 16, lineHeight: 1.55, color: theme.text,
              resize: 'vertical',
            }}
          />
        )}
      </div>

      {/* Save state */}
      <div style={{
        margin: '10px 18px 0',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 10.5, color: theme.textDim, letterSpacing: 0.5,
      }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <IconCheck size={13} style={{ color: theme.sage }} />
          {savedAt ? `draft saved · ${fmtTime(savedAt.toISOString())}` : 'unsaved'}
        </span>
        <IconCloud size={14} style={{ color: theme.textFaint }} />
      </div>

      {error && (
        <div style={{
          margin: '10px 18px 0', padding: '8px 12px',
          fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
          color: theme.amber, borderRadius: 8,
          background: theme.dark ? 'rgba(255,178,58,0.08)' : 'rgba(201,128,44,0.08)',
        }}>{error}</div>
      )}

      {/* Action buttons */}
      {!locked && (
        <div style={{
          margin: '20px 18px 140px',
          display: 'flex', gap: 8,
        }}>
          <button onClick={onBack} style={{
            flex: 1, height: 44, borderRadius: 12,
            background: theme.dark ? 'rgba(20,25,32,0.8)' : 'rgba(255,254,250,0.9)',
            color: theme.text, border: `0.5px solid ${theme.lineSoft}`,
            fontSize: 13.5, fontWeight: 500, fontFamily: 'Inter, sans-serif',
            cursor: 'pointer',
          }}>Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{
              flex: 1.4, height: 44, borderRadius: 12,
              background: theme.amber,
              color: theme.dark ? '#0A0D10' : '#FFFEFA',
              border: 0,
              fontSize: 13.5, fontWeight: 600, fontFamily: 'Inter, sans-serif',
              letterSpacing: 0.2, cursor: submitting ? 'wait' : 'pointer',
              boxShadow: '0 4px 14px rgba(255,178,58,0.30)',
              opacity: submitting ? 0.7 : 1,
            }}>{submitting ? 'Submitting…' : (entry.response ? 'Update' : 'Submit')}</button>
        </div>
      )}
      {locked && (
        <div style={{ height: 140 }} />
      )}

      <PGTabBar theme={theme} active="today" onChange={onTab} />
    </div>
  );
}

// ═══ Screen 3 — Archive ═════════════════════════════════════════
function ScreenArchive({ theme, t, entries, loading, onOpen, onTab }) {
  const [active, setActive] = React.useState('All');
  const [query, setQuery] = React.useState('');
  const filters = ['All', 'Submitted', 'Open', 'Null'];

  const visible = (entries || []).filter((e) => {
    if (active === 'Submitted' && e.status !== 'submitted') return false;
    if (active === 'Open' && e.status !== 'opened_unresponded') return false;
    if (active === 'Null' && e.status !== 'null') return false;
    if (query && !e.title.toLowerCase().includes(query.toLowerCase())
        && !(e.tags || []).some((tag) => tag.toLowerCase().includes(query.toLowerCase()))) {
      return false;
    }
    return true;
  });

  return (
    <div style={{ position: 'relative', minHeight: '100vh', overflow: 'hidden' }}>
      <PGSubstrate theme={theme} intensity={t.substrate * 0.6} seed={11} />

      <PGAppBar
        theme={theme}
        leading={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <IconArchive size={22} style={{ color: theme.text }} />
            <div style={{
              fontFamily: 'Fraunces, Georgia, serif',
              fontSize: 26, fontWeight: 400, color: theme.text, letterSpacing: -0.3,
            }}>Archive</div>
          </div>
        }
      />

      <div style={{
        margin: '8px 18px 0',
        display: 'flex', alignItems: 'center', gap: 10,
        height: 42, borderRadius: 12,
        background: theme.dark ? 'rgba(20,25,32,0.6)' : 'rgba(255,254,250,0.85)',
        border: `0.5px solid ${theme.lineSoft}`,
        padding: '0 14px',
      }}>
        <IconSearch size={16} style={{ color: theme.textDim }} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search entries…"
          style={{
            flex: 1, color: theme.text, background: 'transparent', border: 0,
            fontSize: 14, fontFamily: 'Inter, sans-serif',
          }}
        />
      </div>

      <div style={{
        margin: '12px 18px 8px',
        display: 'flex', alignItems: 'center', gap: 6,
        overflowX: 'auto',
      }}>
        {filters.map((f) => {
          const on = f === active;
          return (
            <button key={f} onClick={() => setActive(f)} style={{
              height: 30, padding: '0 12px', borderRadius: 999,
              background: on
                ? (theme.dark ? '#E8E2D2' : '#1A1A1F')
                : (theme.dark ? 'rgba(20,25,32,0.5)' : 'rgba(255,254,250,0.7)'),
              color: on
                ? (theme.dark ? '#0A0D10' : '#F8F7F4')
                : theme.textDim,
              border: on ? 0 : `0.5px solid ${theme.lineSoft}`,
              fontSize: 12, fontWeight: 500, fontFamily: 'Inter, sans-serif',
              cursor: 'pointer', flexShrink: 0,
            }}>{f}</button>
          );
        })}
      </div>

      <div style={{
        padding: '4px 14px 130px',
        display: 'flex', flexDirection: 'column', gap: 10,
      }}>
        {loading && (
          <div style={{ color: theme.textDim, padding: '40px 0', textAlign: 'center',
                        fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>
            Loading…
          </div>
        )}
        {!loading && visible.length === 0 && (
          <div style={{ color: theme.textDim, padding: '40px 8px', textAlign: 'center',
                        fontFamily: 'Fraunces, Georgia, serif', fontSize: 16 }}>
            No entries match.
          </div>
        )}
        {visible.map((e) => {
          const status = e.status === 'submitted' ? 'synced'
            : e.status === 'opened_unresponded' ? 'opened'
            : e.status === 'null' ? 'null' : 'local';
          const statusColor = status === 'synced' ? theme.sage
            : status === 'local' ? theme.amber : theme.textDim;
          const slabClip = 'polygon(2% 0, 100% 0, 100% 70%, 96% 100%, 0 100%, 0 14%)';
          return (
            <div key={e.id}
                 onClick={() => onOpen(e.id)}
                 style={{
              position: 'relative',
              background: theme.dark ? 'rgba(22,27,33,0.78)' : 'rgba(255,255,254,0.85)',
              clipPath: slabClip, WebkitClipPath: slabClip,
              padding: '12px 18px 12px 16px', cursor: 'pointer',
            }}>
              <div style={{
                position: 'absolute', inset: 0,
                clipPath: slabClip, WebkitClipPath: slabClip,
                boxShadow: theme.dark
                  ? '0 0 0 1px rgba(220,225,235,0.06) inset'
                  : '0 0 0 1px rgba(40,46,54,0.10) inset',
                pointerEvents: 'none',
              }} />
              <svg style={{ position: 'absolute', left: 8, top: 6, width: 28, height: 4,
                            pointerEvents: 'none', opacity: 0.5 }} viewBox="0 0 28 4">
                <path d="M0 2 L8 2 L10 0 L20 0 L22 2 L28 2"
                      stroke={theme.dark ? 'rgba(220,225,235,0.20)' : 'rgba(40,46,54,0.22)'}
                      strokeWidth="0.6" fill="none" />
              </svg>
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 9.5, letterSpacing: 0.6, textTransform: 'uppercase',
                color: theme.textDim, marginBottom: 6,
              }}>
                <span>{fmtDate(e.timestamp_fired)} · {fmtTime(e.timestamp_fired)}</span>
                <span style={{
                  color: statusColor,
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                }}>
                  <StatusNode kind={status} size={10} color={statusColor} />
                  {e.status}
                </span>
              </div>
              <div style={{
                fontFamily: 'Fraunces, Georgia, serif',
                fontSize: 17, color: theme.text, marginBottom: 8, letterSpacing: -0.2,
              }}>{e.title}</div>
              {e.tags && e.tags.length > 0 && (
                <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                  {e.tags.slice(0, 4).map((tag) => <Tag key={tag} theme={theme}>{tag}</Tag>)}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <PGTabBar theme={theme} active="archive" onChange={onTab} />
    </div>
  );
}

// ═══ Screen 4 — Analysis ════════════════════════════════════════
function ScreenAnalysis({ theme, t, groups, loading, onTab }) {
  const cadences = (groups || []).map((g) => g.cadence);
  const [tab, setTab] = React.useState(cadences[0] || 'weekly');
  React.useEffect(() => {
    if (cadences.length && !cadences.includes(tab)) setTab(cadences[0]);
  }, [cadences.join('|')]);

  const active = (groups || []).find((g) => g.cadence === tab);

  return (
    <div style={{ position: 'relative', minHeight: '100vh', overflow: 'hidden' }}>
      <PGSubstrate theme={theme} intensity={t.substrate * 0.65} seed={9} />

      <PGAppBar
        theme={theme}
        leading={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <IconAnalysis size={22} style={{ color: theme.text }} />
            <div style={{
              fontFamily: 'Fraunces, Georgia, serif',
              fontSize: 26, fontWeight: 400, color: theme.text, letterSpacing: -0.3,
            }}>Analysis</div>
          </div>
        }
      />

      {cadences.length > 0 && (
        <div style={{ margin: '6px 18px 0' }}>
          <div style={{
            display: 'flex', padding: 3, borderRadius: 12,
            background: theme.dark ? 'rgba(20,25,32,0.6)' : 'rgba(220,217,211,0.55)',
            border: `0.5px solid ${theme.lineSoft}`,
          }}>
            {cadences.map((tb) => {
              const on = tb === tab;
              return (
                <button key={tb} onClick={() => setTab(tb)} style={{
                  flex: 1, height: 32, borderRadius: 9,
                  background: on ? theme.amber : 'transparent',
                  color: on ? (theme.dark ? '#0A0D10' : '#FFFEFA') : theme.textDim,
                  border: 0,
                  fontSize: 12.5, fontWeight: 600, fontFamily: 'Inter, sans-serif',
                  letterSpacing: 0.2, cursor: 'pointer',
                  boxShadow: on ? '0 2px 8px rgba(255,178,58,0.30)' : 'none',
                  textTransform: 'capitalize',
                }}>{tb}</button>
              );
            })}
          </div>
        </div>
      )}

      <div style={{
        padding: '14px 18px 130px',
        display: 'flex', flexDirection: 'column', gap: 10,
      }}>
        {loading && (
          <div style={{ color: theme.textDim, padding: '40px 0', textAlign: 'center',
                        fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>
            Loading…
          </div>
        )}
        {!loading && (!active || active.items.length === 0) && (
          <div style={{
            color: theme.textDim, padding: '40px 8px', textAlign: 'center',
            fontFamily: 'Fraunces, Georgia, serif', fontSize: 16,
          }}>
            No analysis reports yet.
          </div>
        )}
        {active && active.items.map((item) => (
          <a key={item.relative_path}
             href={`/analysis/view?path=${encodeURIComponent(item.relative_path)}`}
             style={{
               display: 'block', textDecoration: 'none',
               padding: '14px 16px', borderRadius: 12,
               background: theme.dark ? 'rgba(22,27,33,0.78)' : 'rgba(255,255,254,0.85)',
               border: `0.5px solid ${theme.lineSoft}`,
               color: theme.text,
             }}>
            <div style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 9.5, letterSpacing: 1, textTransform: 'uppercase',
              color: theme.textDim, marginBottom: 4,
            }}>{tab}{item.has_correction ? ' · correction' : ''}</div>
            <div style={{
              fontFamily: 'Fraunces, Georgia, serif',
              fontSize: 16, color: theme.text, letterSpacing: -0.2,
            }}>{item.title}</div>
          </a>
        ))}
      </div>

      <PGTabBar theme={theme} active="analysis" onChange={onTab} />
    </div>
  );
}

// ═══ Screen 5 — Settings ════════════════════════════════════════
function ScreenSettings({ theme, t, themePref, onThemePref, onTab }) {
  const [notif, setNotif] = React.useState(true);

  return (
    <div style={{ position: 'relative', minHeight: '100vh', overflow: 'hidden' }}>
      <PGSubstrate theme={theme} intensity={t.substrate * 0.6} seed={7} />

      <PGAppBar
        theme={theme}
        leading={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <IconSettings size={22} style={{ color: theme.text }} />
            <div style={{
              fontFamily: 'Fraunces, Georgia, serif',
              fontSize: 26, fontWeight: 400, color: theme.text, letterSpacing: -0.3,
            }}>Settings</div>
          </div>
        }
      />

      <div style={{ padding: '8px 18px 130px', display: 'flex', flexDirection: 'column', gap: 18 }}>

        <SettingsGroup theme={theme} label="Appearance">
          <SettingsRow theme={theme} label="Theme"
                       trailing={
                         <select
                           value={themePref}
                           onChange={(e) => onThemePref(e.target.value)}
                           style={{
                             background: theme.dark ? 'rgba(20,25,32,0.7)' : 'rgba(255,254,250,0.9)',
                             color: theme.text, border: `0.5px solid ${theme.lineSoft}`,
                             borderRadius: 8, padding: '4px 8px',
                             fontFamily: 'JetBrains Mono, monospace', fontSize: 12,
                           }}>
                           <option value="auto">Auto</option>
                           <option value="light">Light</option>
                           <option value="dark">Dark</option>
                         </select>
                       } />
        </SettingsGroup>

        <SettingsGroup theme={theme} label="Main exercise time">
          <SettingsRow theme={theme} icon={<IconSun size={18} style={{color: theme.amber}} />}
                       label="Morning" detail="07:30" />
          <SettingsRow theme={theme} icon={<IconMoon size={18} style={{color: theme.textDim}} />}
                       label="Evening" detail="21:00" />
        </SettingsGroup>

        <SettingsGroup theme={theme} label="Reminders">
          <SettingsRow theme={theme} icon={<IconBell size={18} style={{color: theme.textDim}} />}
                       label="Reminder before main" detail="15 min before" />
          <SettingsRow theme={theme} label="Missed reminder follow-up" detail="2 hours later" />
          <SettingsRow theme={theme} label="Enable notifications"
                       trailing={<Toggle theme={theme} value={notif} onChange={setNotif} />} />
        </SettingsGroup>

        <FusedPanel theme={theme} variant={4} style={{ padding: '14px 16px' }} seam={false}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: theme.dark ? 'rgba(255,178,58,0.10)' : 'rgba(201,128,44,0.10)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: theme.amber,
            }}><IconLock size={17} /></div>
            <div style={{ flex: 1 }}>
              <div style={{
                fontSize: 13, fontWeight: 600, color: theme.text,
                fontFamily: 'Inter, sans-serif',
              }}>Private vault · Local-first</div>
              <div style={{
                fontSize: 11, color: theme.textDim, marginTop: 2,
                fontFamily: 'Inter, sans-serif',
              }}>Your data stays on this device.</div>
            </div>
          </div>
        </FusedPanel>

        <div style={{
          marginTop: 4, padding: '0 4px',
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 10, lineHeight: 1.7, color: theme.textFaint, letterSpacing: 0.3,
        }}>
          <div>· main exercise fires at set times</div>
          <div>· response editable until next main fire</div>
          <div>· all data is private and stored locally</div>
          <div>· analysis is generated on-device</div>
          <div>· telegram used only for notifications</div>
        </div>
      </div>

      <PGTabBar theme={theme} active="settings" onChange={onTab} />
    </div>
  );
}

function SettingsGroup({ theme, label, children }) {
  return (
    <div>
      <div style={{
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 9.5, letterSpacing: 1, textTransform: 'uppercase',
        color: theme.textDim, marginBottom: 8, marginLeft: 4,
      }}>{label}</div>
      <div style={{
        background: theme.dark ? 'rgba(20,25,32,0.6)' : 'rgba(255,254,250,0.85)',
        border: `0.5px solid ${theme.lineSoft}`,
        borderRadius: 14, overflow: 'hidden',
      }}>{children}</div>
    </div>
  );
}

function SettingsRow({ theme, icon, label, detail, trailing }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 14px', minHeight: 46,
      borderBottom: `0.5px solid ${theme.lineSoft}`,
    }}>
      {icon && (
        <div style={{
          width: 28, height: 28, borderRadius: 7,
          background: theme.dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>{icon}</div>
      )}
      <div style={{
        flex: 1, fontSize: 13.5, color: theme.text,
        fontFamily: 'Inter, sans-serif',
      }}>{label}</div>
      {detail && (
        <div style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 12, color: theme.textDim, letterSpacing: 0.3,
        }}>{detail}</div>
      )}
      {trailing}
    </div>
  );
}

function Toggle({ theme, value, onChange }) {
  return (
    <button onClick={() => onChange(!value)} style={{
      position: 'relative', width: 38, height: 22, borderRadius: 999,
      background: value ? theme.amber : (theme.dark ? '#2A313B' : '#C8C5BE'),
      border: 0, padding: 0, cursor: 'pointer', transition: 'background 0.18s',
    }}>
      <div style={{
        position: 'absolute', top: 2, left: value ? 18 : 2,
        width: 18, height: 18, borderRadius: 999,
        background: '#FFFEFA',
        boxShadow: '0 1px 2px rgba(0,0,0,0.25)',
        transition: 'left 0.18s',
      }} />
    </button>
  );
}

Object.assign(window, {
  pgTheme, PGSubstrate, FusedPanel, PGAppBar, PGTabBar, Tag,
  ScreenPrompt, ScreenResponse, ScreenArchive, ScreenAnalysis, ScreenSettings,
});
