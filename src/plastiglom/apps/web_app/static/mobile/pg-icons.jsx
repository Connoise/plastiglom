// pg-icons.jsx — Plastiglom icon library
// Updated to match the asset library spec:
//  Today = starburst, Archive = stacked slabs, Analysis = signal trace,
//  Settings = hex-nut, Morning = small radial, Evening = crescent,
//  plus all status iconography (local/synced/null/opened/locked/queued).

function _IconBase({ size = 22, children, viewBox = '0 0 24 24', stroke = 1.3, style = {}, fill = 'none' }) {
  return (
    <svg width={size} height={size} viewBox={viewBox}
      fill={fill} stroke="currentColor" strokeWidth={stroke}
      strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, ...style }}>
      {children}
    </svg>
  );
}

// ── App-mark / brand glyph ──────────────────────────────────
// 8-point starburst with a subtle inner ring — used in the prompt card
// and as the "Today" tab icon.
const IconStar = (p) => (
  <_IconBase {...p} stroke={p.stroke || 1.1}>
    <path d="M12 3 L12 21 M3 12 L21 12 M5.6 5.6 L18.4 18.4 M5.6 18.4 L18.4 5.6" />
    <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
  </_IconBase>
);

// ── Tab-bar icons ───────────────────────────────────────────
const IconPrompt = IconStar; // Today = starburst

const IconArchive = (p) => (
  <_IconBase {...p}>
    {/* stacked translucent slabs */}
    <rect x="3.5" y="6"  width="17" height="4" rx="1.2" />
    <rect x="3.5" y="11" width="17" height="4" rx="1.2" opacity="0.7" />
    <rect x="3.5" y="16" width="17" height="4" rx="1.2" opacity="0.45" />
  </_IconBase>
);

const IconAnalysis = (p) => (
  <_IconBase {...p}>
    {/* signal trace with a peak node */}
    <path d="M3 17 L7 17 L9 13 L12 15 L15 9 L17 11 L21 11" />
    <circle cx="15" cy="9" r="1.2" fill="currentColor" stroke="none" />
  </_IconBase>
);

const IconSettings = (p) => (
  <_IconBase {...p}>
    {/* hex-nut */}
    <path d="M12 3.2 L19 7.2 L19 14.8 L12 18.8 L5 14.8 L5 7.2 Z" />
    <circle cx="12" cy="11" r="2.6" />
  </_IconBase>
);

// ── Time-of-day ─────────────────────────────────────────────
const IconMorning = (p) => (
  <_IconBase {...p}>
    {/* restrained sunburst */}
    <circle cx="12" cy="13" r="3.2" />
    <path d="M12 5 L12 7 M5.5 13 L7.5 13 M16.5 13 L18.5 13 M7 8 L8.4 9.4 M17 8 L15.6 9.4" />
    <path d="M3 19 L21 19" opacity="0.5" />
  </_IconBase>
);

const IconEvening = (p) => (
  <_IconBase {...p}>
    {/* crescent + small dot */}
    <path d="M16.5 4.5 C12 6, 9 9, 9 13 C9 16.5, 11 19, 14.5 19.5 C12 19, 7 17, 6 12 C5 7.5, 9.5 4, 16.5 4.5 Z"
          fill="currentColor" stroke="none" />
    <circle cx="18" cy="9" r="0.7" fill="currentColor" stroke="none" opacity="0.5" />
  </_IconBase>
);

const IconSun = IconMorning;
const IconMoon = IconEvening;

// ── Status icons ────────────────────────────────────────────

// Saved locally — small shield with internal node
const IconSavedLocal = (p) => (
  <_IconBase {...p}>
    <path d="M12 4 L19 6 L19 12 C19 16, 16 19, 12 20 C8 19, 5 16, 5 12 L5 6 Z" />
    <path d="M9 12 L11 14 L15 10" stroke="currentColor" strokeWidth="1.6" />
  </_IconBase>
);
const IconSaved = IconSavedLocal;

// Synced — small cloud with node
const IconSynced = (p) => (
  <_IconBase {...p}>
    <path d="M7 17 C5 17, 4 16, 4 14 C4 12, 5.5 11, 7 11 C7 9, 9 7, 12 7 C15 7, 17 9, 17 12 C19 12, 20 13, 20 15 C20 17, 19 17, 17 17 Z" />
    <path d="M9 14 L11 16 L15 12" />
  </_IconBase>
);
const IconCloud = (p) => (
  <_IconBase {...p}>
    <path d="M7 17 C5 17, 4 16, 4 14 C4 12, 5.5 11, 7 11 C7 9, 9 7, 12 7 C15 7, 17 9, 17 12 C19 12, 20 13, 20 15 C20 17, 19 17, 17 17 Z" />
  </_IconBase>
);

