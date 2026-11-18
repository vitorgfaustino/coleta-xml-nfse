import os
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from nfse import core


def make_pfx(password: bytes = b"secret") -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Teste NFS-e")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        b"teste",
        key,
        cert,
        None,
        serialization.BestAvailableEncryption(password),
    )


class CertificateTests(unittest.TestCase):
    def test_pem_is_private_and_removed(self):
        pfx = make_pfx()
        with core.CertificatePair(pfx, "secret") as pem_path:
            path = Path(pem_path)
            self.assertTrue(path.is_file())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            content = path.read_bytes()
            self.assertIn(b"BEGIN PRIVATE KEY", content)
            self.assertIn(b"BEGIN CERTIFICATE", content)
            self.assertEqual([item.name for item in path.parent.iterdir()], ["client.pem"])
            directory = path.parent
        self.assertFalse(directory.exists())

    def test_wrong_password(self):
        pfx = make_pfx()
        with self.assertRaises(core.CertificateError):
            with core.CertificatePair(pfx, "errada"):
                pass

    def test_run_paths_permissions(self):
        paths = core.RunPaths.create(ephemeral=True)
        try:
            self.assertEqual(stat.S_IMODE(paths.root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(paths.cache.stat().st_mode), 0o700)
        finally:
            paths.cleanup()

    def test_logger_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "log.txt"
            logger = core.RunLogger(path)
            logger.log("teste")
            logger.close()
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertIn("teste", path.read_text(encoding="utf-8"))

    def test_data_dir_override_and_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "dados"
            os.environ["NFSE_DATA_DIR"] = str(target)
            try:
                path = core.data_dir()
                self.assertEqual(path, target)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
            finally:
                os.environ.pop("NFSE_DATA_DIR", None)


if __name__ == "__main__":
    unittest.main()
