# Plastiglom

A personal, single-user system that prompts daily self-reflection exercises,
archives every response in an Obsidian vault, and uses an evolving memory to
run weekly / monthly / ad-hoc analysis across entries.

See `DESIGN.md` for architecture and decision history. This README covers
repository layout and how to run the Phase 1 pieces.

## Layout

```
plastiglom/
├── src/plastiglom/
│   ├── apps/
│   │   ├── scheduler/          # picks next main, computes lock_at
│   │   ├── archiver/           # writes entries, finalizes on next fire
│   │   ├── telegram_bot/       # notification formatter + (future) send
│   │   ├── web_app/            # Tailscale PWA (Phase 1)
│   │   ├── tagger/             # Sonnet 4.6 tagger
│   │   ├── analyzer/           # Opus 4.7 weekly/monthly/ad-hoc
│   │   ├── meta_engine/        # Opus 4.7 exercise pool manager
│   │   └── memory_indexer/     # QMD retrieval wrapper
│   └── packages/
│       ├── core/               # pydantic models (Exercise, Entry, TagPool)
│       ├── config/             # env/settings loader
│       ├── vault/              # frontmatter read/write + vault paths
│       ├── llm/                # Claude API router with cache blocks
│       └── tagpool/            # pool io + merge logic
├── scripts/                    # cron/systemd entrypoints
├── exercises/                  # seed (distributable) exercise templates
├── tests/
├── DESIGN.md
└── pyproject.toml
```

The **evolved** exercise pool and all user data live in the private vault at
`PLASTIGLOM_VAULT_PATH` (default: `/home/vaults/Plastiglom`). `exercises/` in
this repo is the seed distribution only.

## Install (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional extras: `.[telegram]`, `.[web]`.

## Configure

Copy `.env.example` to `.env` and fill in:

- `PLASTIGLOM_VAULT_PATH` — absolute path to your private vault.
- `PLASTIGLOM_TIMEZONE` — IANA tz (e.g. `Pacific/Honolulu`).
- `PLASTIGLOM_MORNING_FIRE` / `PLASTIGLOM_EVENING_FIRE` — 24h wall-clock times.
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — notification channel.
- `ANTHROPIC_API_KEY` — required for tagger / analyzer / meta-engine.

Initialize the vault once by copying `exercises/` into `$PLASTIGLOM_VAULT_PATH/exercises/`
and initializing a private git repo inside the vault.

## Phase 1 run

```bash
# Fire the next main exercise (cron at 07:30 and 21:00 local):
python -m plastiglom.apps.scheduler

# Finalize any entries whose lock_at has passed:
python -m plastiglom.apps.archiver --finalize

# Serve the web app over Tailscale (loopback-only by default):
python -m plastiglom.apps.web_app --host 127.0.0.1 --port 8001
```

## Phase 2

```bash
# Seed tag pool + hubs from YAML (merge by default; --replace to start fresh):
python -m plastiglom.apps.seeder seed-tagpool path/to/seed.yaml
# An example seed lives at exercises/seed_tagpool.example.yaml.

# Sonnet weekly digest — stats + themes, no memory writes:
python -m plastiglom.apps.analyzer digest            # with Sonnet themes
python -m plastiglom.apps.analyzer digest --no-themes  # stats only

# Per-entry tagging (Sonnet):
python -m plastiglom.apps.tagger <entry-path>
```

## Phase 3 (Opus analysis + memory)

```bash
# Seed memory file subjects from YAML (re-runs append rather than overwrite):
python -m plastiglom.apps.seeder seed-memory path/to/memory.yaml
# An example seed lives at exercises/seed_memory.example.yaml.

# Opus analysis — writes to analysis/<cadence>/ + appends to memory/:
python -m plastiglom.apps.analyzer opus weekly
python -m plastiglom.apps.analyzer opus monthly
python -m plastiglom.apps.analyzer opus adhoc --query "your question"
```

The web app at `/analysis` lists every report and lets you flag any of them
as wrong. Submitting a correction note re-runs the analyzer; the corrected
report lands next to the prior one with a `-corrected-<unix-ts>` suffix and
a pointer is written to `analysis_history/`. The prior report is never
overwritten.

QMD reindexing fires automatically after every entry write or daily-index
update once `PLASTIGLOM_QMD_BIN` resolves; failures are swallowed so a
flaky indexer can't break archival.

## Testing

```bash
pytest
```

## Non-negotiables

(from `DESIGN.md §11`; carry these forward in any refactor):

- Analysis never overwrites entries or prior analysis. Corrections supersede
  via a logged channel in `analysis_history/`.
- Exercise changes are never auto-applied. Always propose; user refines; user
  approves; rationale is logged.
- Entries always snapshot the prompt they were answering.
- Private data never enters this public repo.
- Emotional stress is signal, not a stop condition.
- Plastiglom does not read Second Brian for analysis purposes — only for
  tag/hub maintenance.
