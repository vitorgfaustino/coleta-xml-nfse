from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SourceZipTests(unittest.TestCase):
    def test_distribution_zip_contains_only_runtime_files(self):
        with tempfile.TemporaryDirectory(prefix="coleta-source-zip-") as folder:
            output = Path(folder) / "app.zip"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "export_source_zip.py"),
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(output.is_file())
            self.assertTrue(output.with_name(output.name + ".sha256").is_file())
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                modes = {
                    info.filename: info.external_attr >> 16
                    for info in archive.infolist()
                }
            self.assertIn("ColetaXMLNFSE/COMECE-AQUI.md", names)
            self.assertIn("ColetaXMLNFSE/iniciar.command", names)
            self.assertIn("ColetaXMLNFSE/nfse/core.py", names)
            self.assertIn("ColetaXMLNFSE/web/leitor.html", names)
            self.assertIn("ColetaXMLNFSE/requirements.txt", names)
            self.assertNotIn("ColetaXMLNFSE/tests", " ".join(names))
            self.assertNotIn("ColetaXMLNFSE/.github", " ".join(names))
            self.assertNotIn("ColetaXMLNFSE/.gitea", " ".join(names))
            self.assertNotIn("ColetaXMLNFSE/.venv", " ".join(names))
            self.assertTrue(modes["ColetaXMLNFSE/iniciar.command"] & 0o100)


if __name__ == "__main__":
    unittest.main()
