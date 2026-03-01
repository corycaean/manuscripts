#!/usr/bin/env python3
"""
manuscripts-receiver — receives PDF submissions from peers over LAN.

A system-tray GUI app (macOS and Windows) that receives PDF submissions
from manuscripts.py and shows them in a browser dashboard.
"""
from __future__ import annotations

import asyncio
import json
import platform
import re
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import pystray
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw

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
    @font-face {{
      font-family: 'JetBrains Mono';
      src: url('/font/JetBrainsMono-Regular.ttf') format('truetype');
      font-weight: 400;
    }}
    :root {{
      --bg:       #2a2a2a;
      --text:     #e0e0e0;
      --accent:   #e0af68;
      --blue:     #7aa2f7;
      --dim:      #777777;
      --border:   #444444;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: 'JetBrains Mono', 'Courier New', monospace;
      font-size: 14px;
      padding: 2rem 2.5rem 4rem 2.5rem;
    }}
    header {{
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.6rem;
      margin-bottom: 1.5rem;
      display: flex;
      align-items: baseline;
    }}
    h1 {{
      color: var(--accent);
      font-size: 1.5rem;
      letter-spacing: 0.05em;
      font-weight: bold;
    }}
    .header-sep {{
      color: var(--dim);
      margin: 0 0.5rem;
    }}
    #status {{
      color: var(--dim);
      font-size: 0.85rem;
    }}
    #status.active {{
      color: var(--text);
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
    #empty {{
      color: var(--dim);
      padding: 2rem 0.75rem;
      font-size: 0.9rem;
    }}
    footer {{
      position: fixed;
      bottom: 1.5rem;
      left: 2.5rem;
      display: flex;
      gap: 1.5rem;
      color: var(--dim);
      font-size: 0.8rem;
    }}
    footer strong {{
      color: var(--text);
    }}
  </style>
</head>
<body>
  <header>
    <h1>manuscripts</h1>
    <span class="header-sep">·</span>
    <span id="status">receiver</span>
  </header>
  <table id="table" style="display:none">
    <thead>
      <tr>
        <th>time</th>
        <th>student</th>
        <th>title</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  <div id="empty">No submissions received yet.</div>

  <footer>
    <span>teacher: <strong>{teacher_name}</strong></span>
    <span>connections: <strong id="conn-count">0</strong></span>
  </footer>

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
          '<td class="col-title">' + esc(d.title) + '</td>';
        tbody.prepend(tr);
        status.textContent = d.student + ' submitted \u201c' + d.title + '\u201d';
        status.className = 'active';
        setTimeout(() => {{ status.textContent = 'receiver'; status.className = ''; }}, 4000);
      }});

      es.addEventListener('count', e => {{
        connEl.textContent = e.data;
      }});

      es.onerror = () => setTimeout(connect, 3000);
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

_CONFIG_FILE = Path.home() / ".config" / "manuscripts" / "receiver.json"
_OLD_CONFIG_FILE = Path.home() / ".config" / "manuscripts" / "share.json"

# Migrate share.json → receiver.json on first run
if _OLD_CONFIG_FILE.exists() and not _CONFIG_FILE.exists():
    _OLD_CONFIG_FILE.rename(_CONFIG_FILE)


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(cfg: dict) -> None:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


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


# ── Setup dialog ─────────────────────────────────────────────────────────────

