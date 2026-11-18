import base64
import http.client
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path

from nfse import core, web


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp(prefix="nfse_test_web_")
        os.environ["NFSE_DATA_DIR"] = self.tempdir
        self.server, self.token, self.url, self.manager = web.create_server(port=0)
        self.port = int(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        os.environ.pop("NFSE_DATA_DIR", None)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def request(self, path, method="GET", payload=None, token=True, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        request_headers = dict(headers or {})
        if token:
            request_headers["X-NFSE-Token"] = self.token
        body = None
        if payload is not None:
            body = json.dumps(payload)
            request_headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        data = response.read()
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, data, response_headers

    def request_raw(self, path, data, content_type, method="POST"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {
            "X-NFSE-Token": self.token,
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
        }
        connection.request(method, path, body=data, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, payload, response_headers

    def test_index_contains_token(self):
        status, data, headers = self.request("/")
        self.assertEqual(status, 200)
        text = data.decode("utf-8")
        self.assertIn("Coleta XML NFSE", text)
        self.assertIn(self.token, text)
        self.assertIn("Content-Security-Policy", headers)

    def test_reader_and_fflate(self):
        status, data, _ = self.request("/leitor")
        self.assertEqual(status, 200)
        text = data.decode("utf-8")
        self.assertIn("Coleta XML NFSE", text)
        self.assertIn("/vendor/fflate.js", text)

        status, data, headers = self.request("/vendor/fflate.js")
        self.assertEqual(status, 200)
        self.assertGreater(len(data), 1000)
        self.assertIn("javascript", headers.get("Content-Type", ""))

    def test_status_requires_token(self):
        status, _, _ = self.request("/api/status", token=False)
        self.assertEqual(status, 403)
        status, data, _ = self.request("/api/status")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertEqual(payload["state"], "idle")
        self.assertEqual(payload["data_dir"], self.tempdir)

    def test_health_is_public(self):
        status, data, _ = self.request("/api/health", token=False)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["app"], "nfse")

    def test_host_is_checked(self):
        status, _, _ = self.request("/api/health", token=False, headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_run_requires_certificate(self):
        status, data, _ = self.request("/api/run", method="POST", payload={})
        self.assertEqual(status, 400)
        self.assertIn("certificado", json.loads(data)["error"].lower())

    def test_run_rejects_bad_origin(self):
        payload = {
            "pfx_base64": base64.b64encode(b"fake").decode("ascii"),
            "password": "x",
            "cnpjs": ["00.000.000/0001-91"],
        }
        status, _, _ = self.request(
            "/api/run",
            method="POST",
            payload=payload,
            headers={"Origin": "http://evil.example"},
        )
        self.assertEqual(status, 403)

    def test_run_rejects_invalid_cnpj(self):
        payload = {
            "pfx_base64": base64.b64encode(b"fake").decode("ascii"),
            "password": "x",
            "cnpjs": ["123"],
        }
        status, data, _ = self.request("/api/run", method="POST", payload=payload)
        self.assertEqual(status, 400)
        self.assertIn("CNPJ", json.loads(data)["error"])

    def test_run_job_reports_bad_certificate(self):
        payload = {
            "pfx_base64": base64.b64encode(b"not a pfx").decode("ascii"),
            "password": "x",
            "cnpjs": ["00.000.000/0001-91"],
            "no_cache": True,
        }
        status, data, _ = self.request("/api/run", method="POST", payload=payload)
        self.assertEqual(status, 202)
        self.assertTrue(json.loads(data)["job_id"])
        deadline = time.time() + 5
        state = "running"
        last = {}
        while time.time() < deadline:
            _, status_data, _ = self.request("/api/status")
            last = json.loads(status_data)
            state = last["state"]
            if state != "running":
                break
            time.sleep(0.05)
        self.assertEqual(state, "error")
        self.assertIn("PFX", last["error"])

    def test_run_rejects_invalid_period(self):
        payload = {
            "pfx_base64": base64.b64encode(b"fake").decode("ascii"),
            "password": "x",
            "cnpjs": ["00.000.000/0001-91"],
            "period_start": "2026-13",
            "period_end": "2026-12",
        }
        status, data, _ = self.request("/api/run", method="POST", payload=payload)
        self.assertEqual(status, 400)
        self.assertIn("Competência", json.loads(data)["error"])

    def test_run_rejects_partial_period(self):
        payload = {
            "pfx_base64": base64.b64encode(b"fake").decode("ascii"),
            "password": "x",
            "cnpjs": ["00.000.000/0001-91"],
            "period_start": "2026-01",
        }
        status, data, _ = self.request("/api/run", method="POST", payload=payload)
        self.assertEqual(status, 400)
        self.assertIn("período", json.loads(data)["error"].lower())

    def test_run_rejects_partial_emission(self):
        payload = {
            "pfx_base64": base64.b64encode(b"fake").decode("ascii"),
            "password": "x",
            "cnpjs": ["00.000.000/0001-91"],
            "emission_start": "2026-01-01",
        }
        status, data, _ = self.request("/api/run", method="POST", payload=payload)
        self.assertEqual(status, 400)
        self.assertIn("emissão", json.loads(data)["error"].lower())

    def test_run_rejects_invalid_emission(self):
        payload = {
            "pfx_base64": base64.b64encode(b"fake").decode("ascii"),
            "password": "x",
            "cnpjs": ["00.000.000/0001-91"],
            "emission_start": "2026-02-30",
            "emission_end": "2026-03-01",
        }
        status, data, _ = self.request("/api/run", method="POST", payload=payload)
        self.assertEqual(status, 400)
        self.assertIn("emissão", json.loads(data)["error"].lower())

    def test_run_rejects_negative_start_nsu(self):
        payload = {
            "pfx_base64": base64.b64encode(b"fake").decode("ascii"),
            "password": "x",
            "cnpjs": ["00.000.000/0001-91"],
            "start_nsu": -1,
        }
        status, data, _ = self.request("/api/run", method="POST", payload=payload)
        self.assertEqual(status, 400)
        self.assertIn("NSU", json.loads(data)["error"])

    def test_run_rejects_non_boolean_no_cache(self):
        payload = {
            "pfx_base64": base64.b64encode(b"fake").decode("ascii"),
            "password": "x",
            "cnpjs": ["00.000.000/0001-91"],
            "no_cache": "true",
        }
        status, data, _ = self.request("/api/run", method="POST", payload=payload)
        self.assertEqual(status, 400)
        self.assertIn("no_cache", json.loads(data)["error"])

    def test_history_cache_backup_and_diagnostics(self):
        status, data, _ = self.request("/api/history")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["runs"], [])

        status, data, _ = self.request("/api/cache")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["clients"], [])

        cnpj = "12345678000199"
        folder = Path(self.tempdir) / "xml_cache" / cnpj
        folder.mkdir(parents=True)
        (folder / "nota.xml").write_text("<NFSe/>", encoding="utf-8")
        connection = core.connect_state(Path(self.tempdir) / "state.sqlite3")
        try:
            core.record_document(
                connection,
                cnpj,
                "b" * 64,
                "nota.xml",
                9,
                core.DocumentInfo(competence="2026-11", prestado=True),
            )
            core.save_cursor(connection, cnpj, 9)
            core.record_run(
                connection,
                started_at="2026-11-18T10:00:00",
                finished_at="2026-11-18T10:01:00",
                state="done",
                environment="producao",
                document_filter="Ambas",
                cnpj_count=1,
                new_documents=1,
                exported=1,
            )
        finally:
            connection.close()

        status, data, _ = self.request("/api/cache")
        clients = json.loads(data)["clients"]
        self.assertEqual(status, 200)
        self.assertEqual(clients[0]["cnpj"], cnpj)
        self.assertEqual(clients[0]["files"], 1)

        status, data, _ = self.request("/api/history")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["runs"][0]["new_documents"], 1)

        status, backup, headers = self.request("/api/cache/backup")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "application/zip")
        archive = Path(self.tempdir) / "backup.zip"
        archive.write_bytes(backup)
        with zipfile.ZipFile(archive) as bundle:
            self.assertIn("state.sqlite3", bundle.namelist())
            self.assertIn(f"xml_cache/{cnpj}/nota.xml", bundle.namelist())

        status, payload, _ = self.request(
            "/api/cache/clear", method="POST", payload={"cnpj": cnpj}
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)["files"], 1)

        status, payload, _ = self.request_raw(
            "/api/cache/restore", backup, "application/zip"
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)["files"], 1)

        status, data, _ = self.request("/api/diagnostics")
        self.assertEqual(status, 200)
        diagnostics = json.loads(data)
        self.assertEqual(diagnostics["app"], "Coleta XML NFSE")
        self.assertIn("adn", diagnostics)

    def test_wipe(self):
        cache = Path(self.tempdir) / "xml_cache"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "a.xml").write_bytes(b"<x/>")
        status, data, _ = self.request("/api/wipe", method="POST", payload={})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)["ok"])
        self.assertFalse(cache.exists())


if __name__ == "__main__":
    unittest.main()
