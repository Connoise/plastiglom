"""Jinja2 templates kept in-process via DictLoader.

Inlined here to avoid package-data wiring. Swap to a directory loader later
when templates grow past the point a single file is ergonomic.
"""

from __future__ import annotations

from jinja2 import DictLoader, Environment, select_autoescape

_BASE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title or 'Plastiglom' }}</title>
<script src="https://unpkg.com/htmx.org@1.9.12" defer></script>
<style>
  body { font-family: system-ui, sans-serif; max-width: 38rem; margin: 2rem auto; padding: 0 1rem;
         color: #1a1a1a; line-height: 1.5; }
  h1 { font-size: 1.15rem; margin-bottom: 0.25rem; }
  h2 { font-size: 1.0rem; margin-top: 1.5rem; }
  blockquote { margin: 0.5rem 0; padding: 0.5rem 0.75rem; background: #f4f4f4;
               border-left: 3px solid #888; }
  textarea { width: 100%; min-height: 12rem; font: inherit; padding: 0.5rem; box-sizing: border-box; }
  .meta { color: #666; font-size: 0.85rem; }
  .locked { color: #a00; }
  .nav a { margin-right: 0.75rem; }
  form button { margin-top: 0.5rem; padding: 0.5rem 1rem; }
</style>
</head>
<body>
<nav class="nav">
<a href="/">Today</a>
<a href="/day/{{ today.isoformat() }}">Index</a>
<a href="/analysis">Analysis</a>
<a href="/proposals">Proposals</a>
<a href="/mobile">Mobile</a>
</nav>
<main>
{% block content %}{% endblock %}
</main>
</body>
</html>
"""

_HOME = """\
{% extends '_base.html' %}
{% block content %}
{% if entry %}
<h1>{{ entry.title }}</h1>
<p class="meta">fired {{ entry.timestamp_fired.strftime('%Y-%m-%d %H:%M') }}
  · locks {{ entry.lock_at.strftime('%Y-%m-%d %H:%M') }}</p>
{% for prompt in entry.prompt_snapshot %}
<blockquote>{{ prompt }}</blockquote>
{% endfor %}
<form method="post" action="/entry/{{ entry.id }}">
<textarea name="response" autofocus>{{ entry.response }}</textarea>
<button type="submit">{{ 'Update' if entry.response else 'Submit' }}</button>
</form>
{% else %}
<p>No open prompt right now. The next one will fire at its scheduled time.</p>
{% endif %}
{% endblock %}
"""

_ENTRY = """\
{% extends '_base.html' %}
{% block content %}
<h1>{{ entry.title }}</h1>
<p class="meta">
  status: {{ entry.status.value }}
  · fired {{ entry.timestamp_fired.strftime('%Y-%m-%d %H:%M') }}
  · {% if locked %}<span class="locked">locked {{ entry.lock_at.strftime('%Y-%m-%d %H:%M') }}</span>
     {% else %}locks {{ entry.lock_at.strftime('%Y-%m-%d %H:%M') }}{% endif %}
</p>
{% for prompt in entry.prompt_snapshot %}
<blockquote>{{ prompt }}</blockquote>
{% endfor %}
{% if locked %}
<h2>Response</h2>
<pre>{{ entry.response or '(no response)' }}</pre>
{% else %}
<form method="post" action="/entry/{{ entry.id }}">
<textarea name="response" autofocus>{{ entry.response }}</textarea>
<button type="submit">{{ 'Update' if entry.response else 'Submit' }}</button>
</form>
{% endif %}
{% endblock %}
"""

_DAY = """\
{% extends '_base.html' %}
{% block content %}
<h1>{{ day.isoformat() }}</h1>
{% if entries %}
<ul>
{% for entry in entries %}
<li>
  <a href="/entry/{{ entry.id }}">{{ entry.timestamp_fired.strftime('%H:%M') }}
    — {{ entry.title }}</a>
  <span class="meta">({{ entry.status.value }})</span>
</li>
{% endfor %}
</ul>
{% else %}
<p>No entries on this day.</p>
{% endif %}
{% endblock %}
"""

_ANALYSIS_INDEX = """\
{% extends '_base.html' %}
{% block content %}
<h1>Analysis</h1>
{% if items %}
{% for cadence, group in items %}
<h2>{{ cadence }}</h2>
<ul>
{% for item in group %}
<li>
  <a href="/analysis/view?path={{ item.relative_path|urlencode }}">{{ item.title }}</a>
  {% if item.has_correction %}<span class="meta">(correction)</span>{% endif %}
</li>
{% endfor %}
</ul>
{% endfor %}
{% else %}
<p>No analysis reports yet.</p>
{% endif %}
{% endblock %}
"""

_PROPOSALS_INDEX = """\
{% extends '_base.html' %}
{% block content %}
<h1>Proposals</h1>
{% if pending %}
<h2>Pending</h2>
<ul>
{% for record in pending %}
<li>
  <a href="/proposals/{{ record.id }}">{{ record.proposal.action.value }}
    <code>{{ record.proposal.exercise.id }}</code></a>
  <span class="meta">proposed {{ record.proposed_at.strftime('%Y-%m-%d %H:%M') }}
    by {{ record.proposed_by }}</span>
</li>
{% endfor %}
</ul>
{% else %}
<p>No pending proposals.</p>
{% endif %}

{% if decided %}
<h2>Decided</h2>
<ul>
{% for record in decided %}
<li>
  <a href="/proposals/{{ record.id }}">{{ record.proposal.action.value }}
    <code>{{ record.proposal.exercise.id }}</code></a>
  <span class="meta">{{ record.status.value }}
    {% if record.decided_at %}· {{ record.decided_at.strftime('%Y-%m-%d') }}{% endif %}
  </span>
</li>
{% endfor %}
</ul>
{% endif %}
{% endblock %}
"""

_PROPOSAL_VIEW = """\
{% extends '_base.html' %}
{% block content %}
<h1>{{ record.proposal.action.value }}: <code>{{ record.proposal.exercise.id }}</code></h1>
<p class="meta">
  status: {{ record.status.value }}
  · proposed {{ record.proposed_at.strftime('%Y-%m-%d %H:%M') }} by {{ record.proposed_by }}
  {% if record.decided_at %}· decided {{ record.decided_at.strftime('%Y-%m-%d %H:%M') }}
   by {{ record.decided_by }}{% endif %}
</p>

<h2>Rationale</h2>
<p style="white-space: pre-wrap;">{{ record.proposal.rationale }}</p>

{% if record.proposal.diff %}
<h2>Diff</h2>
<pre>{{ record.proposal.diff }}</pre>
{% endif %}

{% if record.status.value == 'pending' %}
<h2>Refine the proposed exercise</h2>
<p class="meta">Edit the YAML below before approving. Id and action stay fixed —
to change those, reject and request a new proposal.</p>
<form method="post" action="/proposals/{{ record.id }}/refine">
<textarea name="exercise_yaml" style="min-height: 22rem; font-family: monospace;">{{ proposed_yaml }}</textarea>
<input type="text" name="rationale_addendum" placeholder="(optional) note explaining your refinement" style="width:100%; margin-top:0.5rem;">
<button type="submit">Save refinement</button>
</form>

<h2>Decision</h2>
<form method="post" action="/proposals/{{ record.id }}/approve" style="display:inline">
<button type="submit">Approve & apply</button>
</form>
<form method="post" action="/proposals/{{ record.id }}/reject" style="display:inline; margin-left:1rem;">
<input type="text" name="note" placeholder="(optional) reason" style="width:14rem;">
<button type="submit">Reject</button>
</form>
{% else %}
<h2>Proposed exercise</h2>
<pre>{{ proposed_yaml }}</pre>
{% if record.decision_note %}
<h2>Decision note</h2>
<p>{{ record.decision_note }}</p>
{% endif %}
{% endif %}
{% endblock %}
"""

_ANALYSIS_VIEW = """\
{% extends '_base.html' %}
{% block content %}
<h1>{{ relative_path }}</h1>
<p class="meta">cadence: {{ meta.cadence or '?' }}
{% if meta.window_start %} · {{ meta.window_start }} → {{ meta.window_end }}{% endif %}
{% if meta.correction_of %} · supersedes <code>{{ meta.correction_of }}</code>{% endif %}
</p>
<article>{{ rendered_body|safe }}</article>
<hr>
<h2>Flag a correction</h2>
<form method="post" action="/analysis/correct">
<input type="hidden" name="path" value="{{ relative_path }}">
<textarea name="note" placeholder="What was wrong?" required></textarea>
<button type="submit">Submit correction note</button>
</form>
{% endblock %}
"""


def build_env() -> Environment:
    return Environment(
        loader=DictLoader(
            {
                "_base.html": _BASE,
                "home.html": _HOME,
                "entry.html": _ENTRY,
                "day.html": _DAY,
                "analysis_index.html": _ANALYSIS_INDEX,
                "analysis_view.html": _ANALYSIS_VIEW,
                "proposals_index.html": _PROPOSALS_INDEX,
                "proposal_view.html": _PROPOSAL_VIEW,
            }
        ),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
