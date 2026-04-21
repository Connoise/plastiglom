# Plastiglom — Design Document

> Named from *plastiglomerate*, in reference to the neuroplasticity encouraged by
> a structured practice of daily self-reflection exercises.

This is a pre-implementation design document. No code lives here yet. The goal
is to capture decisions that came out of the project-planning Q&A so that
implementation can proceed without re-litigating architecture.

---

## 1. Purpose

Plastiglom is a personal, single-user system that:

- Prompts the user to complete self-reflection exercises at scheduled times
- Archives every response (substantive or null) in a structured Obsidian vault
- Tags and organizes entries for later recollection
- Performs weekly, monthly, and ad-hoc analysis across entries using an
  evolving memory of the user
- Uses that analysis to refine the exercise pool itself, closing blind spots
  in the data it collects

The system's purpose is to help the user improve themselves in well-rounded
ways by surfacing areas they would not normally examine.

## 2. Architectural Philosophy

Plastiglom explicitly does **not** inherit Second Brian's editorial philosophy.

- Analysis is **neutral in tone but blunt in substance**. Tone never waters
  down content.
- Analysis offers **observations, questions, and recommendations**.
- **Contradictions are named as patterns**, not preserved as open ambiguity.
- The user is an emotionally mature adult with no self-harm or harm-others
  preconditions. Emotional stress in entries is signal, never a stop
  condition. Analysis never bounds topics on emotional-difficulty grounds,
  and the system never escalates outside its own scope.
- Analysis **never overwrites** entries or prior analysis. Corrections
  supersede earlier analysis via a logged correction channel.

Plastiglom is a **sibling** Obsidian vault to Second Brian. The two systems
do not act on each other's vaults, with one narrow exception:

- Plastiglom may **read** Second Brian's vault **only** during initial
  creation and ongoing maintenance of Plastiglom's own hubs and tags.
- Plastiglom's analysis functions do **not** read Second Brian.
- Tag pools are allowed to drift; no collision checking. A shared
  tag/hub registry may be introduced later.

## 3. Two Repositories, Two Locations

| Concern                  | Location                             | Visibility       |
| ------------------------ | ------------------------------------ | ---------------- |
| Code + default exercises | `plastiglom/` (public, distributable) | Public-ready     |
| User data + evolved exercises + analysis + memory | `/home/vaults/Plastiglom/` | Private, local  |
| Private versioned backup | Self-hosted git repo *inside* `/home/vaults/Plastiglom/` | Private only     |

Rationale: the user may want to distribute Plastiglom as a tool. The public
repo therefore contains only the engine and a seed set of default exercises.
The **evolved exercise pool lives in the private vault** so that Opus-edited
exercises can be maximally direct without leaking information about the
user's history through exercise text in the public repo.

Each entry **snapshots the prompt it was answering** at submission time, so
that historical prompts are always recoverable even when the source exercise
file has been edited or retired.

## 4. Repository Layout (public, distributable)

```
plastiglom/
├── apps/
│   ├── scheduler/          # decides which exercise fires when
│   ├── telegram_bot/       # sends reminder notifications
│   ├── web_app/            # Tailscale-served PWA for entry submission
│   ├── archiver/           # writes entries + daily indexes to vault
│   ├── tagger/             # Sonnet-driven tag assignment
│   ├── analyzer/           # Opus-driven weekly/monthly/ad-hoc analysis
│   ├── meta_engine/        # Opus-driven exercise pool management
│   └── memory_indexer/     # QMD integration for retrieval
├── packages/
│   ├── core/               # shared data models, schemas, validators
│   ├── llm/                # Claude API wrapper with model routing + cache
│   ├── vault/              # read/write helpers for Obsidian markdown
│   ├── tagpool/            # tag pool management primitives
│   └── config/             # env + settings loader
├── scripts/                # cron entrypoints, heartbeat tasks
├── exercises/              # default seed exercises (distributable)
├── docs/
├── tests/
├── pyproject.toml
└── README.md
```

Monorepo layout using a single `pyproject.toml` with `apps/*` and
`packages/*` as installable subpackages. Apps import from `packages/`; apps
do not import from each other (they communicate via the filesystem or
well-defined JSON on disk).

## 5. Private Vault Layout

