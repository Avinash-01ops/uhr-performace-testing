"""
generate_dashboard.py
─────────────────────
Reads JMeter results.csv files from results/{smoke,load,stress,spike}/
and generates a polished HTML dashboard at public/index.html.

Environment variables (injected by GitHub Actions):
    SMOKE_STATUS, LOAD_STATUS, STRESS_STATUS, SPIKE_STATUS  → success | failure | skipped
    GITHUB_SHA, GITHUB_REF_NAME, GITHUB_ACTOR
    GITHUB_RUN_ID, GITHUB_SERVER_URL, GITHUB_REPOSITORY, GITHUB_EVENT_NAME
"""

import csv
import math
import os
from datetime import datetime, timezone


# ── CSV Parser ────────────────────────────────────────────────────────────────

def parse_csv(path):
    """Read a JMeter results.csv and return summary statistics dict, or None."""
    if not os.path.exists(path):
        return None
    rows = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
    except Exception:
        return None
    if not rows:
        return None

    total = len(rows)
    errors = sum(
        1 for r in rows
        if r.get("success", "true").strip().lower() == "false"
    )
    error_pct = round((errors / total) * 100, 1) if total else 0.0

    latencies = []
    for r in rows:
        try:
            latencies.append(int(r.get("elapsed", 0)))
        except ValueError:
            pass

    avg_ms = round(sum(latencies) / len(latencies)) if latencies else 0
    sorted_l = sorted(latencies)
    p90_idx = math.ceil(0.90 * len(sorted_l)) - 1
    p90_ms = sorted_l[max(p90_idx, 0)] if sorted_l else 0

    # Throughput = total requests / elapsed duration in seconds
    throughput = 0.0
    try:
        ts_vals = []
        for r in rows:
            raw = r.get("timeStamp", "")
            if raw.isdigit():
                ts_vals.append(int(raw))
        if len(ts_vals) > 1:
            duration_s = (max(ts_vals) - min(ts_vals)) / 1000.0
            if duration_s > 0:
                throughput = round(total / duration_s, 1)
    except Exception:
        pass

    return {
        "total": total,
        "errors": errors,
        "error_pct": error_pct,
        "avg_ms": avg_ms,
        "p90_ms": p90_ms,
        "throughput": throughput,
    }


# ── Test definitions ──────────────────────────────────────────────────────────

TESTS = [
    {
        "id":      "smoke",
        "name":    "Smoke Test",
        "icon":    "🔵",
        "config":  "2 VU &middot; 60 seconds",
        "purpose": "Quick sanity check — validates basic connectivity and authentication",
        "status_env": "SMOKE_STATUS",
        "report":  "smoke/index.html",
    },
    {
        "id":      "load",
        "name":    "Load Test",
        "icon":    "🟡",
        "config":  "50 VU &middot; 10 minutes",
        "purpose": "Simulates normal production traffic volume",
        "status_env": "LOAD_STATUS",
        "report":  "load/index.html",
    },
    {
        "id":      "stress",
        "name":    "Stress Test",
        "icon":    "🟠",
        "config":  "150 VU &middot; 5 minutes",
        "purpose": "Pushes the system beyond normal load to find the breaking point",
        "status_env": "STRESS_STATUS",
        "report":  "stress/index.html",
    },
    {
        "id":      "spike",
        "name":    "Spike Test",
        "icon":    "🔴",
        "config":  "200 VU &middot; 2 minutes",
        "purpose": "Simulates a sudden burst of traffic — measures system recovery",
        "status_env": "SPIKE_STATUS",
        "report":  "spike/index.html",
    },
]


# ── Helper: status display ────────────────────────────────────────────────────

def status_css(s):
    return {"success": "pass", "failure": "fail"}.get(s, "skip")


def status_label(s):
    return {
        "success": "&#x2705; PASSED",
        "failure": "&#x274C; FAILED",
        "skipped": "&#x23ED; SKIPPED",
    }.get(s, "&#x26A0;&#xFE0F; UNKNOWN")


def overall_status(tests):
    statuses = [t["status"] for t in tests]
    if all(s == "success" for s in statuses):
        return "ALL PASSED", "pass"
    if any(s == "failure" for s in statuses):
        return "SOME FAILED", "fail"
    return "INCOMPLETE", "skip"


# ── HTML builders ─────────────────────────────────────────────────────────────

def metric_pill(label, value, unit="", warn=False):
    cls = ' class="metric metric-warn"' if warn else ' class="metric"'
    return (
        '<div{cls}>'
        '<span class="metric-val">{value}'
        '<span class="metric-unit">{unit}</span></span>'
        '<span class="metric-lbl">{label}</span>'
        '</div>'
    ).format(cls=cls, value=value, unit=unit, label=label)


