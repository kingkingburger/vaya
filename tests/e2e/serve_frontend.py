"""Serve the Vite-built frontend for Playwright with a small Tauri IPC mock."""
import http.server
import os
import sys
import threading

DIST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dist"))

TAURI_IPC_MOCK = """
<script>
window.__TAURI_INTERNALS__ = {
  invoke: async function(command) {
    if (command === "get_backend_status") {
      const res = await fetch("http://127.0.0.1:8765/api/health");
      return await res.json();
    }
    if (command === "open_file_dialog") {
      return window.__testFilePath || null;
    }
    if (command === "open_output_folder") {
      return null;
    }
    throw new Error("Unknown Tauri command: " + command);
  }
};
</script>
"""


class PatchedHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that injects the Tauri IPC mock before app scripts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_GET(self):
        if self.path in ("/", "/index.html", "/index.html?"):
            index_path = os.path.join(DIST_DIR, "index.html")
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read().replace("</head>", f"{TAURI_IPC_MOCK}</head>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content.encode("utf-8"))))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            super().do_GET()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        pass  # Suppress log output during tests


def start_server(port=8766):
    """Start the test frontend server."""
    server = http.server.HTTPServer(("127.0.0.1", port), PatchedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    print(f"Serving patched frontend at http://127.0.0.1:{port}")
    server = start_server(port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
