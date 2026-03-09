"""
Test frontend server that patches Electrobun's Electroview with a mock.
Serves the built frontend files with the Electroview class replaced.
"""
import http.server
import os
import re
import sys
import threading

BUILD_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "build", "dev-win-x64",
    "Vaya-dev", "Resources", "app", "views", "main"
)
MOCK_JS_PATH = os.path.join(os.path.dirname(__file__), "electrobun_mock.js")


def get_patched_main_js():
    """Read main.js and replace Electroview class with our mock."""
    main_js_path = os.path.join(BUILD_DIR, "main.js")
    with open(main_js_path, "r", encoding="utf-8") as f:
        js = f.read()

    with open(MOCK_JS_PATH, "r", encoding="utf-8") as f:
        mock_js = f.read()

    # Remove the original Electroview class definition and everything before it
    # that's related to Electrobun (RPC socket setup, encryption, etc.)
    # The built JS structure:
    #   1. createRPC function (we KEEP this)
    #   2. Electrobun internals: WEBVIEW_ID, RPC_SOCKET_PORT, Electroview class (we REPLACE)
    #   3. App code: var rpc = Electroview.defineRPC({...}); etc. (we KEEP)

    # Replace the Electroview class with our mock
    # Pattern: from "var WEBVIEW_ID" to just before "var rpc = Electroview.defineRPC"
    pattern = r'var WEBVIEW_ID = .*?class Electroview \{.*?\n\}'
    patched = re.sub(pattern, mock_js, js, count=1, flags=re.DOTALL)
    if patched == js:
        raise RuntimeError(
            "Failed to patch Electroview class — regex pattern did not match. "
            "The built main.js structure may have changed."
        )
    js = patched

    # Comment out initBackendStatus() — the mock's backendReady push handles this.
    # Keeping initBackendStatus active causes competing RPC requests that
    # interfere with the upload flow under load.
    js = js.replace(
        'initBackendStatus();',
        '// initBackendStatus(); -- handled by mock Electroview'
    )

    return js


class PatchedHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that serves patched frontend files."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BUILD_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/main.js" or self.path == "/main.js?":
            content = get_patched_main_js()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(content.encode("utf-8"))))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            # Add CORS headers for all responses
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