```
/home/vaults/Plastiglom/
├── .git/                            # private self-hosted backup repo
├── entries/
│   └── YYYY/MM/DD-<exercise-slug>.md
├── daily_index/
│   └── YYYY/MM/YYYY-MM-DD.md        # auto-generated daily aggregation
├── exercises/                       # *live* evolving pool (not in public repo)
│   ├── main/
│   │   └── <exercise-id>.md
│   └── secondary/
│       └── <exercise-id>.md
├── exercise_history/
│   └── YYYY-MM-DD-<exercise-id>.md  # changelog with rationale per edit
├── memory/                          # analysis memory, one file per subject
│   ├── emotional_patterns.md
│   ├── outlook.md
│   ├── recurring_contradictions.md
│   ├── open_questions.md
│   └── ...
├── analysis/
│   ├── weekly/YYYY-WW.md
│   ├── monthly/YYYY-MM.md
│   └── queries/YYYY-MM-DD-<slug>.md
├── analysis_history/                # supersession log for corrections
│   └── YYYY-MM-DD-<slug>.md
├── tags/
│   ├── pool.md                      # active tag pool
│   └── pool_history.md              # appends only
├── hubs/
│   └── <hub-name>.md
├── queue/                           # offline drafts awaiting sync
├── .qmd_index/                      # QMD-generated local index
└── logs/
```

## 6. Data Model

### 6.1 Exercise template

One markdown file per exercise. Frontmatter plus body.

```yaml
---
id: main-evening-values-drift
title: "Values drift check"
category: main          # main | secondary
parent_id: null         # populated for secondary exercises
version: 3
status: active          # active | retired | draft
schedule:
  window: evening       # morning | evening | contextual
  weight_factors:
    recent_relevance: 0.8
    depth_potential: 0.7
    weekday_weight: 0.5
    weekend_weight: 0.9
    novelty_value: 0.6
prompts:
  - "What did you want a year ago that you no longer want?"
  - "What does that shift reveal, if anything?"
tags: [values, identity, temporal-self]
created_at: 2026-05-01T00:00:00Z
created_by: opus-4-7
updated_at: 2026-05-14T00:00:00Z
updated_by: opus-4-7
---

(instructions / notes for the exercise, optional)
```

Main exercises may contain multiple related prompts. Secondary exercises are
sub-tasks of a parent main exercise and tend toward shorter, narrower
probes — used to detect changes in feeling or response across a day.

### 6.2 Entry (one per prompt-firing event)

Filename: `YYYY/MM/DD-<exercise-slug>.md`.

```yaml
---
id: 2026-05-14-evening-values-drift
exercise_id: main-evening-values-drift
exercise_version: 3
title: "2026-05-14 - Values drift check"
timestamp_fired: 2026-05-14T21:00:00-07:00
timestamp_submitted: 2026-05-14T21:47:03-07:00
timestamp_last_edited: 2026-05-14T22:10:11-07:00
lock_at: 2026-05-15T07:30:00-07:00   # editable until next main fires
status: submitted                     # submitted | null | opened_unresponded
tags: [values, identity, uncertainty]
---

## Prompt (snapshot)

What did you want a year ago that you no longer want?
What does that shift reveal, if anything?

## Response

<free-form body>
```

Rules:

- Entries are editable until `lock_at`, which equals the firing time of the
  next main exercise.
- If no response arrives before `lock_at`, the entry is archived with
  `status: null` and the body left empty (or with the user's explicit
  `"I have no response"`-style text if they entered one).
- `opened_unresponded` is supported as a distinct status if the user opened
  the prompt but submitted nothing. This provides signal separate from
  "never opened."

### 6.3 Tag pool

A single `tags/pool.md` listing active tags, each with a short gloss and
links to representative entries. Opus adds/edits; Sonnet reads the pool
when assigning tags. No collision check against Second Brian.

### 6.4 Memory files

One markdown file per subject. Subjects are seeded by user input, and new
files are created by Opus when a durable theme emerges. Opus **appends and
reorganizes** within memory files; it never overwrites prior memory during
routine analysis. Only the correction channel (§7.6) may supersede prior
memory, and it does so via a logged entry in `analysis_history/` rather
than a silent overwrite.

### 6.5 Analysis output

Weekly, monthly, and ad-hoc queries each write a dated markdown report under
`analysis/`. Reports are immutable once written. Corrections produce a new
report that supersedes the prior one via a pointer in `analysis_history/`.

