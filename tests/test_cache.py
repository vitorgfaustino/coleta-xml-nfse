from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from nfse import core


class CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="coleta-cache-test-"))
        self.cnpj = "12345678000199"
        self.connection = core.connect_state(self.root / "state.sqlite3")
        self.connection.close()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _seed(self) -> Path:
        folder = self.root / "xml_cache" / self.cnpj
        folder.mkdir(parents=True)
        path = folder / "nota.xml"
        path.write_text("<NFSe/>", encoding="utf-8")
        connection = core.connect_state(self.root / "state.sqlite3")
        try:
            core.record_document(
                connection,
                self.cnpj,
                "a" * 64,
                "nota.xml",
                42,
                core.DocumentInfo(competence="2026-11", prestado=True),
            )
            core.save_cursor(connection, self.cnpj, 42)
        finally:
            connection.close()
        return path

    def test_cache_clients_and_clear(self) -> None:
        self._seed()
        clients = core.cache_clients(self.root)
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["cnpj"], self.cnpj)
        self.assertEqual(clients[0]["files"], 1)
        self.assertGreater(clients[0]["bytes"], 0)

        result = core.clear_cnpj_cache(self.cnpj, self.root)
        self.assertEqual(result["files"], 1)
        self.assertEqual(result["documents"], 1)
        self.assertEqual(core.cache_clients(self.root), [])
        connection = core.connect_state(self.root / "state.sqlite3")
        try:
            self.assertEqual(core.load_cursor(connection, self.cnpj), 0)
        finally:
            connection.close()

    def test_backup_restore_roundtrip(self) -> None:
        self._seed()
        archive = core.create_cache_backup(self.root)
        try:
            with zipfile.ZipFile(archive) as bundle:
                names = set(bundle.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("state.sqlite3", names)
            self.assertIn(f"xml_cache/{self.cnpj}/nota.xml", names)

            result = core.restore_cache_backup(archive, self.root)
            self.assertEqual(result["documents"], 1)
            self.assertEqual(result["files"], 1)
            connection = core.connect_state(self.root / "state.sqlite3")
            try:
                self.assertEqual(core.load_cursor(connection, self.cnpj), 42)
            finally:
                connection.close()
        finally:
            shutil.rmtree(archive.parent, ignore_errors=True)

    def test_restore_rejects_path_traversal(self) -> None:
        archive = self.root / "malicioso.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../fora.xml", "<x/>")
            bundle.writestr("state.sqlite3", b"")
        with self.assertRaises(ValueError):
            core.restore_cache_backup(archive, self.root)

    def test_history_record_and_list(self) -> None:
        connection = core.connect_state(self.root / "state.sqlite3")
        try:
            core.record_run(
                connection,
                started_at="2026-11-18T10:00:00",
                finished_at="2026-11-18T10:01:00",
                state="done",
                environment="producao",
                document_filter="Ambas",
                cnpj_count=2,
                new_documents=3,
                exported=3,
                ignored=4,
                failures=1,
            )
            runs = core.list_runs(connection)
        finally:
            connection.close()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["state"], "done")
        self.assertEqual(runs[0]["new_documents"], 3)
        self.assertEqual(runs[0]["ignored"], 4)
        self.assertEqual(runs[0]["cnpj_count"], 2)
