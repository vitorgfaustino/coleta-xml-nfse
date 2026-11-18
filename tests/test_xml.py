import base64
import gzip
import unittest

from nfse import core


NFS_E = b"""<NFSe xmlns="http://www.gov.br/nfse">
  <infNFSe>
    <emit><CNPJ>11222333000181</CNPJ></emit>
    <toma><CNPJ>00000000000191</CNPJ></toma>
    <dCompet>2026-11-01</dCompet>
  </infNFSe>
</NFSe>"""

NFS_E_ALFA = b"""<NFSe>
  <infNFSe>
    <emit><CNPJ>00000000E08G12</CNPJ></emit>
    <dCompet>20261101</dCompet>
  </infNFSe>
</NFSe>"""

EVENT = b"""<evento>
  <infEvento>
    <CNPJ>11222333000181</CNPJ>
    <dCompet>2026-11-02</dCompet>
  </infEvento>
</evento>"""


class XmlTests(unittest.TestCase):
    def test_provider_and_recipient(self):
        provider = core.classify_document(NFS_E, "11.222.333/0001-81")
        self.assertTrue(provider.prestado)
        self.assertFalse(provider.tomado)
        self.assertEqual(provider.competence, "2026-11")
        recipient = core.classify_document(NFS_E, "00.000.000/0001-91")
        self.assertFalse(recipient.prestado)
        self.assertTrue(recipient.tomado)

    def test_alphanumeric_match(self):
        info = core.classify_document(NFS_E_ALFA, "00.000.000/E08G-12")
        self.assertTrue(info.prestado)
        self.assertEqual(info.competence, "2026-11")

    def test_event(self):
        info = core.classify_document(EVENT, "11222333000181")
        self.assertTrue(info.event)

    def test_emission_date_fallback(self):
        xml = b"""<NFSe><infNFSe>
        <emit><CNPJ>11222333000181</CNPJ></emit>
        <dhEmi>2026-10-03T09:00:00-03:00</dhEmi>
        </infNFSe></NFSe>"""
        info = core.classify_document(xml, "11222333000181")
        self.assertEqual(info.competence, "2026-10")

    def test_extract_base64_gzip(self):
        encoded = base64.b64encode(gzip.compress(NFS_E)).decode("ascii")
        documents = core.extract_xml_documents({"documento": encoded})
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].data, NFS_E)

    def test_extract_nsu(self):
        encoded = base64.b64encode(gzip.compress(NFS_E)).decode("ascii")
        documents = core.extract_xml_documents(
            {"LoteDFe": [{"NSU": 42, "TipoDocumento": "NFSE", "ArquivoXml": encoded}]}
        )
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].nsu, 42)
        self.assertIn("NSU_000000000000042", core.document_filename(documents[0]))

    def test_invalid_xml_ignored(self):
        documents = core.extract_xml_documents({"documento": "não é xml"})
        self.assertEqual(documents, [])


if __name__ == "__main__":
    unittest.main()