### 6.6 Exercise history

Every create / edit / retire of an exercise writes a dated note to
`exercise_history/` containing: exercise id, action, rationale (from Opus
and user refinement), diff, and the version numbers before/after.

## 7. Subsystems

### 7.1 Scheduler

- Local Python process managed by systemd timer or cron.
- Fires **two main exercises per day**: 07:30 and 21:00 local time.
- Selects next main exercise by sampling the active pool weighted by
  `weight_factors` combined with day-of-week context.
- Allows Opus-driven insertion of **up to three secondary exercises** per
  day, triggered by context rules (time-of-day windows tied to a parent
  main exercise that fired earlier that day, or Opus-flagged follow-ups).
- At each main firing, computes the new `lock_at` and finalizes any prior
  unlocked entries.

### 7.2 Telegram bot

- On firing, sends a notification message: **exercise name + full prompt
  text + deep link** to the Plastiglom web app.
- No response collection in Telegram. The chat stays a notification channel.
- Optional reminder pings at configured intervals if not yet submitted.

### 7.3 Web app (Tailscale PWA)

- Served from Benten-do over Tailscale.
- Entry screen re-displays the prompt above the response field.
- Submission writes an entry file via the archiver.
- After submission, the response remains editable until `lock_at`.
- Offline drafting: responses typed while the phone is offline are stored
  client-side (service worker + IndexedDB) and sync to the server when
  Tailscale reconnects. The archiver treats first-sync as submission.

### 7.4 Archiver

- Writes entries to the vault path scheme above.
- Snapshots the prompt text into the entry at submit time.
- Generates/updates the daily index note for the day.
- On each main firing, walks still-unlocked prior entries and finalizes
  them (null if no response, locks edits otherwise).

### 7.5 Tagger (Sonnet 4.6)

- Runs per-submission (or nightly in batch, TBD at impl time).
- Reads `tags/pool.md`.
- Assigns relevant tags; emits a `suggested_tags` list for Opus to consider
  when updating the pool.

### 7.6 Analyzer (Opus 4.7)

Cadence:

- **Weekly**: runs Sunday night, covers the past 7 days.
- **Monthly**: runs the last day of the month.
- **Ad-hoc**: user-triggered from the web app, arbitrary date range and
  granularity.

Flow:

1. Pre-analysis retrieval via QMD (§7.8): given the target window and
   optional query, pull top-K relevant entries, memory sections, and prior
   analyses.
2. Opus reads the retrieved context plus the raw entries for the window
   and produces a report.
3. Report writes to `analysis/<cadence>/...`. Memory files are
   updated (append + reorganize).
4. Opus may emit **exercise change proposals** (§7.7) and **tag pool
   additions** for user review.

Correction channel:

- User flags an analysis as wrong with a note explaining the error.
- Analyzer re-runs on the same window with the correction injected as
  context. The new report supersedes the old via a pointer in
  `analysis_history/`. Both remain on disk.

### 7.7 Meta-engine (Opus 4.7)

Responsible for the evolving exercise pool:

- Maintains enough exercises to fill a week without unintentional repeats.
  Intentional repeats are allowed when probing time-variance of responses.
- Creates new exercises, edits existing ones, retires ineffective ones.
- Assigns and updates `weight_factors`.
- Creates **secondary exercises** as sub-tasks of parent mains, used to
  probe within-day or post-reflection changes.
- Actively targets **blind spots** in collected data.

User approval flow:

1. On proposing a change, the meta-engine surfaces the proposal in the
   web app.
2. The user may **refine** the change before approving.
3. On approval, the live exercise file is updated and a note is appended
   to `exercise_history/` with the full rationale and diff.

Default stance: **never auto-apply** changes to exercises. Always propose.

### 7.8 Memory indexer (QMD)

- Uses the user's installed QMD (BM25 + vector semantic + local LLM
  re-ranking via node-llama-cpp and GGUF models).
- Re-indexes after each archive write, tag-pool update, memory edit, and
  analysis write.
- Exposed to the analyzer as a retrieval API: given a natural-language
  query (or a set of entry ids), return ranked markdown chunks from
  entries, memory files, and prior analyses.
- Integrated via subprocess to the QMD CLI (Python package `plastiglom.qmd`
  shells out; exact interface confirmed at impl time).