def show_setup_dialog() -> tuple[str, str] | None:
    """Show the name/password dialog. Returns (name, password) or None if cancelled."""
    cfg = _load_config()
    result: list[tuple[str, str] | None] = [None]

    root = tk.Tk()
    root.title("manuscripts-receiver")
    root.resizable(False, False)

    # Center on screen
    w, h = 380, 200
    root.update_idletasks()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill=tk.BOTH, expand=True)
    frame.columnconfigure(1, weight=1)

    ttk.Label(frame, text="Your name:").grid(row=0, column=0, sticky=tk.W, pady=7)
    name_var = tk.StringVar(value=cfg.get("name", ""))
    name_entry = ttk.Entry(frame, textvariable=name_var, width=26)
    name_entry.grid(row=0, column=1, sticky=tk.EW, padx=(12, 0), pady=7)

    ttk.Label(frame, text="Password:").grid(row=1, column=0, sticky=tk.W, pady=7)
    pw_var = tk.StringVar(value=cfg.get("password", ""))
    pw_entry = ttk.Entry(frame, textvariable=pw_var, width=26, show="\u2022")
    pw_entry.grid(row=1, column=1, sticky=tk.EW, padx=(12, 0), pady=7)
    ttk.Label(frame, text="leave blank for none", foreground="gray").grid(
        row=2, column=1, sticky=tk.W, padx=(12, 0)
    )

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=3, column=0, columnspan=2, pady=(18, 0), sticky=tk.E)

    def _ok(event=None):
        name = name_var.get().strip() or "Teacher"
        pw = pw_var.get().strip()
        cfg["name"] = name
        if pw:
            cfg["password"] = pw
        elif "password" in cfg:
            del cfg["password"]
        _save_config(cfg)
        result[0] = (name, pw)
        root.destroy()

    def _cancel(event=None):
        root.destroy()

    ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_frame, text="Start", command=_ok).pack(side=tk.LEFT)

    root.bind("<Return>", _ok)
    root.bind("<Escape>", _cancel)
    root.protocol("WM_DELETE_WINDOW", _cancel)
    name_entry.focus_set()
    root.mainloop()

    return result[0]


# ── Tray icon image ──────────────────────────────────────────────────────────

def _load_font(size: int, weight: str = "Light") -> "ImageFont.FreeTypeFont | ImageFont.ImageFont":
    from PIL import ImageFont
    names = [f"JetBrainsMono-{weight}.ttf", "JetBrainsMono-Regular.ttf"]
    candidates = []
    for name in names:
        candidates += [
            Path(__file__).parent / name,
            *(
                [Path(sys._MEIPASS) / name]
                if hasattr(sys, "_MEIPASS") else []
            ),
            Path.home() / "Library" / "Fonts" / name,
            Path(f"/Library/Fonts/{name}"),
            Path(f"/usr/share/fonts/truetype/jetbrains-mono/{name}"),
        ]
    for p in candidates:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _is_dark_mode() -> bool:
    """Return True when macOS is in dark mode."""
    if sys.platform != "darwin":
        return True  # non-Mac: default to white icon
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True, text=True, timeout=2,
        )
        return result.stdout.strip().lower() == "dark"
    except Exception:
        return False


def _make_icon_image() -> Image.Image:
    dark = _is_dark_mode()
    fill = "#FFFFFF" if dark else "#000000"
    outline = (255, 255, 255, 60) if dark else (0, 0, 0, 60)

    size = 128
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, size - 4, size - 4], radius=14,
                           outline=outline, width=3)
    font = _load_font(80, weight="Light")
    text = "m."
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)
    return img


def _watch_appearance() -> None:
    """Poll for macOS appearance changes and redraw the tray icon."""
    current = _is_dark_mode()
    while True:
        time.sleep(3)
        new = _is_dark_mode()
        if new != current:
            current = new
            if _tray_icon is not None:
                _tray_icon.icon = _make_icon_image()


def _setup_tray(icon: "pystray.Icon") -> None:
    icon.visible = True
    if sys.platform == "darwin":
        threading.Thread(target=_watch_appearance, daemon=True).start()


# ── Global server state (shared across threads) ───────────────────────────────

_submission_count = 0
_dashboard_url = ""
_asyncio_loop: asyncio.AbstractEventLoop | None = None
_stop_event: asyncio.Event | None = None
_server_ready = threading.Event()
_tray_icon: pystray.Icon | None = None
_password_ref: list[str] = [""]  # mutable so handle_submit always sees current value
_mdns_zc: AsyncZeroconf | None = None
_mdns_info: AsyncServiceInfo | None = None
_mdns_teacher_name: str = ""


# ── Tray menu & actions ───────────────────────────────────────────────────────

def _open_dashboard(icon: pystray.Icon, item: pystray.MenuItem) -> None:
    webbrowser.open(_dashboard_url)


def _quit_app(icon: pystray.Icon, item: pystray.MenuItem) -> None:
    if _asyncio_loop and _stop_event:
        _asyncio_loop.call_soon_threadsafe(_stop_event.set)
    icon.stop()


