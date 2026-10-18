"""A tiny stand-in for the CMS data API used by the bats tests.

    python fake_cms_api.py TOTAL_ROWS [flaky] PORT_FILE

Serves /data-api/v1/dataset/<id>/data/stats and /data?size=&offset= with synthetic rows. With "flaky", the first
request for each page answers 503.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

TOTAL = int(sys.argv[1])
FLAKY = len(sys.argv) > 3 and sys.argv[2] == "flaky"
PORT_FILE = sys.argv[-1]
seen: set[str] = set()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # keep test output clean
        return

    def _json(self, status: int, body: object) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path.endswith("/data/stats"):
            self._json(200, {"found_rows": TOTAL, "total_rows": TOTAL * 10})
            return
        if url.path.endswith("/data"):
            if FLAKY and url.query not in seen:
                seen.add(url.query)
                self._json(503, {"error": "try again"})
                return
            size = int(query.get("size", ["5000"])[0])
            offset = int(query.get("offset", ["0"])[0])
            rows = [
                {"Prscrbr_NPI": str(1000000000 + i), "Tot_Clms": str(i + 11)}
                for i in range(offset, min(offset + size, TOTAL))
            ]
            self._json(200, rows)
            return
        self._json(404, {"error": "not found"})


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
with open(PORT_FILE, "w", encoding="utf-8") as fh:
    fh.write(str(server.server_address[1]))
server.serve_forever()
