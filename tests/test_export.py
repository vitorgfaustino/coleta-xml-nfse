import unittest
import zipfile
from pathlib import Path

from nfse import core


CNPJ = "11222333000181"

PROVIDER = b"""<NFSe><infNFSe>
<emit><CNPJ>11222333000181</CNPJ></emit>
<dCompet>2026-11-01</dCompet>
</infNFSe></NFSe>"""

RECIPIENT = b"""<NFSe><infNFSe>
<toma><CNPJ>11222333000181</CNPJ></toma>
<dCompet>2026-10-01</dCompet>
</infNFSe></NFSe>"""

EVENT = b"""<evento><infEvento>
<CNPJ>11222333000181</CNPJ>
<dCompet>2026-09-01</dCompet>
</infEvento></evento>"""

OTHER = b"""<NFSe><infNFSe>
<interm><CNPJ>99999999000199</CNPJ></interm>
<dCompet>2026-08-01</dCompet>
</infNFSe></NFSe>"""


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.paths = core.RunPaths.create(ephemeral=True)
        self.folder = self.paths.cache / CNPJ
        self.folder.mkdir(parents=True, exist_ok=True)
        files = {
            "NSU_000000000000001_NFSE_a.xml": PROVIDER,
            "NSU_000000000000002_NFSE_b.xml": RECIPIENT,
            "NSU_000000000000003_EVENTO_c.xml": EVENT,
            "NSU_000000000000004_NFSE_d.xml": OTHER,
        }
        for name, data in files.items():
            (self.folder / name).write_bytes(data)
        self.connection = core.connect_state(self.paths.state)

    def tearDown(self):
        self.connection.close()
        self.paths.cleanup()

    def test_export_all_categories(self):
        result = core.export_zip(
            self.connection,
            self.paths,
            [CNPJ],
            "Ambas",
            self.paths.exports / "saida.zip",
        )
        self.assertIsNotNone(result.zip_path)
        self.assertEqual(result.total, 4)
        self.assertEqual(result.categories["Prestados"], 1)
        self.assertEqual(result.categories["Tomados"], 1)
        self.assertEqual(result.categories["Eventos"], 1)
        self.assertEqual(result.categories["Outros"], 1)
        with zipfile.ZipFile(result.zip_path) as archive:
            names = archive.namelist()
        self.assertTrue(any("/Prestados/" in name for name in names))
        self.assertTrue(any("/Tomados/" in name for name in names))
        self.assertTrue(any("/Eventos/" in name for name in names))
        self.assertTrue(any("/Outros/" in name for name in names))

    def test_export_provider_includes_events(self):
        result = core.export_zip(
            self.connection,
            self.paths,
            [CNPJ],
            "Prestados",
            self.paths.exports / "prestados.zip",
        )
        self.assertEqual(result.total, 2)
        self.assertEqual(result.categories, {"Prestados": 1, "Eventos": 1})
        with zipfile.ZipFile(result.zip_path) as archive:
            names = archive.namelist()
        self.assertFalse(any("/Tomados/" in name for name in names))
        self.assertFalse(any("/Outros/" in name for name in names))

    def test_export_recipient_includes_events(self):
        result = core.export_zip(
            self.connection,
            self.paths,
            [CNPJ],
            "Tomados",
            self.paths.exports / "tomados.zip",
        )
        self.assertEqual(result.total, 2)
        self.assertEqual(result.categories, {"Tomados": 1, "Eventos": 1})

    def test_export_empty(self):
        empty = core.RunPaths.create(ephemeral=True)
        try:
            connection = core.connect_state(empty.state)
            try:
                result = core.export_zip(
                    connection,
                    empty,
                    ["00000000000191"],
                    "Ambas",
                    empty.exports / "vazio.zip",
                )
            finally:
                connection.close()
            self.assertIsNone(result.zip_path)
            self.assertEqual(result.total, 0)
        finally:
            empty.cleanup()

    def test_wipe_removes_cache_and_state(self):
        self.assertIsNotNone(self.connection.execute("SELECT 1").fetchone())
        self.connection.close()
        removed, freed = core.wipe_data(self.paths.root)
        self.assertGreater(removed, 0)
        self.assertGreater(freed, 0)
        self.assertFalse((self.paths.root / "xml_cache").exists())
        self.assertFalse((self.paths.root / "state.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