def build_card(t):
    sc  = status_css(t["status"])
    lbl = status_label(t["status"])
    m   = t["metrics"]
    has_report = os.path.exists(
        os.path.join("results", t["id"], "html_report", "index.html")
    )

    if m:
        err_warn = m["error_pct"] > 1
        pills_html = (
            '<div class="metrics-grid">'
            + metric_pill("Total Requests",  "{:,}".format(m["total"]))
            + metric_pill("Error Rate",      m["error_pct"],  "%",  warn=err_warn)
            + metric_pill("Avg Response",    m["avg_ms"],     "ms", warn=m["avg_ms"] > 2000)
            + metric_pill("P90 Response",    m["p90_ms"],     "ms", warn=m["p90_ms"] > 3000)
            + metric_pill("Throughput",      m["throughput"], "/s")
            + metric_pill("Errors",          m["errors"])
            + '</div>'
        )
    else:
        pills_html = (
            '<div class="no-metrics">'
            'No metrics available &mdash; test did not produce results'
            '</div>'
        )

    if has_report:
        btn = '<a href="{}" class="btn-report">View Full JMeter Report &#x2192;</a>'.format(
            t["report"]
        )
    else:
        btn = '<span class="btn-report disabled">Report not available</span>'

    return """
    <div class="card card-{sc}">
      <div class="card-header">
        <div class="card-title">
          <span class="card-icon">{icon}</span>
          <div>
            <h2>{name}</h2>
            <span class="card-config">{config}</span>
          </div>
        </div>
        <span class="status-badge badge-{sc}">{lbl}</span>
      </div>
      <p class="card-purpose">{purpose}</p>
      {pills}
      <div class="card-footer">{btn}</div>
    </div>""".format(
        sc=sc, icon=t["icon"], name=t["name"], config=t["config"],
        lbl=lbl, purpose=t["purpose"], pills=pills_html, btn=btn,
    )


# ── CSS (kept in Python so workflow YAML stays clean) ─────────────────────────

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:           #0d1117;
  --bg-card:      #161b22;
  --bg-card2:     #1c2128;
  --border:       #30363d;
  --border-hi:    #484f58;
  --text:         #e6edf3;
  --text-muted:   #8b949e;
  --text-dim:     #6e7681;
  --pass:         #3fb950;
  --pass-bg:      #0d2c1e;
  --pass-border:  #1a4a2e;
  --fail:         #f85149;
  --fail-bg:      #2d1217;
  --fail-border:  #4a1a1d;
  --skip:         #d29922;
  --skip-bg:      #2d2600;
  --skip-border:  #4a3e00;
  --blue:         #58a6ff;
  --accent:       #1f6feb;
}

body {
  font-family: 'Inter', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.6;
}

/* ── Banner ────────────────────────────────────────────────── */
.banner {
  background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
  border-bottom: 1px solid var(--border);
  padding: 36px 24px 28px;
  text-align: center;
  position: relative;
  overflow: hidden;
}
.banner::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 80% 60% at 50% -20%,
    rgba(31,111,235,0.15) 0%, transparent 70%);
  pointer-events: none;
}
.banner-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--blue);
  margin-bottom: 8px;
}
.banner-title {
  font-size: clamp(22px, 4vw, 36px);
  font-weight: 800;
  letter-spacing: -0.5px;
  margin-bottom: 6px;
}
.banner-sub {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 20px;
}
.overall-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  border-radius: 99px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.overall-pass { background: var(--pass-bg); color: var(--pass); border: 1px solid var(--pass-border); }
.overall-fail { background: var(--fail-bg); color: var(--fail); border: 1px solid var(--fail-border); }
.overall-skip { background: var(--skip-bg); color: var(--skip); border: 1px solid var(--skip-border); }

/* ── Meta bar ──────────────────────────────────────────────── */
.meta-bar {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  padding: 12px 24px;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 4px 24px;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}
.meta-item strong {
  color: var(--text);
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}
.meta-item a { color: var(--blue); text-decoration: none; }
.meta-item a:hover { text-decoration: underline; }
.meta-dot { color: var(--border-hi); font-size: 10px; }

/* ── Main ──────────────────────────────────────────────────── */
.main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 20px 60px;
}
.section-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 16px;
}
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(520px, 1fr));
  gap: 16px;
}

/* ── Card ──────────────────────────────────────────────────── */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  transition: border-color 0.2s, transform 0.2s;
}
.card:hover { border-color: var(--border-hi); transform: translateY(-1px); }
.card-pass { border-left: 3px solid var(--pass); }
.card-fail { border-left: 3px solid var(--fail); }
.card-skip { border-left: 3px solid var(--skip); }

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
  gap: 12px;
}
.card-title { display: flex; align-items: center; gap: 12px; }
.card-icon { font-size: 28px; line-height: 1; }
.card-title h2 { font-size: 16px; font-weight: 700; margin-bottom: 4px; }
.card-config {
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-muted);
  background: var(--bg-card2);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--border);
}
.status-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  padding: 5px 12px;
  border-radius: 99px;
  white-space: nowrap;
}
.badge-pass { background: var(--pass-bg); color: var(--pass); border: 1px solid var(--pass-border); }
.badge-fail { background: var(--fail-bg); color: var(--fail); border: 1px solid var(--fail-border); }
.badge-skip { background: var(--skip-bg); color: var(--skip); border: 1px solid var(--skip-border); }

.card-purpose {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border);
}

