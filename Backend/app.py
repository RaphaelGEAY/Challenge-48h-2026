import argparse
from http.server import ThreadingHTTPServer

try:
    from .database import init_db
    from .handler import AuthRequestHandler
except ImportError:
    from Backend.database import init_db
    from Backend.handler import AuthRequestHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CodeArena auth backend")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()

    server = ThreadingHTTPServer((args.host, args.port), AuthRequestHandler)
    print(f"Server listening on http://{args.host}:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
