import hashlib
import unittest
import zipfile
from pathlib import Path

from nfse import core


CNPJ = "11222333000181"


def make_document(
    nsu: int, competence: str, value: str, emission: str | None = None
) -> core.ExtractedDocument:
    emission = emission or f"{competence}-01"
    xml = f"""<NFSe><infNFSe>
<emit><CNPJ>{CNPJ}</CNPJ></emit>
<toma><CNPJ>00000000000191</CNPJ></toma>
<dCompet>{competence}-01</dCompet>
<dhEmi>{emission}T09:00:00-03:00</dhEmi>
<vNF>{value}</vNF>
</infNFSe></NFSe>""".encode("utf-8")
    return core.ExtractedDocument(
        label="NFSE",
        nsu=nsu,
        data=xml,
        digest=hashlib.sha256(xml).hexdigest(),
    )


class FakeClient:
    delay = 0

    def __init__(self, documents):
        self.documents = list(documents)
        self.calls = []

    def fetch_batch(self, cnpj, cursor):
        self.calls.append(cursor)
        if not self.documents:
            raise core.NoDocuments("fim")
        documents = self.documents
        self.documents = []
        return core.Batch(
            documents=documents,
            last_nsu=max(document.nsu or 0 for document in documents),
        )


class PeriodTests(unittest.TestCase):
    def setUp(self):
        self.paths = core.RunPaths.create(ephemeral=True)
        self.logs = []

    def tearDown(self):
        self.paths.cleanup()

    def test_period_skips_documents_but_advances_cursor(self):
        client = FakeClient(
            [
                make_document(1, "2025-12", "10.00"),
                make_document(2, "2026-01", "20.00"),
                make_document(3, "2026-02", "30.00"),
            ]
        )
        results = core.run_download(
            self.paths,
            client,
            [CNPJ],
            self.logs.append,
            ephemeral=True,
            period_start="2026-01",
            period_end="2026-01",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].new_documents, 1)
        self.assertEqual(results[0].ignored, 2)
        self.assertEqual(results[0].cursor, 3)
        cached = list((self.paths.cache / CNPJ).glob("*.xml"))
        self.assertEqual(len(cached), 1)
        self.assertIn(b"2026-01", cached[0].read_bytes())
        self.assertTrue(any("fora do período" in line for line in self.logs))

    def test_export_respects_period(self):
        client = FakeClient(
            [
                make_document(1, "2025-12", "10.00"),
                make_document(2, "2026-01", "20.00"),
            ]
        )
        core.run_download(
            self.paths,
            client,
            [CNPJ],
            self.logs.append,
            ephemeral=True,
            period_start="2026-01",
            period_end="2026-01",
        )
        connection = core.connect_state(self.paths.state)
        try:
            result = core.export_zip(
                connection,
                self.paths,
                [CNPJ],
                "Ambas",
                self.paths.exports / "periodo.zip",
                period_start="2026-01",
                period_end="2026-01",
            )
            self.assertIsNotNone(result.zip_path)
            self.assertEqual(result.total, 1)
            with zipfile.ZipFile(result.zip_path) as archive:
                names = archive.namelist()
            self.assertTrue(any("/2026-01/" in name for name in names))
            self.assertFalse(any("/2025-12/" in name for name in names))

            empty = core.export_zip(
                connection,
                self.paths,
                [CNPJ],
                "Ambas",
                self.paths.exports / "vazio.zip",
                period_start="2026-02",
                period_end="2026-02",
            )
            self.assertIsNone(empty.zip_path)
            self.assertEqual(empty.total, 0)
        finally:
            connection.close()


    def test_emission_day_range(self):
        client = FakeClient(
            [
                make_document(1, "2026-01", "10.00", "2026-01-05"),
                make_document(2, "2026-01", "20.00", "2026-01-20"),
                make_document(3, "2026-02", "30.00", "2026-02-01"),
            ]
        )
        results = core.run_download(
            self.paths,
            client,
            [CNPJ],
            self.logs.append,
            ephemeral=True,
            emission_start="2026-01-10",
            emission_end="2026-01-31",
        )
        self.assertEqual(results[0].new_documents, 1)
        self.assertEqual(results[0].ignored, 2)
        self.assertEqual(results[0].cursor, 3)
        cached = list((self.paths.cache / CNPJ).glob("*.xml"))
        self.assertEqual(len(cached), 1)
        self.assertIn(b"2026-01-20", cached[0].read_bytes())
        self.assertTrue(any("Filtro de emissão" in line for line in self.logs))

    def test_export_respects_emission_range(self):
        client = FakeClient(
            [
                make_document(1, "2026-01", "10.00", "2026-01-05"),
                make_document(2, "2026-01", "20.00", "2026-01-20"),
            ]
        )
        core.run_download(
            self.paths,
            client,
            [CNPJ],
            self.logs.append,
            ephemeral=True,
        )
        connection = core.connect_state(self.paths.state)
        try:
            result = core.export_zip(
                connection,
                self.paths,
                [CNPJ],
                "Ambas",
                self.paths.exports / "emissao.zip",
                emission_start="2026-01-10",
                emission_end="2026-01-31",
            )
            self.assertIsNotNone(result.zip_path)
            self.assertEqual(result.total, 1)
        finally:
            connection.close()

    def test_export_backfills_dates_for_old_index(self):
        client = FakeClient(
            [make_document(1, "2026-01", "10.00", "2026-01-20")]
        )
        core.run_download(
            self.paths,
            client,
            [CNPJ],
            self.logs.append,
            ephemeral=True,
        )
        connection = core.connect_state(self.paths.state)
        try:
            connection.execute(
                "UPDATE documents SET competence_date = NULL, emission_date = NULL"
            )
            connection.commit()
            result = core.export_zip(
                connection,
                self.paths,
                [CNPJ],
                "Ambas",
                self.paths.exports / "backfill.zip",
                log=self.logs.append,
                emission_start="2026-01-10",
                emission_end="2026-01-31",
            )
            self.assertIsNotNone(result.zip_path)
            self.assertEqual(result.total, 1)
            self.assertTrue(any("atualizados com datas" in line for line in self.logs))
        finally:
            connection.close()

    def test_start_nsu_skips_old_history(self):
        client = FakeClient(
            [
                make_document(100, "2026-01", "100.00"),
                make_document(101, "2026-01", "101.00"),
            ]
        )
        results = core.run_download(
            self.paths,
            client,
            [CNPJ],
            self.logs.append,
            ephemeral=True,
            start_nsu=100,
        )
        self.assertEqual(client.calls[0], 99)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].cursor, 101)
        self.assertEqual(len(list((self.paths.cache / CNPJ).glob("*.xml"))), 2)


if __name__ == "__main__":
    unittest.main()
