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


def _load_jsonld_graph():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    start = html.find('application/ld+json')
    assert start != -1, "Schema.org JSON-LD блок не найден в index.html"
    script_start = html.find(">", start) + 1
    script_end = html.find("</script>", script_start)
    payload = json.loads(html[script_start:script_end])
    assert "@graph" in payload, "JSON-LD обязан быть @graph (WebSite + Dataset), не одиночным объектом"
    return payload["@graph"]


def test_index_html_has_schema_org_website_jsonld():
    graph = _load_jsonld_graph()
    website = next((n for n in graph if n.get("@type") == "WebSite"), None)
    assert website is not None, "WebSite-узел отсутствует в @graph"
    assert website["name"] == "Bitcoin Intel"
    assert "url" in website


def test_index_html_has_schema_org_dataset_with_distribution():
    """
    2026-08-18: лента данных для AI-агентов (Подход 3 из брейнсторма
    "агент должен видеть полную картину сайта") — Dataset-узел с
    distribution на signals.json/SIGNALS.md, машиночитаемо указывает
    агенту, где искать полный корпус сигналов, не полагаясь на то, что
    краулер сам догадается зайти по этим путям.
    """
    graph = _load_jsonld_graph()
    dataset = next((n for n in graph if n.get("@type") == "Dataset"), None)
    assert dataset is not None, "Dataset-узел отсутствует в @graph"
    assert "distribution" in dataset and len(dataset["distribution"]) >= 2

    formats = {d["encodingFormat"]: d["contentUrl"] for d in dataset["distribution"]}
    assert formats.get("application/json", "").endswith("signals.json")
    assert formats.get("text/markdown", "").endswith("SIGNALS.md")
    for d in dataset["distribution"]:
        assert d["@type"] == "DataDownload"


def test_index_html_has_alternate_link_autodiscovery_tags():
    """
    <link rel="alternate"> — тот же стандартный паттерн, что у RSS/Atom-
    фидов, только для JSON/Markdown-версии корпуса сигналов. Не полагается
    на то, что агент распарсит JSON-LD — обычный HTML-тег в <head>.
    """
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    head_end = html.find("</head>")
    head = html[:head_end]
    assert 'rel="alternate"' in head and 'type="application/json"' in head and 'href="signals.json"' in head
    assert 'rel="alternate"' in head and 'type="text/markdown"' in head and 'href="SIGNALS.md"' in head
