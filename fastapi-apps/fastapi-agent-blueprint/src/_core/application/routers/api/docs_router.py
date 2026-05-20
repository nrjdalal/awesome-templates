from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()

HANDOFF_GUIDE_URL = (
    "https://github.com/Mr-DooSun/fastapi-agent-blueprint"
    "/blob/main/docs/frontend-handoff.md"
)

# Card data shared by the selector renderer. Keep order stable: the first two
# entries are the recommended viewers, the rest are alternates.
DOCS_CARDS: list[dict[str, str]] = [
    {
        "key": "elements",
        "href": "/api/docs-elements",
        "title": "Stoplight Elements",
        "tagline": "Interactive, three-pane reader. Best for browsing.",
        "label": "Recommended — Visual",
        "kind": "primary",
        "icon": "🎨",
    },
    {
        "key": "scalar",
        "href": "/api/docs-scalar",
        "title": "Scalar API Reference",
        "tagline": "Modern reference with try-it that bridges into a client.",
        "label": "Recommended — Try-it",
        "kind": "primary",
        "icon": "✨",
    },
    {
        "key": "swagger",
        "href": "/api/docs-swagger",
        "title": "Swagger UI",
        "tagline": "FastAPI's bundled default. Familiar to most teams.",
        "label": "Compatibility",
        "kind": "secondary",
        "icon": "📚",
    },
    {
        "key": "redoc",
        "href": "/api/docs-redoc",
        "title": "ReDoc",
        "tagline": "Documentation-first three-panel layout.",
        "label": "Clean",
        "kind": "secondary",
        "icon": "📖",
    },
    {
        "key": "rapidoc",
        "href": "/api/docs-rapidoc",
        "title": "RapiDoc",
        "tagline": "Lightweight viewer. Fast initial load.",
        "label": "Fast",
        "kind": "secondary",
        "icon": "⚡",
    },
]


def _handoff_cards(download_url: str) -> list[dict[str, str]]:
    # `kind="secondary"` keeps the Recommended visual weight reserved for the
    # two viewer cards; handoff actions read as quieter rows.
    return [
        {
            "key": "download",
            "href": download_url,
            "title": "Download OpenAPI (JSON)",
            "tagline": "Save the live spec as openapi.json for Postman, Bruno, or any client.",
            "label": "Spec",
            "external": "false",
            "kind": "secondary",
            "icon": "⬇️",
        },
        {
            "key": "handoff",
            "href": HANDOFF_GUIDE_URL,
            "title": "Frontend Handoff Guide",
            "tagline": "Contract scope, test client comparison, and TypeScript SDK recipes.",
            "label": "Guide",
            "external": "true",
            "kind": "secondary",
            "icon": "🧭",
        },
    ]


@router.get(
    "/docs",
    include_in_schema=False,
    description="API Docs Selector - landing page for choosing among various documentation UIs",
)
def docs_selector(request: Request):
    root_path = request.scope.get("root_path", "")
    download_url = f"{root_path}/openapi-download.json"
    handoff_cards = _handoff_cards(download_url)
    return HTMLResponse(_render_selector(DOCS_CARDS, handoff_cards))


# ---------------------------------------------------------------------------
# Selector renderer — GitHub-flavoured minimal list with light/dark themes.
# Recommended cards lean on a left accent strip + filled badge so the two
# primary viewers read out of the page at a glance. Theme is user-toggleable
# (top-right button), persists in localStorage, and falls back to the system
# preference via prefers-color-scheme. The inline pre-paint script hydrates
# the data-theme attribute before first paint to avoid FOUC.
# ---------------------------------------------------------------------------


