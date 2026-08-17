"""
tests/unit/test_aeo_foundation.py
Bitcoin Intel — regression: robots.txt/sitemap.xml/Schema.org present and
well-formed. Part of the 2026-08-16 AEO foundation — see
docs/superpowers/specs/2026-08-16-home-page-reorg-design.md Часть 2.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def test_robots_txt_exists_and_allows_ai_crawlers():
    robots = (REPO_ROOT / "robots.txt").read_text(encoding="utf-8")
    for bot in ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot"]:
        assert bot in robots, f"{bot} не упомянут в robots.txt"
    assert "Sitemap:" in robots
    assert "Disallow: /" not in robots.split("User-agent: *")[1].split("User-agent:")[0], (
        "User-agent: * не должен блокировать сайт целиком"
    )


def test_sitemap_xml_is_valid_xml_with_root_url():
    sitemap_path = REPO_ROOT / "sitemap.xml"
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = root.findall("sm:url/sm:loc", ns)
    assert len(urls) >= 1
    assert "alxcheh.github.io/Bitcoin-Intel" in urls[0].text


def test_index_html_has_schema_org_website_jsonld():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    start = html.find('application/ld+json')
    assert start != -1, "Schema.org JSON-LD блок не найден в index.html"
    script_start = html.find(">", start) + 1
    script_end = html.find("</script>", script_start)
    payload = json.loads(html[script_start:script_end])
    assert payload["@type"] == "WebSite"
    assert payload["name"] == "Bitcoin Intel"
    assert "url" in payload
