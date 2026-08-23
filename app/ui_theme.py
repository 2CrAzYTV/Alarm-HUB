from __future__ import annotations

from . import main


_original_layout = main._layout


THEME_CSS = r"""
<style id="alarmhub-ui-refresh">
:root {
  color-scheme: dark;
  --bg: #0b0f14;
  --surface: #111821;
  --surface-soft: #151e28;
  --surface-hover: #1a2632;
  --border: #263241;
  --border-soft: #1d2834;
  --text: #edf3f8;
  --muted: #94a3b3;
  --accent: #5da8ff;
  --accent-soft: rgba(93, 168, 255, .12);
  --success: #2fbf71;
  --danger: #d95454;
  --shadow: 0 18px 48px rgba(0, 0, 0, .20);
  --radius: 16px;
}

* { box-sizing: border-box; }
html { background: var(--bg); }
body {
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(circle at 18% -10%, rgba(67, 120, 190, .11), transparent 34rem),
    var(--bg);
  color: var(--text);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

nav {
  max-width: 1120px !important;
  margin: 0 auto !important;
  padding: 14px 22px !important;
  display: flex !important;
  align-items: center !important;
  gap: 6px !important;
  flex-wrap: wrap !important;
  border: 0 !important;
}
nav::before {
  content: "Alarm-HUB";
  margin-right: auto;
  font-size: 1.02rem;
  font-weight: 760;
  letter-spacing: -.02em;
  color: var(--text);
}
nav > a:first-of-type { display: none; }
nav a {
  color: var(--muted) !important;
  padding: 8px 11px;
  border-radius: 10px;
  font-size: .91rem;
  font-weight: 570;
  transition: background .15s ease, color .15s ease;
}
nav a:hover {
  color: var(--text) !important;
  background: var(--surface-hover);
}

body > nav {
  position: sticky;
  top: 0;
  z-index: 20;
  max-width: none !important;
  padding-left: max(22px, calc((100vw - 1120px) / 2)) !important;
  padding-right: max(22px, calc((100vw - 1120px) / 2)) !important;
  background: rgba(11, 15, 20, .88);
  border-bottom: 1px solid rgba(38, 50, 65, .72) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

main {
  max-width: 1040px !important;
  margin: 0 auto !important;
  padding: 38px 22px 70px !important;
}
main > h1 {
  margin: 0 0 26px;
  font-size: clamp(1.8rem, 4vw, 2.45rem);
  line-height: 1.1;
  letter-spacing: -.035em;
}

h2, h3 { letter-spacing: -.02em; }
h2 { margin-top: 0; font-size: 1.22rem; }
h3 { margin-top: 0; font-size: 1.02rem; }
p { margin: .65rem 0; }

section {
  background: var(--surface) !important;
  border: 1px solid var(--border-soft) !important;
  border-radius: var(--radius) !important;
  padding: 22px !important;
  margin: 0 0 18px !important;
  box-shadow: none !important;
}
section + section { margin-top: 18px !important; }

.card {
  background: var(--surface-soft) !important;
  border: 1px solid var(--border-soft) !important;
  border-radius: 13px !important;
  padding: 16px 17px !important;
  margin: 14px 0 !important;
  box-shadow: none !important;
}
.card:last-child { margin-bottom: 0 !important; }

/* Long beginner guides stay readable instead of looking like dozens of heavy panels. */
#ios .card, #android .card {
  background: transparent !important;
  border: 0 !important;
  border-top: 1px solid var(--border-soft) !important;
  border-radius: 0 !important;
  padding: 18px 0 4px !important;
  margin: 14px 0 0 !important;
}
#ios .card:first-of-type, #android .card:first-of-type {
  border-top: 0 !important;
  padding-top: 4px !important;
}

a {
  color: var(--accent);
  text-decoration: none;
}
a:hover { text-decoration: none; }

.row {
  display: flex !important;
  gap: 10px !important;
  flex-wrap: wrap !important;
  align-items: center !important;
}

input, select, textarea {
  width: 100%;
  max-width: 560px;
  background: #0d141c !important;
  color: var(--text) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px !important;
  padding: 10px 12px !important;
  min-height: 42px;
  outline: none;
  transition: border-color .15s ease, box-shadow .15s ease;
}
input:focus, select:focus, textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-soft);
}
label {
  display: block !important;
  margin: 13px 0 !important;
  color: #cbd6e1;
  font-size: .92rem;
  font-weight: 560;
}
label input, label select, label textarea {
  display: block;
  margin-top: 6px;
}

button, .button, a.button {
  appearance: none;
  border: 1px solid transparent !important;
  border-radius: 10px !important;
  padding: 9px 14px !important;
  min-height: 40px;
  background: #2477d4 !important;
  color: #fff !important;
  font-weight: 650;
  cursor: pointer;
  transition: transform .12s ease, filter .12s ease;
}
button:hover, .button:hover, a.button:hover { filter: brightness(1.08); }
button:active { transform: translateY(1px); }
button.danger {
  background: transparent !important;
  border-color: rgba(217, 84, 84, .42) !important;
  color: #ff9696 !important;
}

.alarm {
  display: flex !important;
  justify-content: space-between !important;
  align-items: center !important;
  gap: 16px !important;
  padding: 15px 2px !important;
  border-top: 1px solid var(--border-soft) !important;
}
.alarm:first-of-type { border-top: 0 !important; }
.alarm b { font-size: .98rem; }

.muted {
  color: var(--muted) !important;
  font-size: .9rem;
}

code {
  color: #c6dcf5;
  background: #0b1219;
  border: 1px solid var(--border-soft);
  border-radius: 7px;
  padding: 2px 6px;
  word-break: break-word !important;
}
pre {
  overflow-x: auto;
  padding: 14px;
  background: #0b1219;
  border: 1px solid var(--border-soft);
  border-radius: 11px;
}
pre code { border: 0; padding: 0; background: transparent; }

ol, ul { padding-left: 1.35rem; }
li { margin: .42rem 0; }
hr { border: 0; border-top: 1px solid var(--border-soft); margin: 22px 0; }

details {
  background: var(--surface-soft);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 13px 15px;
  margin: 14px 0;
}
summary {
  cursor: pointer;
  font-weight: 680;
  color: #dbe7f1;
}
details[open] summary { margin-bottom: 14px; }

@media (max-width: 720px) {
  body > nav {
    position: static;
    padding: 12px 14px !important;
  }
  nav::before { width: 100%; margin-bottom: 4px; }
  nav a { padding: 7px 9px; font-size: .86rem; }
  main { padding: 28px 14px 54px !important; }
  main > h1 { margin-bottom: 20px; }
  section { padding: 17px !important; border-radius: 14px !important; }
  .alarm { align-items: flex-start !important; flex-direction: column; }
  .alarm form, .alarm button { width: 100%; }
}
</style>
"""


def _refreshed_layout(title: str, body: str, user: main.User | None = None) -> str:
    html = _original_layout(title, body, user)
    if "alarmhub-ui-refresh" not in html:
        html = html.replace("</head>", THEME_CSS + "</head>")
    return html


main._layout = _refreshed_layout
