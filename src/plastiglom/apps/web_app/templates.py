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
<a href="/">Today</a> <a href="/day/{{ today.isoformat() }}">Index</a>
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


def build_env() -> Environment:
    return Environment(
        loader=DictLoader(
            {
                "_base.html": _BASE,
                "home.html": _HOME,
                "entry.html": _ENTRY,
                "day.html": _DAY,
            }
        ),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