/* ── Metrics ───────────────────────────────────────────────── */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}
.metric {
  background: var(--bg-card2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 4px;
  transition: border-color 0.2s;
}
.metric:hover { border-color: var(--border-hi); }
.metric-warn { background: rgba(248,81,73,0.08); border-color: var(--fail-border); }
.metric-val {
  font-size: 20px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text);
}
.metric-warn .metric-val { color: var(--fail); }
.metric-unit { font-size: 12px; font-weight: 400; color: var(--text-muted); margin-left: 1px; }
.metric-lbl  { font-size: 11px; color: var(--text-dim); font-weight: 500; letter-spacing: 0.3px; }
.no-metrics {
  background: var(--bg-card2);
  border: 1px dashed var(--border);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--text-dim);
  margin-bottom: 20px;
}

/* ── Button ────────────────────────────────────────────────── */
.card-footer { display: flex; }
.btn-report {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--accent);
  color: #fff;
  text-decoration: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  transition: background 0.2s, transform 0.1s;
}
.btn-report:hover { background: #388bfd; transform: translateX(2px); }
.btn-report.disabled {
  background: var(--bg-card2);
  color: var(--text-dim);
  border: 1px solid var(--border);
  cursor: not-allowed;
}

/* ── Footer ────────────────────────────────────────────────── */
.footer {
  text-align: center;
  padding: 24px;
  font-size: 12px;
  color: var(--text-dim);
  border-top: 1px solid var(--border);
}
.footer a { color: var(--blue); text-decoration: none; }
.footer a:hover { text-decoration: underline; }

@media (max-width: 600px) {
  .cards-grid { grid-template-columns: 1fr; }
  .metrics-grid { grid-template-columns: repeat(2, 1fr); }
  .meta-bar { justify-content: flex-start; }
}
"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Resolve per-test data
    tests = []
    for t in TESTS:
        entry = dict(t)
        entry["status"]  = os.environ.get(t["status_env"], "skipped")
        entry["metrics"] = parse_csv(
            os.path.join("results", t["id"], "results.csv")
        )
        tests.append(entry)

    # Run metadata
    sha      = os.environ.get("GITHUB_SHA", "")[:7] or "unknown"
    branch   = os.environ.get("GITHUB_REF_NAME", "unknown")
    actor    = os.environ.get("GITHUB_ACTOR", "unknown")
    run_id   = os.environ.get("GITHUB_RUN_ID", "")
    server   = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo     = os.environ.get("GITHUB_REPOSITORY", "")
    event    = os.environ.get("GITHUB_EVENT_NAME", "push")
    now      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run_url  = "{}/{}/actions/runs/{}".format(server, repo, run_id) if run_id else "#"

    ov_label, ov_class = overall_status(tests)
    cards_html = "\n".join(build_card(t) for t in tests)

    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UHR ADT Performance Test Dashboard</title>
  <meta name="description" content="UHR ADT Events performance test results — Smoke, Load, Stress, Spike">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&amp;family=JetBrains+Mono:wght@400;500&amp;display=swap" rel="stylesheet">
  <style>{css}</style>
</head>
<body>

  <header class="banner">
    <div class="banner-label">Waseel Health &middot; UHR ADT Events</div>
    <h1 class="banner-title">Performance Test Dashboard</h1>
    <p class="banner-sub">JMeter results across all test scenarios</p>
    <span class="overall-badge overall-{ov_class}">{ov_label}</span>
  </header>

  <div class="meta-bar">
    <span class="meta-item">&#x1F4C5; <strong>{now}</strong></span>
    <span class="meta-dot">&middot;</span>
    <span class="meta-item">&#x1F33F; Branch: <strong>{branch}</strong></span>
    <span class="meta-dot">&middot;</span>
    <span class="meta-item">&#x1F516; Commit: <strong>{sha}</strong></span>
    <span class="meta-dot">&middot;</span>
    <span class="meta-item">&#x1F464; Triggered by: <strong>{actor}</strong></span>
    <span class="meta-dot">&middot;</span>
    <span class="meta-item">&#x26A1; Event: <strong>{event}</strong></span>
    <span class="meta-dot">&middot;</span>
    <span class="meta-item"><a href="{run_url}" target="_blank">View Actions Run &#x2192;</a></span>
  </div>

  <main class="main">
    <p class="section-title">Test Results</p>
    <div class="cards-grid">
      {cards}
    </div>
  </main>

  <footer class="footer">
    Generated by GitHub Actions &nbsp;&middot;&nbsp;
    <a href="{run_url}" target="_blank">Run #{run_id}</a> &nbsp;&middot;&nbsp;
    UHR ADT Events Performance Testing Pipeline
  </footer>

</body>
</html>""".format(
        css=CSS,
        ov_class=ov_class, ov_label=ov_label,
        now=now, branch=branch, sha=sha, actor=actor,
        event=event, run_url=run_url, run_id=run_id or "—",
        cards=cards_html,
    )

    os.makedirs("public", exist_ok=True)
    out = os.path.join("public", "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("Dashboard written to", out)


if __name__ == "__main__":
    main()
