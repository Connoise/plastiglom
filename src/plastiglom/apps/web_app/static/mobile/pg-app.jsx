// pg-app.jsx — Plastiglom mobile app shell.
// Owns routing between screens, fetches API data, applies theme.

const TWEAKS = { substrate: 0.55 };

function useThemePref() {
  const [pref, setPref] = React.useState(() => localStorage.getItem('pg-theme') || 'auto');
  React.useEffect(() => { localStorage.setItem('pg-theme', pref); }, [pref]);
  const [systemDark, setSystemDark] = React.useState(() =>
    window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  React.useEffect(() => {
    if (!window.matchMedia) return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => setSystemDark(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  const dark = pref === 'auto' ? systemDark : pref === 'dark';
  return [pref, setPref, dark];
}

async function apiGet(path) {
  const r = await fetch(path, { credentials: 'same-origin' });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

async function apiPostJson(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `${r.status}`;
    try { msg = (await r.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return r.json();
}

function App() {
  const [route, setRoute] = React.useState({ tab: 'today', entryId: null });
  const [todayEntry, setTodayEntry] = React.useState(null);
  const [todayLoading, setTodayLoading] = React.useState(true);
  const [archive, setArchive] = React.useState([]);
  const [archiveLoading, setArchiveLoading] = React.useState(false);
  const [analysis, setAnalysis] = React.useState([]);
  const [analysisLoading, setAnalysisLoading] = React.useState(false);
  const [activeEntry, setActiveEntry] = React.useState(null);
  const [themePref, setThemePref, dark] = useThemePref();

  const theme = pgTheme(dark);

  const refreshToday = React.useCallback(async () => {
    setTodayLoading(true);
    try {
      const j = await apiGet('/api/today');
      setTodayEntry(j.entry);
    } catch (e) {
      console.error(e);
    } finally {
      setTodayLoading(false);
    }
  }, []);

  const refreshArchive = React.useCallback(async () => {
    setArchiveLoading(true);
    try {
      const j = await apiGet('/api/archive?limit=60');
      setArchive(j.entries || []);
    } catch (e) {
      console.error(e);
    } finally {
      setArchiveLoading(false);
    }
  }, []);

  const refreshAnalysis = React.useCallback(async () => {
    setAnalysisLoading(true);
    try {
      const j = await apiGet('/api/analysis');
      setAnalysis(j.groups || []);
    } catch (e) {
      console.error(e);
    } finally {
      setAnalysisLoading(false);
    }
  }, []);

  React.useEffect(() => { refreshToday(); }, [refreshToday]);
  React.useEffect(() => {
    if (route.tab === 'archive') refreshArchive();
    if (route.tab === 'analysis') refreshAnalysis();
  }, [route.tab, refreshArchive, refreshAnalysis]);

  // Load active entry when entryId changes.
  React.useEffect(() => {
    if (!route.entryId) { setActiveEntry(null); return; }
    let cancelled = false;
    (async () => {
      try {
        const j = await apiGet(`/api/entry/${route.entryId}`);
        if (!cancelled) setActiveEntry(j.entry);
      } catch (e) {
        if (!cancelled) setActiveEntry(null);
        console.error(e);
      }
    })();
    return () => { cancelled = true; };
  }, [route.entryId]);

  const onTab = (tab) => setRoute({ tab, entryId: null });
  const onOpenEntry = (id) => setRoute({ tab: 'today', entryId: id });
  const onBack = () => {
    setRoute({ tab: route.tab, entryId: null });
    refreshToday();
    if (route.tab === 'archive') refreshArchive();
  };

  const onSubmit = async (id, response) => {
    await apiPostJson(`/api/entry/${id}`, { response });
    await refreshToday();
  };

  // Apply page-level background to match theme.
  React.useEffect(() => {
    document.body.style.background = theme.bg;
    document.body.style.color = theme.text;
  }, [theme.bg, theme.text]);

  if (route.entryId) {
    return (
      <ScreenResponse
        theme={theme} t={TWEAKS}
        entry={activeEntry}
        onBack={onBack}
        onSubmit={onSubmit}
        onTab={onTab}
      />
    );
  }

  if (route.tab === 'today') {
    return (
      <ScreenPrompt
        theme={theme} t={TWEAKS}
        entry={todayEntry}
        loading={todayLoading}
        onOpen={onOpenEntry}
        onTab={onTab}
      />
    );
  }
  if (route.tab === 'archive') {
    return (
      <ScreenArchive
        theme={theme} t={TWEAKS}
        entries={archive}
        loading={archiveLoading}
        onOpen={onOpenEntry}
        onTab={onTab}
      />
    );
  }
  if (route.tab === 'analysis') {
    return (
      <ScreenAnalysis
        theme={theme} t={TWEAKS}
        groups={analysis}
        loading={analysisLoading}
        onTab={onTab}
      />
    );
  }
  if (route.tab === 'settings') {
    return (
      <ScreenSettings
        theme={theme} t={TWEAKS}
        themePref={themePref}
        onThemePref={setThemePref}
        onTab={onTab}
      />
    );
  }
  return null;
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