def _make_menu() -> pystray.Menu:
    def _count_label(item: pystray.MenuItem) -> str:
        n = _submission_count
        return f"{n} submission{'s' if n != 1 else ''} received"

    def _pw_label(item: pystray.MenuItem) -> str:
        return "Change Password  [set]" if _password_ref[0] else "Change Password  [none]"

    return pystray.Menu(
        pystray.MenuItem(_count_label, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open Dashboard", _open_dashboard),
        pystray.MenuItem(_pw_label, _change_password),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _quit_app),
    )


def _prompt_password() -> str | None:
    """Show a password-entry dialog. Returns the new password, "" to clear, or None if cancelled."""
    if platform.system() == "Darwin":
        r = subprocess.run(
            ["osascript", "-e",
             'display dialog "New submission password (leave blank to remove):" '
             'default answer "" with hidden answer '
             'buttons {"Cancel", "OK"} default button "OK"'],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return None
        for part in r.stdout.strip().split(", "):
            if part.startswith("text returned:"):
                return part[len("text returned:"):]
        return ""
    else:
        # Windows: tkinter works fine from a non-main thread
        from tkinter import simpledialog
        result: list[str | None] = [None]
        done = threading.Event()

        def _show() -> None:
            root = tk.Tk()
            root.withdraw()
            pw = simpledialog.askstring(
                "Change Password",
                "New submission password\n(leave blank to remove):",
                show="\u2022",
                parent=root,
            )
            root.destroy()
            result[0] = pw
            done.set()

        threading.Thread(target=_show, daemon=True).start()
        done.wait(timeout=60)
        return result[0]


async def _reregister_mdns(new_pw: str) -> None:
    """Re-register the mDNS service with an updated auth flag."""
    global _mdns_info
    if _mdns_zc is None or _mdns_info is None:
        return
    await _mdns_zc.async_unregister_service(_mdns_info)
    new_info = AsyncServiceInfo(
        type_="_manuscripts._tcp.local.",
        name=f"{_mdns_teacher_name}._manuscripts._tcp.local.",
        addresses=_mdns_info.addresses,
        port=_mdns_info.port,
        properties={
            "teacher": _mdns_teacher_name,
            "version": "1",
            "auth": "1" if new_pw else "0",
        },
        server=_mdns_info.server,
    )
    await _mdns_zc.async_register_service(new_info)
    _mdns_info = new_info


def _change_password(icon: pystray.Icon, item: pystray.MenuItem) -> None:
    new_pw = _prompt_password()
    if new_pw is None:
        return  # cancelled
    new_pw = new_pw.strip()
    _password_ref[0] = new_pw
    cfg = _load_config()
    if new_pw:
        cfg["password"] = new_pw
    elif "password" in cfg:
        del cfg["password"]
    _save_config(cfg)
    # Update the mDNS auth flag so clients see the change immediately
    if _asyncio_loop:
        asyncio.run_coroutine_threadsafe(_reregister_mdns(new_pw), _asyncio_loop)


# ── Submission callback (called from asyncio thread) ─────────────────────────

def _on_submission() -> None:
    global _submission_count
    _submission_count += 1


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


async def handle_font(request: web.Request) -> web.Response:
    """Serve the JetBrains Mono font for the dashboard."""
    font_name = "JetBrainsMono-Regular.ttf"
    candidates = [
        *(
            [Path(sys._MEIPASS) / font_name]
            if hasattr(sys, "_MEIPASS") else []
        ),
        Path(__file__).parent / font_name,
    ]
    for p in candidates:
        if p.exists():
            return web.FileResponse(p, headers={"Cache-Control": "max-age=86400"})
    return web.Response(status=404)


async def handle_events(request: web.Request) -> web.StreamResponse:
    sse: SSEManager = request.app["sse"]
    q = sse.connect()
    resp = web.StreamResponse(headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
    await resp.prepare(request)
    await resp.write(f"event: count\ndata: {sse.count}\n\n".encode())
    await sse.broadcast("count", str(sse.count))
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=20.0)
                await resp.write(chunk.encode())
            except asyncio.TimeoutError:
                await resp.write(b": keepalive\n\n")
    except ConnectionResetError:
        pass
    finally:
        sse.disconnect(q)
        await sse.broadcast("count", str(sse.count))
    return resp


async def handle_submit(request: web.Request) -> web.Response:
    sse: SSEManager = request.app["sse"]
    required_password: str = request.app["password_ref"][0]
    on_sub = request.app["on_submission"]
    try:
        reader = await request.multipart()
        student = ""
        title = ""
        file_bytes = b""
        ext = ".pdf"
        submitted_password = ""

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
            elif part.name == "password":
                submitted_password = (await part.read()).decode("utf-8", errors="replace").strip()

        if required_password and submitted_password != required_password:
            return web.json_response({"ok": False, "error": "Incorrect password"}, status=401)

        student = student or "Unknown Student"
        title = title or "Untitled"

        date_str = datetime.now().strftime("%Y-%m-%d")
        save_dir = Path.home() / "Downloads" / "Submissions" / date_str
        save_dir.mkdir(parents=True, exist_ok=True)

        last_name = student.strip().split()[-1] if student.strip() else "Unknown"
        safe_last = re.sub(r"[^\w\-]", "", last_name)[:30]
        safe_title = re.sub(r"[^\w\s\-]", "", title).strip()[:50]
        dest = save_dir / f"{safe_last}-{safe_title}{ext}"
        if dest.exists():
            stem, suffix, i = dest.stem, dest.suffix, 2
            while dest.exists():
                dest = save_dir / f"{stem} ({i}){suffix}"
                i += 1

        dest.write_bytes(file_bytes)
        on_sub()

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


# ── mDNS advertisement ───────────────────────────────────────────────────────

async def advertise_mdns(
    teacher_name: str,
    port: int,
    zc: AsyncZeroconf,
    password: str = "",
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
            "auth": "1" if password else "0",
        },
        server=f"{hostname}.local.",
    )
    await zc.async_register_service(info)
    return info


