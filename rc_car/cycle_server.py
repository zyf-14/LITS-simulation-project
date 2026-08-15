# === cycle_server.py ===
# Minimal local HTTP control server wrapping track_run.py/reset_to_home.py, so
# the terminal Pi's monitoring webpage can start a cycle (or a HOME reset) and
# poll its status remotely. No external deps - stdlib http.server + subprocess
# only.
#
# Endpoints:
#   GET  /status  -> {"running": bool, "mode": "track_run"|"reset"|None,
#                      "last_result": "success"|"aborted"|null,
#                      "last_line": "<most recent stdout line, or null>"}
#   POST /start   -> starts track_run.py (full forward+return cycle) if
#                    nothing is already running.
#   POST /reset   -> starts reset_to_home.py (reverse-only recovery from a
#                    denied entry). If a track_run.py cycle is currently
#                    mid-wait (e.g. stuck at trigger1 after a denied entry,
#                    waiting out its 60s gate-open timeout), interrupts it
#                    first (SIGINT - same clean GPIO-releasing shutdown as
#                    Ctrl-C) instead of waiting for it to time out on its own,
#                    so a denied vehicle can be reset immediately.
#   Both POST endpoints return {"started": true} or {"error": "already running"}.
#   /start and /reset share the same process slot - only one of them (or a
#   cycle already in progress) can run at a time, since it's one physical car.

import json
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8765
SCRIPT_DIR = "/home/pi/Desktop/codev3"

state = {
    "process": None,
    "mode": None,           # "track_run" | "reset" | None
    "last_result": None,    # "success" | "aborted" | None
    "last_line": None,
}
state_lock = threading.Lock()


def _reader_thread(proc):
    for raw_line in proc.stdout:
        line = raw_line.rstrip("\n")
        with state_lock:
            state["last_line"] = line
    proc.wait()
    with state_lock:
        state["last_result"] = "success" if proc.returncode == 0 else "aborted"
        state["process"] = None
        state["mode"] = None


def start_process(script, mode):
    with state_lock:
        if state["process"] is not None:
            return False
        proc = subprocess.Popen(
            ["python3", "-u", script],
            cwd=SCRIPT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        state["process"] = proc
        state["mode"] = mode
        state["last_result"] = None
        state["last_line"] = None
    threading.Thread(target=_reader_thread, args=(proc,), daemon=True).start()
    return True


def interrupt_current(timeout_s=10):
    """Sends SIGINT to whatever's currently running (if anything) and waits
    for _reader_thread to notice it exited and clear state.process. track_run.py
    and reset_to_home.py both catch KeyboardInterrupt and release GPIO/stop the
    motor in a finally block, same as a manual Ctrl-C, so this is safe to fire
    at any point in either script."""
    with state_lock:
        proc = state["process"]
    if proc is None:
        return True
    proc.send_signal(signal.SIGINT)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with state_lock:
            if state["process"] is None:
                return True
        time.sleep(0.1)
    return False


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/status":
            with state_lock:
                running = state["process"] is not None
                self._send_json({
                    "running": running,
                    "mode": state["mode"],
                    "last_result": state["last_result"],
                    "last_line": state["last_line"],
                })
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/start":
            if start_process("track_run.py", "track_run"):
                self._send_json({"started": True})
            else:
                self._send_json({"error": "already running"}, 409)
        elif self.path == "/reset":
            interrupt_current()
            if start_process("reset_to_home.py", "reset"):
                self._send_json({"started": True})
            else:
                self._send_json({"error": "already running"}, 409)
        else:
            self._send_json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        print(f"[cycle_server] {self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    print(f"[cycle_server] Listening on 0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
