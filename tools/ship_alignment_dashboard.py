#!/usr/bin/env python3
"""Build a single local HTML review dashboard for ShuttleA alignment."""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
FIT_TARGETS_JSON_PATH = REPORTS / "ship_fit_targets.json"
RECOMMENDATIONS_JSON_PATH = REPORTS / "ship_fit_recommendations.json"
DASHBOARD_PATH = REPORTS / "ship_alignment_dashboard.html"
CAPTURE_DIR = REPORTS / "ship_alignment_captures"

PROJECTION_ARTIFACTS = [
    ("Top Projection", "ship_alignment_top.svg"),
    ("Side Projection", "ship_alignment_side.svg"),
    ("Front Projection", "ship_alignment_front.svg"),
]

EXPECTED_CAPTURES = [
    "01_exterior_front.png",
    "02_exterior_rear_hatch.png",
    "03_exterior_left.png",
    "04_exterior_top.png",
    "05_cockpit_glass_close.png",
    "06_interior_entry.png",
    "07_interior_seat.png",
    "08_interior_cockpit_backlook.png",
]


def rel(path: Path) -> str:
    return path.relative_to(REPORTS).as_posix()


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def vector_text(value: object) -> str:
    if not isinstance(value, list) or len(value) != 3:
        return "-"
    return f"{value[0]:.2f}, {value[1]:.2f}, {value[2]:.2f}"


def artifact_card(title: str, path: Path) -> str:
    escaped_title = html.escape(title)
    if not path.exists():
        return f"""
        <section class="card missing">
          <h3>{escaped_title}</h3>
          <div class="placeholder">Missing: <code>{html.escape(rel(path))}</code></div>
        </section>
        """
    return f"""
    <section class="card">
      <h3>{escaped_title}</h3>
      <a href="{html.escape(rel(path))}"><img src="{html.escape(rel(path))}" alt="{escaped_title}"></a>
    </section>
    """


def recommendations_table(data: dict[str, object]) -> str:
    rows = data.get("recommendations", [])
    if not isinstance(rows, list):
        rows = []
    body: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        severity = str(row.get("severity", "unknown"))
        notes = row.get("notes", [])
        if isinstance(notes, list):
            notes_text = "<br>".join(html.escape(str(note)) for note in notes)
        else:
            notes_text = html.escape(str(notes))
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('name', '-')))}</td>"
            f"<td><span class=\"severity {html.escape(severity)}\">{html.escape(severity)}</span></td>"
            f"<td><code>{html.escape(vector_text(row.get('center_delta')))}</code></td>"
            f"<td><code>{html.escape(vector_text(row.get('suggested_centering_move')))}</code></td>"
            f"<td>{notes_text}</td>"
            "</tr>"
        )
    if not body:
        body.append("<tr><td colspan=\"5\">No recommendation data generated yet.</td></tr>")
    return "\n".join(body)


def fit_targets_table(data: dict[str, object]) -> str:
    targets = data.get("fit_targets", {})
    if not isinstance(targets, dict):
        targets = {}
    rows: list[str] = []
    for name, bounds in targets.items():
        if not isinstance(bounds, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(name))}</td>"
            f"<td><code>{html.escape(vector_text(bounds.get('center')))}</code></td>"
            f"<td><code>{html.escape(vector_text(bounds.get('size')))}</code></td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan=\"3\">No fit target data generated yet.</td></tr>")
    return "\n".join(rows)


def failure_list(data: dict[str, object], recommendation_data: dict[str, object]) -> str:
    failures: list[object] = []
    raw_failures = data.get("failures", [])
    if isinstance(raw_failures, list):
        failures.extend(raw_failures)
    upstream = recommendation_data.get("upstream_failures", [])
    if isinstance(upstream, list):
        failures.extend(failure for failure in upstream if failure not in failures)
    if not failures:
        return '<p class="status ok">No automated gate failures.</p>'
    items = "\n".join(f"<li>{html.escape(str(failure))}</li>" for failure in failures)
    return f'<ul class="failures">{items}</ul>'


def capture_cards() -> str:
    return "\n".join(
        artifact_card(capture.removesuffix(".png").replace("_", " ").title(), CAPTURE_DIR / capture)
        for capture in EXPECTED_CAPTURES
    )


