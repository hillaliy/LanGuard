import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError

from download_badge import badge_payload, main, parse_download_count


class DownloadBadgeTests(unittest.TestCase):
    def test_exact_total_is_used_instead_of_rounded_or_version_counts(self):
        html = """
        <h3 title="5">5 Version downloads</h3>
        <div class="anything"><span> Total\n downloads </span>
        <h3 title="30762">30.8K</h3></div>
        <div><span>Downloads for the last 30 days</span><h3 title="42">42</h3></div>
        """
        self.assertEqual(parse_download_count(html), 30762)

    def test_zero_is_a_valid_count(self):
        self.assertEqual(parse_download_count('<div><span>Total downloads</span><h3 title="0">0</h3></div>'), 0)

    def test_missing_ambiguous_and_invalid_counts_fail_closed(self):
        valid = '<div><span>Total downloads</span><h3 title="123">123</h3></div>'
        for html in (
            "<html>Temporarily unavailable</html>",
            valid + valid,
            '<div><span>Total downloads</span></div><div><h3 title="123">123</h3></div>',
            '<div><span>Total downloads</span><h3>30.8K</h3></div>',
            '<div><span>Total downloads</span><h3 title="-1">-1</h3></div>',
        ):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_download_count(html)

    def test_badge_keeps_docker_pulls_label_and_formats_count(self):
        payload = badge_payload(30762)
        self.assertEqual(payload["label"], "Docker pulls")
        self.assertEqual(payload["message"], "30,762")
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["style"], "for-the-badge")

    def test_failed_fetch_preserves_previous_output(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "badge.json"
            output.write_text("previous count", encoding="utf-8")
            with (
                patch("sys.argv", ["download_badge.py", "--output", str(output)]),
                patch("download_badge.urlopen", side_effect=URLError("unavailable")),
                self.assertRaises(URLError),
            ):
                main()
            self.assertEqual(output.read_text(encoding="utf-8"), "previous count")

    def test_failed_parsing_preserves_previous_output(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "badge.json"
            output.write_text("previous count", encoding="utf-8")
            with (
                patch("sys.argv", ["download_badge.py", "--output", str(output)]),
                patch("download_badge.urlopen") as response,
                self.assertRaises(ValueError),
            ):
                response.return_value.__enter__.return_value.read.return_value = b"<html>Unavailable</html>"
                main()
            self.assertEqual(output.read_text(encoding="utf-8"), "previous count")
