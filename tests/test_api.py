import base64
import gzip
import json
import unittest
from unittest.mock import patch

from nfse import core


XML = b"""<NFSe><infNFSe>
<emit><CNPJ>11222333000181</CNPJ></emit>
<toma><CNPJ>00000000000191</CNPJ></toma>
<dCompet>2026-11-01</dCompet>
</infNFSe></NFSe>"""


def encoded(xml=XML):
    return base64.b64encode(gzip.compress(xml)).decode("ascii")


class FakeResponse:
    def __init__(self, status, payload=None, text="", content=None, headers=None):
        self.status_code = status
        self._payload = payload
        self._text = text
        self.content = content if content is not None else text.encode("utf-8")
        self.headers = headers or {}
        self.closed = False

    def json(self):
        if self._payload is None:
            raise ValueError("sem JSON")
        return self._payload

    @property
    def text(self):
        return self._text

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def close(self):
        self.closed = True


def json_response(status, payload):
    body = json.dumps(payload)
    return FakeResponse(
        status,
        payload=payload,
        text=body,
        content=body.encode("utf-8"),
        headers={"content-type": "application/json"},
    )


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.cert = None
        self.headers = {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if not self.responses:
            raise AssertionError("FakeSession sem resposta")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        pass


class ApiTests(unittest.TestCase):
    def make_client(self, responses, max_retries=2):
        session = FakeSession(responses)
        client = core.NfseClient(
            core.PRODUCTION,
            "dummy-client.pem",
            lambda message: None,
            session=session,
            max_retries=max_retries,
        )
        return client, session

    def test_lote_dfe_ok(self):
        payload = {
            "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
            "LoteDFe": [
                {
                    "NSU": 8,
                    "TipoDocumento": "NFSE",
                    "ArquivoXml": encoded(),
                }
            ],
        }
        client, session = self.make_client([json_response(200, payload)])
        batch = client.fetch_batch("11222333000181", 0)
        self.assertEqual(batch.last_nsu, 8)
        self.assertEqual(len(batch.documents), 1)
        self.assertEqual(batch.documents[0].nsu, 8)
        self.assertEqual(batch.documents[0].data, XML)
        self.assertIn("/DFe/0", session.calls[0][0])

    def test_404_e2230_is_end(self):
        payload = {
            "StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO",
            "Erros": [{"Codigo": "E2230", "Descricao": "Nenhum documento localizado"}],
        }
        client, _ = self.make_client([json_response(404, payload)])
        with self.assertRaises(core.NoDocuments):
            client.fetch_batch("11222333000181", 0)

    def test_404_generic_is_error(self):
        client, _ = self.make_client(
            [FakeResponse(404, text="Not Found", headers={"content-type": "text/plain"})]
        )
        with self.assertRaises(core.ApiError) as ctx:
            client.fetch_batch("11222333000181", 0)
        self.assertNotIsInstance(ctx.exception, core.NoDocuments)

    def test_404_e2230_plus_other_error_is_error(self):
        payload = {
            "StatusProcessamento": "NENHUM_DOCUMENTO_LOCALIZADO",
            "Erros": [
                {"Codigo": "E2230", "Descricao": "Nenhum documento"},
                {"Codigo": "E9999", "Descricao": "Falha inesperada"},
            ],
        }
        client, _ = self.make_client([json_response(404, payload)])
        with self.assertRaises(core.ApiError) as ctx:
            client.fetch_batch("11222333000181", 0)
        self.assertNotIsInstance(ctx.exception, core.NoDocuments)

    def test_200_empty_errors_is_error(self):
        payload = {"StatusProcessamento": "REJEICAO", "Erros": []}
        client, _ = self.make_client([json_response(200, payload)])
        with self.assertRaises(core.ApiError):
            client.fetch_batch("11222333000181", 0)

    def test_204_is_end(self):
        client, _ = self.make_client([FakeResponse(204)])
        with self.assertRaises(core.NoDocuments):
            client.fetch_batch("11222333000181", 0)

    def test_retry_429(self):
        payload = {
            "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
            "LoteDFe": [{"NSU": 9, "TipoDocumento": "NFSE", "ArquivoXml": encoded()}],
        }
        client, session = self.make_client(
            [
                FakeResponse(429, text="slow", headers={"content-type": "text/plain"}),
                json_response(200, payload),
            ],
            max_retries=2,
        )
        with patch.object(core.NfseClient, "_sleep", lambda self, seconds: None):
            batch = client.fetch_batch("11222333000181", 0)
        self.assertEqual(batch.last_nsu, 9)
        self.assertEqual(len(session.calls), 2)

    def test_no_advance_is_error(self):
        payload = {
            "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
            "LoteDFe": [{"NSU": 0, "TipoDocumento": "NFSE", "ArquivoXml": encoded()}],
        }
        client, _ = self.make_client([json_response(200, payload)])
        with self.assertRaises(core.ApiError):
            client.fetch_batch("11222333000181", 0)

    def test_alerts_and_query_type(self):
        payload = {
            "StatusProcessamento": "DOCUMENTOS_LOCALIZADOS",
            "TipoConsulta": "PROCURACAO",
            "Alertas": [{"Descricao": "Alerta de teste"}],
            "LoteDFe": [{"NSU": 5, "TipoDocumento": "NFSE", "ArquivoXml": encoded()}],
        }
        client, _ = self.make_client([json_response(200, payload)])
        batch = client.fetch_batch("11222333000181", 0)
        self.assertEqual(batch.query_type, "PROCURACAO")
        self.assertEqual(batch.alerts, ["Alerta de teste"])

    def test_invalid_json_is_error(self):
        client, _ = self.make_client(
            [
                FakeResponse(
                    200,
                    text="<html>erro</html>",
                    headers={"content-type": "application/json"},
                )
            ]
        )
        with self.assertRaises(core.ApiError):
            client.fetch_batch("11222333000181", 0)


if __name__ == "__main__":
    unittest.main()