// Queued — clock face with empty arms
const IconQueued = (p) => (
  <_IconBase {...p}>
    <circle cx="12" cy="12" r="7.5" />
    <path d="M12 8 L12 12 L15 14" />
  </_IconBase>
);

// Locked — lock with status dot inside
const IconLocked = (p) => (
  <_IconBase {...p}>
    <rect x="5.5" y="11" width="13" height="9" rx="1.4" />
    <path d="M8 11 L8 8 C8 5.5, 10 4, 12 4 C14 4, 16 5.5, 16 8 L16 11" />
    <circle cx="12" cy="15.5" r="1" fill="currentColor" stroke="none" />
  </_IconBase>
);
const IconLock = IconLocked;

// Editable — pencil with seam mark
const IconEditable = (p) => (
  <_IconBase {...p}>
    <path d="M4 20 L4 16 L16 4 L20 8 L8 20 Z" />
    <path d="M14 6 L18 10" />
  </_IconBase>
);
const IconEdit = IconEditable;

// Null — hollow unlit node
const IconNull = (p) => (
  <_IconBase {...p}>
    <circle cx="12" cy="12" r="7.5" />
    <circle cx="12" cy="12" r="1.4" opacity="0.35" />
  </_IconBase>
);

// Opened-unresponded — broken-ring node
const IconOpenedUnresponded = (p) => (
  <_IconBase {...p}>
    <path d="M5 12 A 7 7 0 0 1 19 12" />
    <path d="M19 12 A 7 7 0 0 1 14.5 18.5" />
    <path d="M9 19 A 7 7 0 0 1 5 14" opacity="0.55" />
    <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
  </_IconBase>
);
const IconWaning = IconOpenedUnresponded;

// Private vault — enclosed cube
const IconPrivateVault = (p) => (
  <_IconBase {...p}>
    <path d="M5 8 L12 4 L19 8 L19 16 L12 20 L5 16 Z" />
    <path d="M5 8 L12 12 L19 8 M12 12 L12 20" opacity="0.45" />
    <circle cx="12" cy="14" r="0.9" fill="currentColor" stroke="none" />
  </_IconBase>
);

// Telegram notification — minimal paper plane
const IconTelegram = (p) => (
  <_IconBase {...p}>
    <path d="M21 4 L3 11 L10 13 L13 20 Z" />
    <path d="M10 13 L21 4" opacity="0.5" />
  </_IconBase>
);

// Search — magnifier
const IconSearch = (p) => (
  <_IconBase {...p}>
    <circle cx="11" cy="11" r="6" />
    <path d="M15.5 15.5 L20 20" />
  </_IconBase>
);

// Filter — sliders
const IconFilter = (p) => (
  <_IconBase {...p}>
    <path d="M5 7 L19 7 M5 12 L19 12 M5 17 L19 17" />
    <circle cx="9" cy="7" r="1.5" fill="currentColor" />
    <circle cx="15" cy="12" r="1.5" fill="currentColor" />
    <circle cx="11" cy="17" r="1.5" fill="currentColor" />
  </_IconBase>
);

const IconBack = (p) => <_IconBase {...p}><path d="M15 5 L8 12 L15 19" /></_IconBase>;
const IconChevron = (p) => <_IconBase {...p}><path d="M9 6 L15 12 L9 18" /></_IconBase>;
const IconChevronLeft = (p) => <_IconBase {...p}><path d="M15 6 L9 12 L15 18" /></_IconBase>;
const IconMore = (p) => (
  <_IconBase {...p}>
    <circle cx="6" cy="12" r="1.3" fill="currentColor" />
    <circle cx="12" cy="12" r="1.3" fill="currentColor" />
    <circle cx="18" cy="12" r="1.3" fill="currentColor" />
  </_IconBase>
);
const IconAdd = (p) => <_IconBase {...p}><path d="M12 5 L12 19 M5 12 L19 12" /></_IconBase>;
const IconCheck = (p) => <_IconBase {...p}><path d="M5 12 L10 17 L19 7" /></_IconBase>;
const IconBell = (p) => (
  <_IconBase {...p}>
    <path d="M6 16 L18 16 L17 14 C16 13, 16 11, 16 9 C16 6, 14 4, 12 4 C10 4, 8 6, 8 9 C8 11, 8 13, 7 14 Z" />
    <path d="M10 19 C10.5 20, 11.2 20.5, 12 20.5 C12.8 20.5, 13.5 20, 14 19" />
  </_IconBase>
);
const IconTag = (p) => (
  <_IconBase {...p}>
    <path d="M4 12 L4 4 L12 4 L20 12 L12 20 Z" />
    <circle cx="8" cy="8" r="1.2" fill="currentColor" />
  </_IconBase>
);
const IconPaperclip = (p) => (
  <_IconBase {...p}>
    <path d="M17 9 L10 16 C9 17, 7 17, 6 16 C5 15, 5 13, 6 12 L13 5 C14.5 3.5, 16.5 3.5, 18 5 C19.5 6.5, 19.5 8.5, 18 10 L11 17" />
  </_IconBase>
);
const IconSync = (p) => (
  <_IconBase {...p}>
    <path d="M5 12 C5 8, 8 5, 12 5 C15 5, 17 7, 18 9 L20 7" />
    <path d="M19 12 C19 16, 16 19, 12 19 C9 19, 7 17, 6 15 L4 17" />
  </_IconBase>
);
const IconUnlock = (p) => (
  <_IconBase {...p}>
    <rect x="5" y="11" width="14" height="9" rx="1.5" />
    <path d="M8 11 L8 8 C8 5.5, 10 4, 12 4 C13.5 4, 14.8 4.7, 15.5 6" />
    <circle cx="12" cy="15" r="1" fill="currentColor" />
  </_IconBase>
);