- Rationale: much cheaper than sending the entire vault as context to
  Opus on every analysis. Opus receives a curated, ranked retrieval plus
  the target-window entries verbatim.

## 8. LLM Routing

| Task                                         | Model            | Runs          |
| -------------------------------------------- | ---------------- | ------------- |
| Scheduling, archival, Telegram, indexing, file I/O | none (local Python) | continuously |
| Tag assignment per entry                     | Sonnet 4.6       | on submission |
| Daily index summarization                    | Sonnet 4.6       | nightly       |
| Short prompt/metadata cleanup                | Sonnet 4.6       | as needed    |
| Weekly / monthly analysis                    | Opus 4.7         | scheduled    |
| Ad-hoc analytical queries                    | Opus 4.7         | on demand    |
| Memory file creation / reorganization        | Opus 4.7         | during analysis |
| Exercise creation / editing / weight updates | Opus 4.7         | post-analysis |
| Blind-spot detection                         | Opus 4.7         | monthly      |

The `packages/llm/` wrapper enforces model routing, applies **prompt
caching** on large shared context (entry corpus snapshots, memory files,
pool), and logs cost/latency per call.

## 9. Phased Delivery

**Phase 0 — Scaffold**
- Monorepo layout, `pyproject.toml`, shared packages (`core`, `config`,
  `vault`, `llm`).
- Create `/home/vaults/Plastiglom/` and initialize the private git repo
  inside it.
- Seed a minimal set of initial exercises with user input.

**Phase 1 — MVP loop (scheduler + prompter + archiver + mobile interface)**
- Scheduler firing at 07:30 and 21:00.
- Telegram bot sending notification with prompt + deep link.
- Web app over Tailscale: view pending prompt, submit response, edit until
  `lock_at`, offline draft queue.
- Archiver writes entries with prompt snapshots; produces daily index
  notes; finalizes null/opened_unresponded entries on next main firing.
- No analysis yet; exercises selected by uniform random from the seed pool.

**Phase 2 — Tags and hubs (light organization)**
- Seed `tags/pool.md` from user input, optionally borrowing default tags
  and hubs from Second Brian as a one-time read.
- Sonnet tagger on submission.
- Hub notes scaffolded as organizing structure for tags.
- Weekly digest (Sonnet, non-memory, stats + themes) — training wheels
  before Opus analysis comes online.
- Decide concrete formats for: memory file structure, analysis report
  structure, exercise-history note structure, changelog conventions.

**Phase 3 — Memory + Opus analysis**
- Memory file seeds written with user input.
- QMD integration in `memory_indexer`, re-indexing on writes.
- Opus-driven weekly and monthly analysis writing to memory + analysis.
- Ad-hoc query interface in the web app.
- Correction channel + analysis history.

**Phase 4 — Meta-engine and evolving exercises**
- Opus pool management: create/edit/retire exercises, assign weights.
- Secondary exercise creation and context-triggered firing.
- Exercise-change approval flow in web app with user refinement.
- Blind-spot detection in monthly analysis feeding exercise generation.

## 10. Open Implementation Choices

Deferred to implementation time, not blocking this design:

- Telegram bot library: `python-telegram-bot` vs `aiogram`.
- Web app stack: FastAPI + htmx (light) vs FastAPI + a minimal React/Svelte
  SPA. htmx is the default unless offline-drafting needs push SPA.
- Offline drafting: service worker + IndexedDB vs simpler localStorage with
  manual sync.
- QMD invocation: CLI subprocess vs library binding, depending on what QMD
  exposes.
- Exact cron vs systemd timer for the scheduler.
- Private-git backup: bare repo on the same machine, or a second host over
  Tailscale.

## 11. Non-negotiables (for future Claude or human contributors)

- Analysis never overwrites entries or prior analysis. Corrections
  supersede via the logged channel in `analysis_history/`.
- Exercise changes are never auto-applied. Always propose, user refines,
  user approves, rationale is logged.
- Entries always snapshot the prompt they were answering.
- Private data never enters the public git repo. The public repo contains
  code and the distributable default exercise seed only.
- Emotional stress is signal, not a stop condition. The system does not
  escalate outside itself and does not soften analysis on emotional grounds.
- Plastiglom does not read Second Brian for analysis purposes — only for
  tag/hub maintenance.
