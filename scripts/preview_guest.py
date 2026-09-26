"""Serve the embedded guest page with a fake API for visual development."""

from __future__ import annotations

import ast
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 4173
ROOT = Path(__file__).parents[1]
BRAND_ICON = ROOT / "custom_components" / "gate_pass" / "brand" / "icon.png"


def _guest_html() -> str:
    tree = ast.parse(
        (ROOT / "custom_components" / "gate_pass" / "server.py").read_text(
            encoding="utf-8"
        )
    )
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "GUEST_PAGE_HTML"
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError("GUEST_PAGE_HTML not found")


class PreviewHandler(BaseHTTPRequestHandler):
    """Return the guest page and deterministic fake API responses."""

    def do_GET(self) -> None:
        if self.path == "/gate-pass/assets/icon.png":
            encoded = BRAND_ICON.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        if self.path.endswith("/status"):
            self._json(
                {
                    "access_name": "Garage gate",
                    "action_label": "Tor öffnen",
                    "label": "Testgast",
                    "expires_at": "2026-07-13T22:00:00+02:00",
                    "remaining_uses": 1,
                }
            )
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_guest_html().encode("utf-8"))

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(content_length)
        self._json({"success": True, "remaining_uses": 0})

    def _json(self, data: dict[str, object]) -> None:
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        """Keep preview output quiet."""


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), PreviewHandler)
    print(f"Guest preview: http://127.0.0.1:{PORT}/gate-pass/guest/demo/secret")
    server.serve_forever()