// ── Status node — small SVG (used inline in archive cards & chips) ──
function StatusNode({ kind = 'synced', size = 12, color = 'currentColor' }) {
  const s = size, r = s / 2;
  if (kind === 'synced') return (
    <svg width={s} height={s} viewBox="0 0 12 12" style={{ flexShrink: 0 }}>
      <circle cx="6" cy="6" r="5" fill={color} />
      <path d="M3.6 6.2 L5.2 7.8 L8.6 4.4" stroke="#fff" strokeWidth="1.3" fill="none"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
  if (kind === 'local') return (
    <svg width={s} height={s} viewBox="0 0 12 12" style={{ flexShrink: 0 }}>
      <circle cx="6" cy="6" r="4.5" fill="none" stroke={color} strokeWidth="1.1" />
      <circle cx="6" cy="6" r="1.6" fill={color} />
    </svg>
  );
  if (kind === 'queued') return (
    <svg width={s} height={s} viewBox="0 0 12 12" style={{ flexShrink: 0 }}>
      <circle cx="6" cy="6" r="4.5" fill="none" stroke={color} strokeWidth="1.1"
              strokeDasharray="1.5 1.5" />
      <circle cx="6" cy="6" r="1.4" fill={color} opacity="0.6" />
    </svg>
  );
  if (kind === 'null') return (
    <svg width={s} height={s} viewBox="0 0 12 12" style={{ flexShrink: 0 }}>
      <circle cx="6" cy="6" r="4.5" fill="none" stroke={color} strokeWidth="1.1" opacity="0.55" />
    </svg>
  );
  if (kind === 'opened') return (
    <svg width={s} height={s} viewBox="0 0 12 12" style={{ flexShrink: 0 }}>
      <path d="M1.5 6 A 4.5 4.5 0 0 1 10.5 6" fill="none" stroke={color} strokeWidth="1.2" strokeLinecap="round" />
      <path d="M10.5 6 A 4.5 4.5 0 0 1 7.5 10.2" fill="none" stroke={color} strokeWidth="1.2" strokeLinecap="round" />
      <path d="M4 10.4 A 4.5 4.5 0 0 1 2 7.5" fill="none" stroke={color} strokeWidth="1.2" strokeLinecap="round" opacity="0.5" />
      <circle cx="6" cy="6" r="1.4" fill={color} />
    </svg>
  );
  if (kind === 'locked') return (
    <svg width={s} height={s} viewBox="0 0 12 12" style={{ flexShrink: 0 }}>
      <rect x="2.5" y="5" width="7" height="5" rx="0.8" fill="none" stroke={color} strokeWidth="1.1" />
      <path d="M3.8 5 L3.8 4 C3.8 2.6, 4.8 2, 6 2 C7.2 2, 8.2 2.6, 8.2 4 L8.2 5" fill="none" stroke={color} strokeWidth="1.1" />
      <circle cx="6" cy="7.5" r="0.7" fill={color} />
    </svg>
  );
  // active dot
  return (
    <svg width={s} height={s} viewBox="0 0 12 12" style={{ flexShrink: 0 }}>
      <circle cx="6" cy="6" r="3.5" fill={color} />
      <circle cx="6" cy="6" r="5.5" fill="none" stroke={color} strokeWidth="0.6" opacity="0.4" />
    </svg>
  );
}

Object.assign(window, {
  IconPrompt, IconArchive, IconAnalysis, IconSettings,
  IconMorning, IconEvening, IconSun, IconMoon,
  IconSaved, IconSavedLocal, IconSynced, IconQueued,
  IconLocked, IconLock, IconUnlock, IconEditable, IconEdit,
  IconNull, IconOpenedUnresponded, IconWaning,
  IconPrivateVault, IconTelegram,
  IconSearch, IconFilter, IconBack, IconChevron, IconChevronLeft,
  IconMore, IconAdd, IconCheck, IconBell, IconTag, IconPaperclip, IconSync,
  IconStar, IconCloud,
  StatusNode,
});
