#!/usr/bin/env python3
"""fetch_models.py 的标准库单元测试。

运行：
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/model-update/scripts -p 'test_*.py' -v
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_models  # noqa: E402

API_KEY = "sk-secret-test-key"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.server.body)

    def log_message(self, *args):
        pass


def _jsonc(text: str) -> object:
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))
    return json.loads(body)


class FetchModelsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("HOME")
        os.environ["HOME"] = self.tmp.name
        os.environ.pop("SENSE_BASE_URL", None)
        os.environ.pop("SENSE_API_KEY", None)
        self.server = None

    def tearDown(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.old_home
        os.environ.pop("SENSE_BASE_URL", None)
        os.environ.pop("SENSE_API_KEY", None)
        self.tmp.cleanup()

    def start_server(self, status: int = 200, payload: object | None = None):
        body = json.dumps(payload if payload is not None else {"data": []}).encode("utf-8")
        server = HTTPServer(("127.0.0.1", 0), _Handler)
        server.status = status
        server.body = body
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.server = server
        port = server.server_address[1]
        os.environ["SENSE_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
        os.environ["SENSE_API_KEY"] = API_KEY

    def cache_file(self) -> Path:
        return Path(self.tmp.name) / ".cache" / "models" / "sense.jsonc"

    def test_env_prefix_normalization(self):
        self.assertEqual(fetch_models.env_prefix("sense"), "SENSE")
        self.assertEqual(fetch_models.env_prefix("sense-ai"), "SENSE_AI")
        self.assertEqual(fetch_models.env_prefix("a.b c/d"), "A_B_C_D")

    def test_missing_env_writes_nothing(self):
        with self.assertRaises(RuntimeError) as ctx:
            fetch_models.fetch("sense")
        self.assertIn("SENSE_BASE_URL", str(ctx.exception))
        self.assertIn("SENSE_API_KEY", str(ctx.exception))
        self.assertFalse(self.cache_file().exists())

    def test_success_preserves_raw_fields_and_writes_cache(self):
        self.start_server(
            payload={
                "data": [
                    {
                        "id": "sensenova-6.8-flash-lite",
                        "context_length": 131072,
                        "owned_by": "sensenova",
                        "features": {"vision": True},
                    },
                    {"id": "sensenova-6.7-flash-lite"},
                ]
            }
        )

        path, count = fetch_models.fetch("sense")

        self.assertEqual(count, 2)
        self.assertEqual(Path(path), self.cache_file())
        cached = _jsonc(self.cache_file().read_text(encoding="utf-8"))
        self.assertEqual(cached["data"][0]["context_length"], 131072)
        self.assertEqual(cached["data"][0]["features"], {"vision": True})
        self.assertNotIn(API_KEY, self.cache_file().read_text(encoding="utf-8"))

    def test_http_error_keeps_old_cache(self):
        self.start_server(payload={"data": [{"id": "first"}]})
        fetch_models.fetch("sense")
        before = self.cache_file().read_text(encoding="utf-8")

        self.server.status = 500
        self.server.body = b'{"error": "upstream failed"}'
        with self.assertRaises(Exception):
            fetch_models.fetch("sense")

        self.assertEqual(self.cache_file().read_text(encoding="utf-8"), before)

    def test_empty_list_keeps_old_cache(self):
        self.start_server(payload={"data": [{"id": "first"}]})
        fetch_models.fetch("sense")
        before = self.cache_file().read_text(encoding="utf-8")

        self.server.status = 200
        self.server.body = b'{"data": []}'
        with self.assertRaises(ValueError):
            fetch_models.fetch("sense")

        self.assertEqual(self.cache_file().read_text(encoding="utf-8"), before)

    def test_main_output_does_not_contain_api_key(self):
        self.start_server(payload={"data": [{"id": "m1"}]})
        stdout, stderr = io.StringIO(), io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = fetch_models.main(["fetch_models.py", "sense"])

        self.assertEqual(code, 0)
        self.assertNotIn(API_KEY, stdout.getvalue() + stderr.getvalue())
        self.assertIn("1 个模型", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
