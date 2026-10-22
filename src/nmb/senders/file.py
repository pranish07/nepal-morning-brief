"""Optional GitHub Pages output: index.html plus an RSS mirror."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from email.utils import format_datetime
from pathlib import Path

from ..models import Digest
from ..timeutil import to_utc
from .base import Sender, SenderError

logger = logging.getLogger(__name__)


class FileSender(Sender):
    name = "file"

    def __init__(self, output_dir: Path, site_url: str = "") -> None:
        self.output_dir = output_dir
        self.site_url = site_url.rstrip("/")

    def send(self, subject: str, text_body: str, html_body: str, digest: Digest) -> None:
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "index.html").write_text(html_body, encoding="utf-8")
            (self.output_dir / "rss.xml").write_text(self._build_rss(digest), encoding="utf-8")
        except OSError as exc:
            raise SenderError(f"Could not write file output: {exc}") from exc
        logger.info(
            "sender.sent",
            extra={"data": {"sender": self.name, "output_dir": str(self.output_dir)}},
        )

    def _build_rss(self, digest: Digest) -> str:
        rss = ET.Element("rss", {"version": "2.0"})
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = "Nepal Morning Brief"
        if self.site_url:
            ET.SubElement(channel, "link").text = self.site_url
        ET.SubElement(channel, "description").text = (
            "A daily digest of Nepal, world, AI, and programming news."
        )
        ET.SubElement(channel, "language").text = "en"
        ET.SubElement(channel, "lastBuildDate").text = format_datetime(
            to_utc(digest.generated_at), usegmt=True
        )

        for section in digest.sections:
            for article in section.articles:
                item = ET.SubElement(channel, "item")
                ET.SubElement(item, "title").text = article.title
                ET.SubElement(item, "link").text = article.url
                ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = article.url
                ET.SubElement(item, "category").text = section.name
                ET.SubElement(item, "source").text = article.source_name
                ET.SubElement(item, "pubDate").text = format_datetime(
                    article.published_at, usegmt=True
                )
                description = article.summary or f"{article.title} ({article.source_name})"
                ET.SubElement(item, "description").text = description

        ET.indent(rss, space="  ")
        return ET.tostring(rss, encoding="unicode", xml_declaration=True) + "\n"
