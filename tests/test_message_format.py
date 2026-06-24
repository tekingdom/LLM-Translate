import unittest

from app.services.message_format import parse_translation_options
from app.services.translation import _trim_extra_options


class ParseTranslationOptionsTests(unittest.TestCase):
    def test_multiline_options(self) -> None:
        text = "Option 1: a, b\nOption 2: x, y"
        result = parse_translation_options(text)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("Option 1:", "a, b"))
        self.assertEqual(result[1], ("Option 2:", "x, y"))

    def test_inline_comma_list_same_line(self) -> None:
        text = "Option 1: a, b, c Option 2: x, y, z"
        result = parse_translation_options(text)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("Option 1:", "a, b, c"))
        self.assertEqual(result[1], ("Option 2:", "x, y, z"))

    def test_aviation_inline_list(self) -> None:
        text = (
            "Option 1: โครงเครื่อง, กิมบอล, โหลด "
            "Option 2: แอร์เฟรม, กิมบอล, เพย์โหลด"
        )
        result = parse_translation_options(text)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][1], "โครงเครื่อง, กิมบอล, โหลด")
        self.assertEqual(result[1][1], "แอร์เฟรม, กิมบอล, เพย์โหลด")

    def test_no_options_returns_none(self) -> None:
        self.assertIsNone(parse_translation_options("plain translation text"))


class TrimExtraOptionsTests(unittest.TestCase):
    def test_trims_third_option_multiline(self) -> None:
        text = "Option 1: a\nOption 2: b\nOption 3: c"
        trimmed, was_trimmed = _trim_extra_options(text)
        self.assertTrue(was_trimmed)
        self.assertEqual(trimmed, "Option 1: a\nOption 2: b")

    def test_trims_third_option_inline(self) -> None:
        text = "Option 1: a, b Option 2: x, y Option 3: extra"
        trimmed, was_trimmed = _trim_extra_options(text)
        self.assertTrue(was_trimmed)
        self.assertEqual(trimmed, "Option 1: a, b Option 2: x, y")

    def test_two_options_unchanged(self) -> None:
        text = "Option 1: a, b, c Option 2: x, y, z"
        trimmed, was_trimmed = _trim_extra_options(text)
        self.assertFalse(was_trimmed)
        self.assertEqual(trimmed, text)


if __name__ == "__main__":
    unittest.main()
