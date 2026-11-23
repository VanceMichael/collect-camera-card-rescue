"""检查原件在本机来源上能被实际读取。"""
import json
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from source_server import make_server

HERE = Path(__file__).resolve().parents[1]


class SourceTests(unittest.TestCase):
    """用 HTTP 验证读取端点和柜台实际回页。"""

    @classmethod
    def setUpClass(cls):
        cls.source = make_server()
        cls.thread = threading.Thread(target=cls.source.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.source.server_port}"
        cls.config = json.loads((HERE / "origin.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.source.shutdown()
        cls.thread.join()
        cls.source.server_close()

    def test_origins(self):
        for item in self.config["sources"]:
            with self.subTest(path=item), urlopen(self.url + item, timeout=3) as response:
                self.assertEqual(response.status, 200)
                raw = response.read()
                self.assertTrue(raw)
                if item.endswith(".json"):
                    self.assertIsInstance(json.loads(raw), dict)
                if item.endswith(".ndjson"):
                    self.assertTrue(all(json.loads(line) for line in raw.splitlines()))

    def test_unpublished_path(self):
        with self.assertRaises(HTTPError) as result:
            urlopen(self.url + "/unpublished", timeout=3)
        self.assertEqual(result.exception.code, 404)

    def test_frame_range(self):
        request = Request(self.url + "/frames/e14.txt", headers={"Range": "bytes=20-39"})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.headers["Content-Range"], "bytes 20-39/40")
            self.assertEqual(response.read(), b"01234567890123456789")

    def test_archive_and_transport_expose_separate_observations(self):
        with urlopen(self.url + "/crew/transport.json", timeout=3) as response:
            transport = json.load(response)
        with urlopen(self.url + "/archive/inbox.json", timeout=3) as response:
            archive = json.load(response)
        self.assertEqual(transport["arrivals"], [["T3", "C21", "arrived", 56]])
        self.assertEqual(archive["late_observed_at"], 60)
        self.assertEqual(archive["late"], [["E15", "G8", 0, 28, "raw", "F15"]])


if __name__ == "__main__":
    unittest.main()
