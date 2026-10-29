"""Build a Shields endpoint from the public GHCR package download count."""

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

PACKAGE_URL = "https://github.com/hillaliy/LanGuard/pkgs/container/languard-backend"
MAX_PAGE_BYTES = 2 * 1024 * 1024


class DownloadCountParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.div_depth = 0
        self.label = None
        self.count_depth = None
        self.counts = []

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            self.div_depth += 1
        elif tag == "span":
            self.label = []
        elif tag == "h3" and self.count_depth == self.div_depth:
            title = dict(attrs).get("title", "")
            if not title.isascii() or not title.isdecimal():
                raise ValueError("GitHub did not return an exact total download count.")
            self.counts.append(int(title))

    def handle_data(self, data):
        if self.label is not None:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "span" and self.label is not None:
            if " ".join("".join(self.label).split()) == "Total downloads":
                self.count_depth = self.div_depth
            self.label = None
        elif tag == "div":
            if self.count_depth == self.div_depth:
                self.count_depth = None
            self.div_depth -= 1


def parse_download_count(html):
    parser = DownloadCountParser()
    parser.feed(html)
    if len(parser.counts) != 1:
        raise ValueError("Expected one total download count on the public GitHub package page.")
    return parser.counts[0]


def badge_payload(count):
    return {
        "schemaVersion": 1,
        "label": "Docker pulls",
        "message": f"{count:,}",
        "color": "blue",
        "namedLogo": "docker",
        "style": "for-the-badge",
        "cacheSeconds": 3600,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = Request(PACKAGE_URL, headers={"User-Agent": "LanGuard-download-badge", "Accept": "text/html"})
    with urlopen(request, timeout=30) as response:
        html = response.read(MAX_PAGE_BYTES + 1)
    if len(html) > MAX_PAGE_BYTES:
        raise ValueError("GitHub package page exceeded the read limit.")
    count = parse_download_count(html.decode("utf-8"))
    # Never replace the last good badge if fetching or parsing fails.
    args.output.write_text(json.dumps(badge_payload(count), indent=2) + "\n", encoding="utf-8")
    print(f"Docker pulls: {count:,} ({PACKAGE_URL})")


if __name__ == "__main__":
    main()
