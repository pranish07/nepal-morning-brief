import xml.etree.ElementTree as ET

from nmb.models import Digest, Section
from nmb.render import render_digest
from nmb.senders.file import FileSender


def test_render_and_file_sender_write_html_and_rss(tmp_path, make_article, now):
    article = make_article(title="A linked headline", url="https://example.com/story")
    article.summary = "An original summary about the event."
    digest = Digest(
        generated_at=now,
        sections=[Section(id="nepal", name="Nepal", count=10, articles=[article])],
    )
    subject, text_body, html_body = render_digest(digest)
    assert "Nepal Morning Brief" in subject
    assert "A linked headline" in text_body
    assert "NPT" in text_body
    assert 'href="https://example.com/story"' in html_body

    sender = FileSender(tmp_path / "public", site_url="https://example.com")
    sender.send(subject, text_body, html_body, digest)

    assert (tmp_path / "public" / "index.html").is_file()
    rss_path = tmp_path / "public" / "rss.xml"
    assert rss_path.is_file()
    root = ET.fromstring(rss_path.read_text(encoding="utf-8"))
    item = root.find("./channel/item")
    assert item is not None
    assert item.findtext("title") == "A linked headline"
    assert item.findtext("link") == "https://example.com/story"
    assert item.findtext("description") == "An original summary about the event."
