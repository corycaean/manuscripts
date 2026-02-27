#!/usr/bin/env python3
"""
manuscripts-teacher — receives PDF submissions from students over LAN.

Usage:
    python teacher.py

Opens a browser dashboard at http://localhost:{port}/ and advertises itself
on the local network as a submission target for manuscripts.py.
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import re
import socket
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from aiohttp import web
from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceInfo, AsyncZeroconf

# ── Embedded browser UI ──────────────────────────────────────────────────────

HTML_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>manuscripts · {teacher_name}</title>
  <style>
    :root {{
      --bg:       #2a2a2a;
      --text:     #e0e0e0;
      --accent:   #e0af68;
      --blue:     #7aa2f7;
      --row-bg:   #333333;
      --dim:      #8a8a8a;
      --border:   #444444;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: 'Courier New', Courier, monospace;
      font-size: 14px;
      padding: 2rem 2.5rem;
    }}
    header {{
      border-bottom: 1px solid var(--border);
      padding-bottom: 1rem;
      margin-bottom: 1.5rem;
      display: flex;
      align-items: baseline;
      gap: 1.5rem;
    }}
    h1 {{
      color: var(--accent);
      font-size: 1.5rem;
      letter-spacing: 0.05em;
    }}
    .meta {{
      color: var(--dim);
      font-size: 0.85rem;
    }}
    .meta strong {{
      color: var(--text);
    }}
    #status {{
      margin-bottom: 1.5rem;
      color: var(--dim);
      font-size: 0.85rem;
      min-height: 1.2em;
    }}
    #status.active {{
      color: var(--accent);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    th {{
      text-align: left;
      color: var(--dim);
      font-weight: normal;
      font-size: 0.8rem;
      padding: 0 0.75rem 0.5rem 0.75rem;
      border-bottom: 1px solid var(--border);
    }}
    td {{
      padding: 0.6rem 0.75rem;
      border-bottom: 1px solid #383838;
      vertical-align: middle;
    }}
    tr:first-child td {{
      background: #2f2f2f;
    }}
    .col-time  {{ color: var(--dim); width: 5.5rem; white-space: nowrap; }}
    .col-name  {{ color: var(--blue); width: 16rem; }}
    .col-title {{ }}
    .col-open  {{ width: 5rem; text-align: right; }}
    .open-btn {{
      background: #404040;
      color: var(--text);
      border: none;
      border-radius: 3px;
      padding: 0.2rem 0.65rem;
      cursor: pointer;
      font-family: inherit;
      font-size: 0.85rem;
    }}
    .open-btn:hover {{ background: #555; }}
    #empty {{
      color: var(--dim);
      padding: 2rem 0.75rem;
      font-size: 0.9rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>manuscripts</h1>
    <span class="meta">teacher: <strong>{teacher_name}</strong></span>
    <span class="meta" id="conn">connections: <strong id="conn-count">0</strong></span>
  </header>
  <div id="status">Waiting for submissions&hellip;</div>
  <table id="table" style="display:none">
    <thead>
      <tr>
        <th>time</th>
        <th>student</th>
        <th>title</th>
        <th></th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  <div id="empty">No submissions yet.</div>

  <script>
    const tbody  = document.getElementById('tbody');
    const table  = document.getElementById('table');
    const empty  = document.getElementById('empty');
    const status = document.getElementById('status');
    const connEl = document.getElementById('conn-count');
    let count = 0;

    let _es = null;
    function connect() {{
      if (_es) {{ _es.close(); _es = null; }}
      const es = _es = new EventSource('/events');

      es.addEventListener('submission', e => {{
        const d = JSON.parse(e.data);
        if (count === 0) {{
          table.style.display = '';
          empty.style.display = 'none';
        }}
        count++;
        const tr = document.createElement('tr');
        tr.innerHTML =
          '<td class="col-time">' + esc(d.time) + '</td>' +
          '<td class="col-name">' + esc(d.student) + '</td>' +
          '<td class="col-title">' + esc(d.title) + '</td>' +
          '<td class="col-open"><button class="open-btn" ' +
            'onclick="openFile(this,' + JSON.stringify(d.path) + ')">open</button></td>';
        tbody.prepend(tr);
        status.textContent = d.student + ' submitted \u201c' + d.title + '\u201d';
        status.className = 'active';
        setTimeout(() => {{ status.textContent = 'Waiting for submissions\u2026'; status.className = ''; }}, 4000);
      }});

      es.addEventListener('count', e => {{
        connEl.textContent = e.data;
      }});

      es.onerror = () => setTimeout(connect, 3000);
    }}

    function openFile(btn, path) {{
      console.log('[open] path:', path);
      btn.disabled = true;
      fetch('/open?path=' + encodeURIComponent(path))
        .then(r => {{ console.log('[open] status:', r.status); return r.json(); }})
        .then(d => {{ console.log('[open] result:', JSON.stringify(d)); if (!d.ok) btn.disabled = false; }})
        .catch(e => {{ console.log('[open] error:', e); btn.disabled = false; }});
    }}

    function esc(s) {{
      return String(s)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;')
        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }}

    connect();
  </script>
</body>
</html>
"""

