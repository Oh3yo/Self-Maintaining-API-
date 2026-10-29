"""The API the demo repo depends on, which you control. Break it live in front of judges.

    python mock_api.py          start the server (leave this window open)
    python mock_api.py break    rename User.email -> email_address
    python mock_api.py reset    put it back
    python mock_api.py try      call it exactly like demo_repo/client.py does
"""
import json
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

URL = "http://localhost:8000"
state = {"field": "email"}


def spec():
    f = state["field"]
    user = {"type": "object", "required": ["id", f], "properties": {"id": {"type": "integer"}, f: {"type": "string"}}}
    ok = {"description": "ok", "content": {"application/json": {"schema": user}}}
    return {"openapi": "3.0.3", "info": {"title": "demo users api", "version": "1.0"},
            "paths": {"/v1/users/{id}": {"get": {"responses": {"200": ok}}}}}


class Handler(BaseHTTPRequestHandler):
    def _send(self, body, code=200):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/openapi.json":
            self._send(spec())
        elif self.path.startswith("/v1/users/"):
            self._send({"id": int(self.path.rsplit("/", 1)[1]), state["field"]: "tsu@example.com"})
        else:
            self._send({"error": "not found"}, 404)

    def do_POST(self):
        if self.path in ("/break", "/reset"):
            state["field"] = "email_address" if self.path == "/break" else "email"
            self._send({"user_field": state["field"]})
        else:
            self._send({"error": "not found"}, 404)

    def log_message(self, *a):  # keep the demo window quiet
        pass


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "serve":
        print(f"Mock API on {URL}  (spec at {URL}/openapi.json). Ctrl+C to stop.")
        HTTPServer(("localhost", 8000), Handler).serve_forever()
    elif cmd in ("break", "reset"):
        r = urllib.request.urlopen(urllib.request.Request(f"{URL}/{cmd}", method="POST"))
        print(f"{cmd}: the API now returns", json.load(r))
    elif cmd == "try":
        sys.path.insert(0, "demo_repo")
        sys.dont_write_bytecode = True  # else demo_repo/__pycache__ makes the repo look dirty to the PR step
        import client
        client.BASE = URL
        try:
            print("user_email(1) ->", client.user_email(1))
        except Exception as e:
            print(f"user_email(1) crashed: {type(e).__name__}: {e}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