def _render_selector(
    docs_cards: list[dict[str, str]],
    handoff_cards: list[dict[str, str]],
) -> str:
    rows = "\n".join(_selector_row(c) for c in docs_cards)
    handoff_rows = "\n".join(_selector_row(c) for c in handoff_cards)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>API Documentation — fastapi-agent-blueprint</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script>
      (function() {{
        try {{
          var stored = localStorage.getItem('docs-selector-theme');
          if (stored === 'dark' || stored === 'light') {{
            document.documentElement.setAttribute('data-theme', stored);
          }}
        }} catch (e) {{ /* ignore */ }}
      }})();
    </script>
    <style>
      :root {{
        --bg: #ffffff;
        --surface: #ffffff;
        --fg: #0e0e10;
        --muted: #57606a;
        --border: #d0d7de;
        --border-hover: #0969da;
        --accent: #0969da;
        --accent-fg: #ffffff;
        --accent-soft: #ddf4ff;
        --focus-ring: #0969da;
      }}
      :root[data-theme="dark"] {{
        --bg: #0d1117;
        --surface: #161b22;
        --fg: #e6edf3;
        --muted: #7d8590;
        --border: #30363d;
        --border-hover: #58a6ff;
        --accent: #58a6ff;
        --accent-fg: #0d1117;
        --accent-soft: #121d2f;
        --focus-ring: #58a6ff;
      }}
      @media (prefers-color-scheme: dark) {{
        :root:not([data-theme]) {{
          --bg: #0d1117;
          --surface: #161b22;
          --fg: #e6edf3;
          --muted: #7d8590;
          --border: #30363d;
          --border-hover: #58a6ff;
          --accent: #58a6ff;
          --accent-fg: #0d1117;
          --accent-soft: #121d2f;
          --focus-ring: #58a6ff;
        }}
      }}

      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ background: var(--bg); }}
      body {{
        background: var(--bg); color: var(--fg);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', sans-serif;
        min-height: 100vh; padding: 64px 24px; line-height: 1.5;
        font-size: 15px;
      }}
      .frame {{ max-width: 720px; margin: 0 auto; }}
      .head h1 {{ font-size: 1.6rem; font-weight: 600; margin-bottom: 4px; }}
      .head .meta {{ color: var(--muted); font-size: 13px; }}
      .section-head {{
        margin: 36px 0 12px; font-size: 12px; font-weight: 600; color: var(--muted);
        text-transform: uppercase; letter-spacing: 0.04em;
      }}
      .list {{ display: flex; flex-direction: column; gap: 8px; }}
      .row {{
        display: flex; align-items: center; justify-content: space-between; gap: 16px;
        padding: 14px 16px; border: 1px solid var(--border); border-radius: 6px;
        text-decoration: none; color: var(--fg); transition: border-color 0.12s ease;
        background: var(--surface);
      }}
      .row:hover {{ border-color: var(--border-hover); }}
      .row.primary {{
        border-left: 3px solid var(--accent); padding-left: 14px;
      }}
      .row .row-leading {{ display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }}
      .row .row-icon {{
        font-size: 1.5rem; line-height: 1; flex-shrink: 0;
        width: 32px; text-align: center;
      }}
      .row .row-text {{ min-width: 0; }}
      .row .row-text .name {{ font-weight: 600; font-size: 0.98rem; }}
      .row .row-text .desc {{ color: var(--muted); font-size: 13px; margin-top: 2px; }}
      .row .row-meta {{ display: flex; align-items: center; gap: 10px; flex-shrink: 0; }}
      .row .label {{
        font-size: 11px; color: var(--muted); border: 1px solid var(--border);
        padding: 2px 8px; border-radius: 999px; white-space: nowrap;
      }}
      .row .label.primary {{
        color: var(--accent-fg); background: var(--accent); border-color: var(--accent);
      }}
      .row .arrow {{ color: var(--muted); font-size: 14px; }}
      .row:hover .arrow {{ color: var(--accent); }}

      .toolbar {{
        position: fixed; top: 14px; right: 14px;
        display: flex; gap: 4px; align-items: center;
        background: var(--surface); border: 1px solid var(--border);
        border-radius: 6px; padding: 4px 6px;
        font-size: 12px; z-index: 10;
      }}
      .toolbar button {{
        background: transparent; border: 0; cursor: pointer;
        color: var(--muted); padding: 4px 8px; border-radius: 3px; font: inherit;
      }}
      .toolbar button:hover {{ color: var(--fg); background: var(--accent-soft); }}

      .row:focus-visible,
      .toolbar button:focus-visible {{
        outline: 2px solid var(--focus-ring); outline-offset: 2px;
      }}

      @media (max-width: 720px) {{
        body {{ padding: 32px 16px 64px; }}
        .toolbar {{ top: 8px; right: 8px; }}
      }}
    </style>
  </head>
  <body>
    <nav class="toolbar" aria-label="Theme toggle">
      <button id="theme-toggle" type="button"
              aria-label="Toggle light or dark theme" aria-pressed="false">Dark</button>
    </nav>
    <div class="frame">
      <div class="head">
        <h1>API Documentation</h1>
        <div class="meta">fastapi-agent-blueprint · dev environment · /docs</div>
      </div>
      <div class="section-head">Viewers</div>
      <div class="list">
{rows}
      </div>
      <div class="section-head">Handoff</div>
      <div class="list">
{handoff_rows}
      </div>
    </div>
    <script>
      (function() {{
        var KEY = 'docs-selector-theme';
        var root = document.documentElement;
        var btn = document.getElementById('theme-toggle');
        function currentTheme() {{
          return root.getAttribute('data-theme')
            || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        }}
        function paint() {{
          var dark = currentTheme() === 'dark';
          btn.textContent = dark ? 'Light' : 'Dark';
          btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
        }}
        paint();
        btn.addEventListener('click', function() {{
          var next = currentTheme() === 'dark' ? 'light' : 'dark';
          root.setAttribute('data-theme', next);
          try {{ localStorage.setItem(KEY, next); }} catch (e) {{ /* ignore */ }}
          paint();
        }});
      }})();
    </script>
  </body>