def write_dashboard() -> None:
    fit_data = read_json(FIT_TARGETS_JSON_PATH)
    recommendation_data = read_json(RECOMMENDATIONS_JSON_PATH)
    projections = "\n".join(
        artifact_card(title, REPORTS / filename)
        for title, filename in PROJECTION_ARTIFACTS
    )
    captures = capture_cards()
    visual_bounds = fit_data.get("visual_bounds", {})
    visual_center = "-"
    visual_size = "-"
    if isinstance(visual_bounds, dict):
        visual_center = vector_text(visual_bounds.get("center"))
        visual_size = vector_text(visual_bounds.get("size"))

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ship Alignment Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f5f7;
      --panel: #ffffff;
      --ink: #111827;
      --muted: #5b6472;
      --line: #d8dde6;
      --ok: #0f766e;
      --review: #a16207;
      --adjust: #b91c1c;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    main {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px;
    }}
    header {{
      margin-bottom: 22px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 28px 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 0 0 10px;
      font-size: 15px;
      letter-spacing: 0;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      margin: 16px 0;
    }}
    .metric, .card, table {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric {{
      padding: 14px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 4px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 14px;
    }}
    .card {{
      padding: 12px;
      min-height: 180px;
    }}
    .card img {{
      width: 100%;
      max-height: 680px;
      object-fit: contain;
      background: #eef1f5;
      border: 1px solid var(--line);
      border-radius: 4px;
    }}
    .placeholder {{
      display: grid;
      min-height: 150px;
      place-items: center;
      color: var(--muted);
      background: #eef1f5;
      border: 1px dashed #aab3c2;
      border-radius: 4px;
      text-align: center;
      padding: 16px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      overflow: hidden;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      background: #f8fafc;
    }}
    code {{
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
    }}
    .severity {{
      display: inline-block;
      min-width: 52px;
      padding: 2px 8px;
      border-radius: 999px;
      color: white;
      text-align: center;
      font-size: 12px;
    }}
    .severity.ok {{ background: var(--ok); }}
    .severity.review {{ background: var(--review); }}
    .severity.adjust, .severity.critical {{ background: var(--adjust); }}
    .status.ok {{
      color: var(--ok);
      font-weight: 600;
    }}
    .failures {{
      color: var(--adjust);
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-radius: 8px;
      padding: 12px 12px 12px 30px;
    }}
    .links a {{
      margin-right: 14px;
    }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>Ship Alignment Dashboard</h1>
    <p>Single-page review surface for the ShuttleA 0.2.1b alignment loop.</p>
    <p class="links">
      <a href="ship_alignment_report.md">Markdown report</a>
      <a href="ship_fit_recommendations.md">Fit recommendations</a>
      <a href="ship_fit_targets.json">Fit target JSON</a>
      <a href="ship_hull_profile.csv">Hull profile CSV</a>
    </p>
  </header>

  <section class="summary">
    <div class="metric"><span>Visual Bounds Center</span><code>{html.escape(visual_center)}</code></div>
    <div class="metric"><span>Visual Bounds Size</span><code>{html.escape(visual_size)}</code></div>
    <div class="metric"><span>Screenshot Directory</span><code>reports/ship_alignment_captures</code></div>
  </section>

  <h2>Automated Gate</h2>
  {failure_list(fit_data, recommendation_data)}

  <h2>Fit Recommendations</h2>
  <table>
    <thead><tr><th>Fit</th><th>Severity</th><th>Center Delta</th><th>Suggested Move</th><th>Notes</th></tr></thead>
    <tbody>{recommendations_table(recommendation_data)}</tbody>
  </table>

  <h2>Fit Targets</h2>
  <table>
    <thead><tr><th>Target</th><th>Center</th><th>Size</th></tr></thead>
    <tbody>{fit_targets_table(fit_data)}</tbody>
  </table>

  <h2>Projection Overlays</h2>
  <div class="grid">{projections}</div>

  <h2>Fixed Camera Captures</h2>
  <div class="grid">{captures}</div>
</main>
</body>
</html>
"""
    DASHBOARD_PATH.write_text(document, encoding="utf-8")


def main() -> int:
    check_mode = "--check" in sys.argv[1:]
    if not FIT_TARGETS_JSON_PATH.exists():
        print(f"FAIL: {FIT_TARGETS_JSON_PATH.relative_to(ROOT)} does not exist.", file=sys.stderr)
        return 1
    if not RECOMMENDATIONS_JSON_PATH.exists():
        print(f"FAIL: {RECOMMENDATIONS_JSON_PATH.relative_to(ROOT)} does not exist.", file=sys.stderr)
        return 1
    write_dashboard()
    print(f"Wrote {DASHBOARD_PATH.relative_to(ROOT)}")
    if check_mode and not DASHBOARD_PATH.exists():
        print("FAIL: dashboard was not written.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
