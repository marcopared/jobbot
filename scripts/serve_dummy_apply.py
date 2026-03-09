from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8899


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fixtures_dir = repo_root / "tests" / "fixtures"
    if not fixtures_dir.exists():
        raise RuntimeError(f"Fixtures directory not found: {fixtures_dir}")

    handler = partial(SimpleHTTPRequestHandler, directory=str(fixtures_dir))
    server = ThreadingHTTPServer((HOST, PORT), handler)

    print(f"Serving fixtures from: {fixtures_dir}")
    print(f"Dummy form URL: http://{HOST}:{PORT}/dummy_apply_form.html")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