</html>"""


def _selector_row(card: dict[str, str]) -> str:
    kind = card.get("kind", "primary")
    row_class = "row primary" if kind == "primary" else "row"
    label_class = "label primary" if kind == "primary" else "label"
    is_external = card.get("external", "false") == "true"
    target = ' target="_blank" rel="noopener"' if is_external else ""
    download = (
        " download"
        if card.get("external") == "false" and card["key"] == "download"
        else ""
    )
    icon = card.get("icon", "")
    return f"""        <a class="{row_class}" href="{card["href"]}"{target}{download}>
          <div class="row-leading">
            <span class="row-icon" aria-hidden="true">{icon}</span>
            <div class="row-text">
              <div class="name">{card["title"]}</div>
              <div class="desc">{card["tagline"]}</div>
            </div>
          </div>
          <div class="row-meta">
            <span class="{label_class}">{card["label"]}</span>
            <span class="arrow">&rsaquo;</span>
          </div>
        </a>"""


# ---------------------------------------------------------------------------
# Spec download + individual UI mounts.
# ---------------------------------------------------------------------------


@router.get(
    "/openapi-download.json",
    include_in_schema=False,
    description="OpenAPI spec download with attachment Content-Disposition for frontend handoff",
)
def openapi_download(request: Request):
    spec = request.app.openapi()
    return JSONResponse(
        content=spec,
        headers={"Content-Disposition": 'attachment; filename="openapi.json"'},
    )


@router.get(
    "/docs-scalar",
    include_in_schema=False,
    description="Scalar API Reference - Modern, clean API documentation",
)
def scalar_docs(request: Request):
    root_path = request.scope.get("root_path", "")
    spec_url = f"{root_path}{request.app.openapi_url}"
    return HTMLResponse(
        f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>API Reference - Scalar</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </head>
  <body>
    <div id="api"></div>
    <script>
      Scalar.createApiReference('#api', {{
        url: '{spec_url}',
      }});
    </script>
  </body>
</html>"""
    )


@router.get(
    "/docs-elements",
    include_in_schema=False,
    description="Stoplight Elements - Interactive, visually appealing API documentation",
)
def elements_docs(request: Request):
    root_path = request.scope.get("root_path", "")
    spec_url = f"{root_path}{request.app.openapi_url}"
    return HTMLResponse(
        f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>API Reference - Elements</title>
    <script src="https://unpkg.com/@stoplight/elements/web-components.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@stoplight/elements/styles.min.css" />
  </head>
  <body>
    <elements-api apiDescriptionUrl="{spec_url}" router="hash" />
  </body>
</html>"""
    )


@router.get(
    "/docs-rapidoc",
    include_in_schema=False,
    description="RapiDoc - Fast, lightweight API documentation",
)
def rapidoc_docs(request: Request):
    root_path = request.scope.get("root_path", "")
    spec_url = f"{root_path}{request.app.openapi_url}"
    return HTMLResponse(
        f"""
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>API Reference - RapiDoc</title>
    <script type="module" src="https://unpkg.com/rapidoc/dist/rapidoc-min.js"></script>
  </head>
  <body>
    <rapi-doc spec-url="{spec_url}"
              render-style="read"
              allow-try="true"
              show-method-in-nav-bar="true">
    </rapi-doc>
  </body>
</html>"""
    )
