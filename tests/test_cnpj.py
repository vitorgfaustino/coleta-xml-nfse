import unittest

from nfse import core


class CnpjTests(unittest.TestCase):
    def test_numeric_cnpj(self):
        self.assertTrue(core.valid_cnpj("11.222.333/0001-81"))
        self.assertTrue(core.valid_cnpj("00000000000191"))
        self.assertFalse(core.valid_cnpj("11.222.333/0001-80"))

    def test_alphanumeric_cnpj(self):
        self.assertTrue(core.valid_cnpj("00.000.000/E08G-12"))
        self.assertTrue(core.valid_cnpj("12.ABC.345/01DE-35"))
        self.assertFalse(core.valid_cnpj("00.000.000/E08G-13"))

    def test_normalize_keeps_letters(self):
        self.assertEqual(core.normalize_cnpj("00.000.000/e08g-12"), "00000000E08G12")

    def test_parse_text_with_labels_and_invalid(self):
        text = (
            "00.000.000/0001-91\n"
            "CNPJ: 12.ABC.345/01DE-35\n"
            "00.000.000/E08G-12, 11.222.333/0001-81\n"
            "não é cnpj"
        )
        valid, invalid = core.parse_cnpj_text(text)
        self.assertIn("00000000000191", valid)
        self.assertIn("12ABC34501DE35", valid)
        self.assertIn("00000000E08G12", valid)
        self.assertIn("11222333000181", valid)
        self.assertTrue(invalid)

    def test_mask(self):
        self.assertEqual(core.mask_cnpj("12.ABC.345/01DE-35"), "***DE35")

    def test_redact_sensitive(self):
        text = "erro 12.ABC.345/01DE-35 e 11222333000181"
        redacted = core.redact_sensitive(text)
        self.assertNotIn("12.ABC.345/01DE-35", redacted)
        self.assertNotIn("11222333000181", redacted)
        self.assertIn("***DE35", redacted)
        self.assertIn("***0181", redacted)
        access_key = "1" * 44
        self.assertIn(access_key, core.redact_sensitive(access_key))


if __name__ == "__main__":
    unittest.main()