# ── Config ───────────────────────────────────────────────────────────────────

_CONFIG_FILE = Path.home() / ".config" / "manuscripts" / "teacher.json"


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(cfg: dict) -> None:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def _get_teacher_name() -> str:
    cfg = _load_config()
    if cfg.get("name"):
        return cfg["name"]
    try:
        name = input("Your name (shown to students): ").strip()
    except (EOFError, KeyboardInterrupt):
        name = ""
    if not name:
        name = "Teacher"
    cfg["name"] = name
    _save_config(cfg)
    return name


# ── Network helpers ──────────────────────────────────────────────────────────

def _get_local_ip() -> str:
    """Return the primary LAN IP (not 127.0.0.1)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


_DEFAULT_PORT = 8765


def _find_free_port() -> int:
    """Try the default port first, fall back to a random free one."""
    for port in (_DEFAULT_PORT, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return _DEFAULT_PORT  # unreachable


# ── SSE manager ──────────────────────────────────────────────────────────────

class SSEManager:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []

    def connect(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.append(q)
        return q

    def disconnect(self, q: asyncio.Queue) -> None:
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    async def broadcast(self, event: str, data: str) -> None:
        dead = []
        for q in list(self._queues):
            try:
                q.put_nowait(f"event: {event}\ndata: {data}\n\n")
            except Exception:
                dead.append(q)
        for q in dead:
            self.disconnect(q)

    @property
    def count(self) -> int:
        return len(self._queues)


# ── HTTP handlers ────────────────────────────────────────────────────────────

async def handle_index(request: web.Request) -> web.Response:
    return web.Response(text=request.app["html"], content_type="text/html")


async def handle_events(request: web.Request) -> web.StreamResponse:
    sse: SSEManager = request.app["sse"]
    q = sse.connect()
    resp = web.StreamResponse(headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
    await resp.prepare(request)
    # Send current count to new client immediately
    await resp.write(f"event: count\ndata: {sse.count}\n\n".encode())
    # Broadcast updated count to all
    await sse.broadcast("count", str(sse.count))
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=20.0)
                await resp.write(chunk.encode())
            except asyncio.TimeoutError:
                # Send keepalive comment to hold the connection open
                await resp.write(b": keepalive\n\n")
    except ConnectionResetError:
        pass
    finally:
        sse.disconnect(q)
        await sse.broadcast("count", str(sse.count))
    return resp


async def handle_submit(request: web.Request) -> web.Response:
    sse: SSEManager = request.app["sse"]
    try:
        reader = await request.multipart()
        student = ""
        title = ""
        file_bytes = b""
        ext = ".pdf"

        async for part in reader:
            if part.name == "student":
                student = (await part.read()).decode("utf-8", errors="replace").strip()
            elif part.name == "title":
                title = (await part.read()).decode("utf-8", errors="replace").strip()
            elif part.name == "file":
                file_bytes = await part.read()
                ct = part.headers.get("Content-Type", "application/pdf")
                if "markdown" in ct or "text/plain" in ct:
                    ext = ".md"

        student = student or "Unknown Student"
        title = title or "Untitled"

        date_str = datetime.now().strftime("%Y-%m-%d")
        save_dir = Path.home() / "Downloads" / "Submissions" / date_str
        save_dir.mkdir(parents=True, exist_ok=True)

        safe_student = re.sub(r"[^\w\s\-]", "", student).strip()[:40]
        safe_title = re.sub(r"[^\w\s\-]", "", title).strip()[:40]
        dest = save_dir / f"{safe_student} - {safe_title}{ext}"
        if dest.exists():
            stem, suffix, i = dest.stem, dest.suffix, 2
            while dest.exists():
                dest = save_dir / f"{stem} ({i}){suffix}"
                i += 1

        dest.write_bytes(file_bytes)

        event_data = json.dumps({
            "time": datetime.now().strftime("%H:%M"),
            "student": student,
            "title": title,
            "path": str(dest),
        })
        await sse.broadcast("submission", event_data)

        return web.json_response({"ok": True, "saved": str(dest)})
    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=500)


async def handle_open(request: web.Request) -> web.Response:
    raw = request.rel_url.query.get("path", "")
    print(f"[open] raw={repr(raw)}", flush=True)
    try:
        dest = Path(raw).resolve()
        allowed = (Path.home() / "Downloads" / "Submissions").resolve()
        print(f"[open] dest={dest}  allowed={allowed}  ok={str(dest).startswith(str(allowed))}", flush=True)
        if not str(dest).startswith(str(allowed)):
            return web.json_response({"ok": False, "error": "Forbidden"}, status=403)
        if not dest.exists():
            print(f"[open] file not found", flush=True)
            return web.json_response({"ok": False, "error": "Not found"}, status=404)
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", str(dest)])
        elif system == "Windows":
            os.startfile(str(dest))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(dest)])
        return web.json_response({"ok": True})
    except Exception as exc:
        print(f"[open] exception: {exc}", flush=True)
        return web.json_response({"ok": False, "error": str(exc)}, status=500)


# ── mDNS advertisement ───────────────────────────────────────────────────────

async def advertise_mdns(
    teacher_name: str,
    port: int,
    zc: AsyncZeroconf,
) -> AsyncServiceInfo:
    hostname = socket.gethostname()
    info = AsyncServiceInfo(
        type_="_manuscripts._tcp.local.",
        name=f"{teacher_name}._manuscripts._tcp.local.",
        addresses=[socket.inet_aton(_get_local_ip())],
        port=port,
        properties={
            "teacher": teacher_name,
            "version": "1",
        },
        server=f"{hostname}.local.",
    )
    await zc.async_register_service(info)
    return info


# ── Server setup ─────────────────────────────────────────────────────────────

async def run_server(teacher_name: str, port: int) -> web.AppRunner:
    sse = SSEManager()
    app = web.Application()
    app["sse"] = sse
    app["html"] = HTML_PAGE.format(teacher_name=teacher_name)
    app.router.add_get("/", handle_index)
    app.router.add_get("/events", handle_events)
    app.router.add_post("/submit", handle_submit)
    app.router.add_get("/open", handle_open)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    return runner


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    teacher_name = _get_teacher_name()
    port = _find_free_port()
    url = f"http://localhost:{port}/"

    print(f"\nmanuscripts-teacher")
    print(f"  teacher : {teacher_name}")
    print(f"  address : {url}")
    print(f"\nPress Ctrl+C to stop.\n")

    async def _run() -> None:
        runner = await run_server(teacher_name, port)
        zc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        info = await advertise_mdns(teacher_name, port, zc)
        webbrowser.open(url)
        try:
            await asyncio.sleep(float("inf"))
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            await zc.async_unregister_service(info)
            await zc.async_close()
            await runner.cleanup()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