# ── Server setup ─────────────────────────────────────────────────────────────

async def run_server(
    teacher_name: str, port: int, password_ref: list[str] | None = None, on_submission=None
) -> web.AppRunner:
    sse = SSEManager()
    app = web.Application()
    app["sse"] = sse
    app["password_ref"] = password_ref if password_ref is not None else _password_ref
    app["html"] = HTML_PAGE.format(teacher_name=teacher_name)
    app["on_submission"] = on_submission or (lambda: None)
    app.router.add_get("/", handle_index)
    app.router.add_get("/events", handle_events)
    app.router.add_post("/submit", handle_submit)
    app.router.add_get("/font/JetBrainsMono-Regular.ttf", handle_font)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    return runner


# ── Asyncio server thread ────────────────────────────────────────────────────

def _run_server_thread(teacher_name: str, port: int, password: str) -> None:
    global _asyncio_loop, _stop_event, _mdns_zc, _mdns_info, _mdns_teacher_name
    _password_ref[0] = password
    _mdns_teacher_name = teacher_name

    async def _main() -> None:
        global _asyncio_loop, _stop_event, _mdns_zc, _mdns_info
        _asyncio_loop = asyncio.get_running_loop()
        _stop_event = asyncio.Event()

        runner = await run_server(teacher_name, port, _password_ref, _on_submission)
        zc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        info = await advertise_mdns(teacher_name, port, zc, password)
        _mdns_zc = zc
        _mdns_info = info

        _server_ready.set()
        await _stop_event.wait()

        await zc.async_unregister_service(info)
        await zc.async_close()
        await runner.cleanup()

    asyncio.run(_main())


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    global _dashboard_url, _tray_icon

    setup = show_setup_dialog()
    if setup is None:
        sys.exit(0)
    teacher_name, password = setup

    port = _find_free_port()
    _dashboard_url = f"http://localhost:{port}/"

    # Start aiohttp + zeroconf in background thread
    server_thread = threading.Thread(
        target=_run_server_thread,
        args=(teacher_name, port, password),
        daemon=True,
    )
    server_thread.start()
    _server_ready.wait(timeout=10)

    webbrowser.open(_dashboard_url)

    # Run system tray icon on main thread (blocks until Quit)
    _tray_icon = pystray.Icon(
        "manuscripts-receiver",
        _make_icon_image(),
        "manuscripts-receiver",
        menu=_make_menu(),
    )
    _tray_icon.run(_setup_tray)


if __name__ == "__main__":
    main()
