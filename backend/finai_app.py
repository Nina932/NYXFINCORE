"""
FinAI Desktop Application — Standalone Entry Point
Built with PyInstaller into a single distributable folder.
All dependencies, static files, and the FastAPI server are bundled.
"""
import sys
import os
import multiprocessing

# Fix for PyInstaller frozen multiprocessing
multiprocessing.freeze_support()

# ── Resolve base path (works both frozen .exe and dev mode) ──────
if getattr(sys, 'frozen', False):
    # Running as compiled .exe
    BASE_DIR = sys._MEIPASS
    APP_DIR = os.path.dirname(sys.executable)
    IS_FROZEN = True
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = BASE_DIR
    IS_FROZEN = False

# Add app directory to path so imports work
sys.path.insert(0, BASE_DIR)

import subprocess
import time
import socket
import logging
import atexit
import threading
import signal

# ── Logging ──────────────────────────────────────────────────────
LOG_FILE = os.path.join(APP_DIR, "finai_desktop.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
log = logging.getLogger("FinAI")

# ── Configuration ────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 9200
TITLE = "FinAI \u00b7 Financial Intelligence OS"
WIDTH = 1440
HEIGHT = 900

server_thread = None
server_ready = threading.Event()


def is_port_open(port, host="127.0.0.1"):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((host, port))
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def find_free_port(start=9200, end=9210):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    return start


def run_server(port):
    """Run FastAPI/uvicorn server in-process."""
    try:
        # Set environment
        os.environ["AGENT_MODE"] = "multi"
        os.environ["PYTHONIOENCODING"] = "utf-8"

        # Change to the app directory so relative paths work
        if IS_FROZEN:
            os.chdir(BASE_DIR)

        import uvicorn
        from main import app

        log.info(f"Starting embedded server on {HOST}:{port}")
        server_ready.set()

        uvicorn.run(
            app,
            host=HOST,
            port=port,
            log_level="warning",
            access_log=False,
        )
    except Exception as e:
        log.error(f"Server error: {e}")
        import traceback
        traceback.print_exc()


def wait_for_server(port, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(port):
            return True
        time.sleep(0.5)
        elapsed = int(time.time() - start)
        if elapsed > 0 and elapsed % 10 == 0:
            log.info(f"  Waiting for server... ({elapsed}s)")
    return False


SPLASH_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#040507;color:#c8d4e8;font-family:'Segoe UI',sans-serif;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;overflow:hidden}
.logo{font-size:42px;font-weight:800;background:linear-gradient(135deg,#38bdf8,#818cf8);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}
.sub{font-size:11px;color:#5a6a85;letter-spacing:3px;text-transform:uppercase;margin-bottom:32px}
.bar-wrap{width:220px;height:3px;background:#10121b;border-radius:2px;overflow:hidden}
.bar{height:100%;width:0%;background:linear-gradient(90deg,#38bdf8,#818cf8);border-radius:2px;
  animation:load 8s ease-in-out forwards}
@keyframes load{0%{width:0%}30%{width:40%}60%{width:65%}80%{width:80%}100%{width:95%}}
.status{margin-top:16px;font-size:10px;color:#3a4558;font-family:monospace}
</style></head><body>
<div class="logo">FinAI</div>
<div class="sub">Financial Intelligence OS</div>
<div class="bar-wrap"><div class="bar"></div></div>
<div class="status">Initializing server...</div>
</body></html>"""


def main():
    import webview

    log.info("=" * 60)
    log.info("FinAI Desktop Application")
    log.info(f"  Frozen: {IS_FROZEN}")
    log.info(f"  BASE_DIR: {BASE_DIR}")
    log.info(f"  APP_DIR:  {APP_DIR}")
    log.info("=" * 60)

    port = find_free_port(PORT)
    already_running = is_port_open(port)

    if already_running:
        log.info(f"Server already running on port {port}")
    else:
        # Start server in background thread
        server_thread = threading.Thread(
            target=run_server, args=(port,), daemon=True
        )
        server_thread.start()

    # Create main window — starts with splash HTML, then navigates to app
    window = webview.create_window(
        title=TITLE,
        html=SPLASH_HTML if not already_running else None,
        url=f"http://{HOST}:{port}/static/FinAI_Platform_v7.html" if already_running else None,
        width=WIDTH,
        height=HEIGHT,
        min_size=(1024, 600),
        resizable=True,
        text_select=True,
        confirm_close=False,
    )

    def on_start():
        """Called after webview.start() — runs in background thread."""
        if not already_running:
            log.info("Waiting for backend server...")
            if not wait_for_server(port, timeout=120):
                log.error("Server failed to start!")
                try:
                    window.evaluate_js("""
                        document.querySelector('.status').textContent = 'ERROR: Server failed to start';
                        document.querySelector('.bar').style.background = '#f87171';
                    """)
                except Exception:
                    pass
                time.sleep(3)
                os._exit(1)

            log.info("Server ready! Loading application...")
            # Navigate the same window to the app URL
            url = f"http://{HOST}:{port}/static/FinAI_Platform_v7.html"
            try:
                window.load_url(url)
            except Exception:
                pass

        # Wait for page to load, then inject desktop flag
        time.sleep(3)
        try:
            window.evaluate_js(f"""
                window.__FINAI_DESKTOP__ = true;
                document.title = 'FinAI \\u00b7 Financial Intelligence OS';
                console.log('[FinAI] Desktop mode active, port={port}');
            """)
        except Exception:
            pass

    log.info("Opening FinAI window...")

    # Single webview.start() call — the ONLY one allowed per process
    webview.start(
        func=on_start,
        debug=("--debug" in sys.argv),
        gui="edgechromium",
        private_mode=False,
    )

    log.info("Window closed. Exiting.")
    os._exit(0)


if __name__ == "__main__":
    main()
