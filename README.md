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

# Send follow-up reminders for still-open entries (cron hourly is plenty):
python -m plastiglom.apps.scheduler --remind

# Finalize any entries whose lock_at has passed:
python -m plastiglom.apps.archiver --finalize

# Serve the web app over Tailscale (loopback-only by default):
python -m plastiglom.apps.web_app --host 127.0.0.1 --port 8001
```

The firing notification carries the full prompt, the deep link, and — when
the fired main has a connected secondary that may run later the same day — a
one-line mention that a follow-up is coming. The same follow-up note shows on
the web/mobile prompt screen.

`--remind` is a separate, idempotent heartbeat: when an entry is still
unanswered and its lock (the next main firing) is within
`PLASTIGLOM_REMINDER_WINDOW_MINUTES` (default 60), it sends one more Telegram
nudge carrying the exercise title plus a slice of the prompt. Each entry is
pinged at most once; the stamp lives on the entry as `reminder_sent_at`.

Recommended crontab entry (staggered 15 min after `llm_schedule.py`):

```cron
15 * * * *  cd '/path/to/Plastiglom' && PLASTIGLOM_VAULT_PATH=/path/to/vault \
              .venv/bin/python3 scripts/remind.py >> /path/to/vault/logs/remind.log 2>&1
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

## Operational dashboards

Three read-only reports are exposed both as CLIs and as web pages.
Everything runs against the on-disk vault; no LLM calls.

```bash
# Streak + per-exercise coverage. /stats in the web app.
plastiglom-stats summary
plastiglom-stats summary --since-days 30
plastiglom-stats summary --json

# LLM cost / token usage / cache-hit rate. /cost in the web app.
plastiglom-cost summary
plastiglom-cost summary --since-days 7
plastiglom-cost top --by task --limit 5
# Override list prices for non-default models:
PLASTIGLOM_LLM_PRICES_JSON=/path/to/prices.json plastiglom-cost summary

# Vault integrity check (linter for the markdown vault). Exits non-zero
# when an invariant is broken. Use --warnings-as-errors in CI.
plastiglom-vault check
plastiglom-vault check --json
plastiglom-vault check --warnings-as-errors
```

The cost report reads `<vault>/logs/llm_usage.jsonl`, which the router
appends to on every Anthropic call (timestamp, task, model, token counts,
cache-hit, latency). Records without a timestamp are still rolled into the
overall totals but excluded from the per-day breakdown.

The vault validator covers: malformed frontmatter, orphan entries, broken
secondary `parent_id` links, exercises sitting in the wrong category dir,
`lock_at <= timestamp_fired`, `submitted` entries with empty responses,
empty `prompt_snapshot`, duplicate filenames, and recent prompt-snapshot
drift vs. the live exercise.

## LLM job scheduler

The Sonnet digest, Opus weekly/monthly analyses, and the meta-engine
proposal pass each have a canonical cadence (see DESIGN.md §7.6 / §7.7).
`apps/llm_scheduler` turns those into cron-driven jobs while leaving every
function runnable on demand through its existing CLI.

Default cadences (local time, overridable via env):

| Job                | Schedule                          | Env override                        |
| ------------------ | --------------------------------- | ----------------------------------- |
| `digest_weekly`    | Sunday 22:00                      | `PLASTIGLOM_DIGEST_WEEKLY_AT`       |
| `analyzer_weekly`  | Sunday 22:30                      | `PLASTIGLOM_ANALYZER_WEEKLY_AT`     |
| `analyzer_monthly` | Last day of month 23:00 (also fires blind-spot proposals) | `PLASTIGLOM_ANALYZER_MONTHLY_AT` |
| `meta_blind_spots` | 15th of month 04:00 (independent proposal pass)            | `PLASTIGLOM_META_BLIND_SPOTS_AT` |

Wire it into cron once — hourly is plenty, the runner gates each job to one
fire per canonical tick via `<vault>/logs/llm_scheduler_state.json`:

```cron
0 * * * *  PLASTIGLOM_VAULT_PATH=/home/vaults/Plastiglom /path/to/scripts/llm_schedule.py
```

Off-schedule execution:

```bash
# Show the registry, last-run timestamps, and what's due:
python -m plastiglom.apps.llm_scheduler status

# Preview what the next cron tick would fire without executing:
python -m plastiglom.apps.llm_scheduler run --dry-run

# Run a single registered job right now (updates last_run_at):
python -m plastiglom.apps.llm_scheduler force digest_weekly

# Or invoke the underlying CLIs directly (does not touch scheduler state):
python -m plastiglom.apps.analyzer digest
python -m plastiglom.apps.analyzer opus weekly
python -m plastiglom.apps.analyzer opus monthly
python -m plastiglom.apps.meta_engine blind-spots
```

A failed job leaves `last_run_at` unchanged, so the next cron tick retries.

When `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are configured, every fire
(success or failure, scheduled or `force`-d) sends a one-line status to the
bot chat — e.g. `Plastiglom: weekly digest written to /vault/analysis/weekly/2026-W19-digest.md`
or `Plastiglom: digest_weekly failed — api 429`. Notifier errors are
absorbed so a flaky Telegram can't poison the job.

## Phase 4 (meta-engine)

Opus proposes exercise changes — never auto-applied. Proposals land in
`proposals/<id>.md` with status `pending` and surface in the web app at
`/proposals`, where you can approve (calls `apply_proposal` and writes a
note to `exercise_history/`) or reject with a note. Decided proposals
stay on disk for audit.

```bash
# Generate proposals from a recent analysis context (Opus):
python -c "
from plastiglom.apps.meta_engine import Generator, GeneratorInput, detect_blind_spots
# wire up settings + router + pool, then call detect_blind_spots(...)
"
```

Secondary exercises fire context-triggered (parent main must have fired
earlier today). The scheduler caps secondary firings at three per day.

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
