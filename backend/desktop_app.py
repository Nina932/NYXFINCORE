"""
FinAI Desktop Application
Launches FastAPI backend as subprocess + native desktop window using pywebview.
Run with: venv2\\Scripts\\python desktop_app.py
Or double-click: FinAI.bat
"""
import sys
import os
import subprocess
import time
import socket
import logging
import atexit

# ── Resolve paths ────────────────────────────────────────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Configure logging ────────────────────────────────────────────
LOG_FILE = os.path.join(APP_DIR, "finai_desktop.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]
)
log = logging.getLogger("FinAI-Desktop")

# Find Python interpreter for the server subprocess
VENV_PYTHON = os.path.join(APP_DIR, "venv2", "Scripts", "python.exe")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = os.path.join(APP_DIR, "venv2", "Scripts", "python3.exe")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable
    log.warning(f"venv2 not found, using system Python: {VENV_PYTHON}")

# ── Configuration ────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 9200
TITLE = "FinAI \u00b7 Financial Intelligence OS"
WIDTH = 1440
HEIGHT = 900

server_process = None


def find_free_port(start=9200, end=9210):
    """Find a free port in range."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    return start


def is_port_open(port):
    """Check if port is accepting connections."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((HOST, port))
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def wait_for_server(port, timeout=120):
    """Wait until the server is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(port):
            return True
        time.sleep(0.5)
        elapsed = int(time.time() - start)
        if elapsed % 10 == 0 and elapsed > 0:
            log.info(f"  Still waiting... ({elapsed}s)")
    return False


def start_server(port):
    """Start FastAPI server as a separate subprocess."""
    global server_process
    env = os.environ.copy()
    env["AGENT_MODE"] = "multi"
    env["PYTHONIOENCODING"] = "utf-8"

    log.info(f"Starting FastAPI server on {HOST}:{port}")
    log.info(f"Python: {VENV_PYTHON}")
    log.info(f"Working dir: {APP_DIR}")

    server_process = subprocess.Popen(
        [VENV_PYTHON, "-m", "uvicorn", "main:app",
         "--host", HOST, "--port", str(port),
         "--log-level", "warning", "--no-access-log"],
        cwd=APP_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    log.info(f"Server PID: {server_process.pid}")


def cleanup_server():
    """Kill the server subprocess on exit."""
    global server_process
    if server_process and server_process.poll() is None:
        log.info("Shutting down backend server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
        log.info("Server stopped.")


def main():
    import webview

    log.info("=" * 60)
    log.info("FinAI Desktop Application Starting")
    log.info(f"  APP_DIR: {APP_DIR}")
    log.info(f"  Python:  {VENV_PYTHON}")
    log.info("=" * 60)

    port = find_free_port(PORT)

    # ── Check if server already running ──────────────────────────
    already_running = is_port_open(port)
    if already_running:
        log.info(f"Server already running on port {port}, reusing it")
    else:
        start_server(port)
        atexit.register(cleanup_server)

        log.info("Waiting for backend server to start...")
        log.info("(First launch may take 60-90 seconds for database initialization)")
        if not wait_for_server(port, timeout=120):
            log.error("Server failed to start within 120 seconds!")
            if server_process and server_process.poll() is not None:
                stderr_out = server_process.stderr.read().decode("utf-8", errors="replace")
                log.error(f"Server exit code: {server_process.returncode}")
                log.error(f"STDERR: {stderr_out[:3000]}")
            cleanup_server()
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    "FinAI server failed to start.\n\nCheck finai_desktop.log for details.",
                    "FinAI \u2014 Startup Error",
                    0x10
                )
            except Exception:
                pass
            sys.exit(1)

    log.info("Backend server is ready!")

    url = f"http://{HOST}:{port}/static/FinAI_Platform_v7.html"

    # ── Create native window ─────────────────────────────────────
    window = webview.create_window(
        title=TITLE,
        url=url,
        width=WIDTH,
        height=HEIGHT,
        min_size=(1024, 600),
        resizable=True,
        text_select=True,
        confirm_close=False,
    )

    def on_loaded():
        try:
            window.evaluate_js("""
                window.__FINAI_DESKTOP__ = true;
                document.title = 'FinAI \\u00b7 Financial Intelligence OS';
                document.querySelectorAll('[data-browser-only]').forEach(el => el.style.display='none');
                console.log('[FinAI Desktop] Native window loaded');
            """)
        except Exception:
            pass

    window.events.loaded += on_loaded
    log.info(f"Opening desktop window: {url}")

    # ── Start GUI event loop (blocking) ──────────────────────────
    webview.start(
        debug=("--debug" in sys.argv),
        gui="edgechromium",
        private_mode=False,
    )

    log.info("Desktop window closed. Shutting down.")
    if not already_running:
        cleanup_server()
    os._exit(0)


if __name__ == "__main__":
    main()
