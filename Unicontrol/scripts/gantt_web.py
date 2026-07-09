# scripts/gantt_web.py
"""Local web-app PROOF OF CONCEPT: pick a project + view in the browser, get the Gantt.

    python scripts/gantt_web.py            # serves http://127.0.0.1:8000 and opens it

A program manager just opens the URL, chooses a project and Customer/Internal, and the
Gantt renders in the browser — no Python, no repo, no Odoo secrets on their machine.
Stdlib only. READ-ONLY on Odoo. This POC has NO authentication and binds to localhost;
auth + hosting are the next step before real PMs use it.
"""
from __future__ import annotations

import argparse
import sys
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uc.core.config import add_hermes_to_path, load_config  # noqa: E402
from uc.service.gantt_service import RenderError, norm_view, render  # noqa: E402

add_hermes_to_path()
from uc.connectors.odoo_project import ProjectOdooClient  # noqa: E402

PAGE_CSS = """
:root{--bg:#eef1f4;--panel:#fff;--ink:#161b22;--muted:#5b6b7c;--line:#d7dde3;--accent:#d97b12}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
background:var(--bg);color:var(--ink);line-height:1.5}
.wrap{max-width:640px;margin:0 auto;padding:56px 24px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.02em}
.sub{color:var(--muted);margin:0 0 28px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:24px;
box-shadow:0 1px 3px rgba(20,30,45,.06)}
label{display:block;font-size:13px;color:var(--muted);margin:16px 0 6px;font-weight:600}
select,input[type=date]{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:9px;
font-size:15px;background:#fff;color:var(--ink)}
.views{display:flex;gap:10px;margin-top:6px}
.views label{flex:1;margin:0;display:flex;align-items:center;gap:8px;border:1px solid var(--line);
border-radius:9px;padding:12px;cursor:pointer;font-weight:500;color:var(--ink)}
.views input{accent-color:var(--accent)}
.hint{font-size:12px;color:var(--muted);margin-top:4px}
.btn{display:inline-block;margin-top:22px;width:100%;text-align:center;background:var(--accent);
color:#fff;border:0;border-radius:9px;padding:13px;font-size:15px;font-weight:600;cursor:pointer;
text-decoration:none}
.warn{margin-top:14px;font-size:12.5px;color:#8a5a12;background:#fdf3e3;border:1px solid #f0d9b5;
border-radius:8px;padding:10px 12px}
.eyebrow{font-family:ui-monospace,Consolas,monospace;font-size:12px;letter-spacing:.14em;
text-transform:uppercase;color:var(--accent);margin:0 0 6px}
a.back{color:var(--accent)}
"""


def render_index(projects: list[dict]) -> str:
    opts = "\n".join(
        f'<option value="{p["id"]}">[{p["id"]}] {p["name"]}</option>' for p in projects)
    today = date.today().isoformat()
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Generador de Gantt — Unicontrol</title><style>{PAGE_CSS}</style></head><body>
<div class="wrap">
  <p class="eyebrow">Unicontrol · PM</p>
  <h1>Generador de Gantt</h1>
  <p class="sub">Elige un proyecto y una vista. Se genera en tu navegador.</p>
  <form class="card" action="/render" method="get" target="_blank">
    <label for="project_id">Proyecto</label>
    <select id="project_id" name="project_id" required>{opts}</select>

    <label>Vista</label>
    <div class="views">
      <label><input type="radio" name="view" value="customer" checked> Cliente
        <span class="hint">(fases + hitos)</span></label>
      <label><input type="radio" name="view" value="internal"> Interno
        <span class="hint">(WBS + línea base)</span></label>
    </div>

    <label for="as_of">Fecha de estado</label>
    <input id="as_of" type="date" name="as_of" value="{today}">

    <button class="btn" type="submit">Generar Gantt</button>
    <div class="warn"><b>Interno = USO INTERNO.</b> No lo compartas con clientes; expone
      cada tarea y su desviación. La vista de <b>Cliente</b> sí es segura para compartir.</div>
  </form>
</div></body></html>"""


def error_page(message: str, extra_html: str = "") -> str:
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Sin generar</title><style>{PAGE_CSS}</style></head><body><div class="wrap">
  <h1>No se pudo generar</h1>
  <div class="card"><p>{message}</p>{extra_html}
  <p style="margin-top:18px"><a class="back" href="/">← Volver</a></p></div>
</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quieter console
        pass

    def _send(self, code: int, html: str):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _odoo(self):
        return ProjectOdooClient.from_config(self.server.cfg)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index"):
            odoo = self._odoo()
            self._send(200, render_index(odoo.active_projects()))
        elif parsed.path == "/render":
            self._render(parse_qs(parsed.query))
        elif parsed.path == "/favicon.ico":
            self._send(204, "")
        else:
            self._send(404, error_page("Página no encontrada."))

    def _render(self, q: dict):
        raw = q.get("project_id", [""])[0]
        if not raw.isdigit():
            self._send(400, error_page("Falta un proyecto válido."))
            return
        pid = int(raw)
        view = norm_view(q.get("view", [""])[0])
        if not view:
            self._send(400, error_page("Vista inválida (customer|internal)."))
            return
        as_of_s = q.get("as_of", [""])[0]
        as_of = date.fromisoformat(as_of_s) if as_of_s else date.today()
        save_bl = q.get("save_baseline", ["0"])[0] == "1"

        odoo = self._odoo()
        proj = odoo.project_by_id(pid)
        if not proj:
            self._send(404, error_page(f"No existe el proyecto {pid}."))
            return
        try:
            html = render(odoo, self.server.cfg, pid, proj["name"], view, as_of,
                          save_baseline_if_missing=save_bl)
            self._send(200, html)
        except RenderError as e:
            extra = ""
            if e.code == 6:  # no baseline yet — offer to save it and retry
                extra = (f'<a class="btn" href="/render?project_id={pid}&view=internal'
                         f'&as_of={as_of.isoformat()}&save_baseline=1">'
                         "Guardar línea base ahora y generar</a>")
            self._send(200, error_page(e.message, extra))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", dest="open_", action="store_false")
    ap.set_defaults(open_=True)
    args = ap.parse_args()

    cfg = load_config()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.cfg = cfg
    url = f"http://{args.host}:{args.port}/"
    print(f"Gantt web (POC) en {url}  —  Ctrl+C para detener")
    print("  Sin autenticación; solo localhost. Auth + hosting es el siguiente paso.")
    if args.open_:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
