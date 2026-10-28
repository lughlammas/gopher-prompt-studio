"""Loopback-only HTTP API, Python standard library."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .engine import generate, registry
from .validation import InputError

MAX_BODY = 65536


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key / chave JSON duplicada: " + key)
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("Nonfinite JSON number / número JSON não finito: " + value)


class Handler(BaseHTTPRequestHandler):
    server_version = "GopherPromptStudio/" + __version__

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, fmt, *args):
        # Goals and pasted responses are never written to disk or access logs.
        pass

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def error(self, status, code, message, field=None):
        self.send_json(status, {"error": {"code": code, "message": message, "field": field}})

    def valid_host(self):
        return self.headers.get("Host") in (
            f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def do_GET(self):
        if not self.valid_host():
            return self.error(403, "invalid_host", "Use the local server address / use o endereço local.")
        if self.path == "/health":
            return self.send_json(200, {"status": "ok", "version": __version__, "mode": "local-rule-based"})
        if self.path == "/capabilities":
            try:
                return self.send_json(200, registry())
            except (OSError, ValueError):
                return self.error(500, "registry_error", "Could not read the capability registry / falha ao ler o registro.")
        self.error(404, "not_found", "Unknown route / rota inexistente.")

    def do_POST(self):
        if not self.valid_host():
            return self.error(403, "invalid_host", "Use the local server address / use o endereço local.")
        if self.path != "/prompts":
            return self.error(404, "not_found", "Unknown route / rota inexistente.")
        if self.headers.get("Transfer-Encoding"):
            return self.error(400, "invalid_body", "Transfer-Encoding is not supported.")
        if self.headers.get_content_type() != "application/json":
            return self.error(415, "content_type", "Use Content-Type: application/json.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.error(400, "invalid_length", "Invalid Content-Length.")
        if not 0 < length <= MAX_BODY:
            return self.error(413, "body_size", "Body must contain 1–65536 bytes / corpo entre 1 e 65536 bytes.")
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete request body / corpo incompleto.")
            data = json.loads(body.decode("utf-8"), object_pairs_hook=strict_object, parse_constant=reject_constant)
            result = generate(data)
        except InputError as exc:
            return self.error(422, "validation_error", str(exc), exc.field)
        except (UnicodeError, ValueError, RecursionError) as exc:
            return self.error(400, "invalid_json", str(exc))
        except TimeoutError:
            return self.error(408, "request_timeout", "Request timed out / tempo de envio excedido.")
        except Exception:
            return self.error(500, "internal_error", "Could not compose the prompt / não foi possível gerar o prompt.")
        self.send_json(200, result)


def make_server(port=8767):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description="Gopher Prompt Studio — local copy/paste API")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    if not 0 < args.port < 65536:
        parser.error("port must be between 1 and 65535")
    with make_server(args.port) as server:
        print(f"Gopher Prompt Studio: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
