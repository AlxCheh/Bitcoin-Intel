"""
tests/unit/test_site_map_sync.py
Bitcoin Intel — тест-страж синхронизации data/site_map.json с index.html.

Проблема, которую решает: манифест — единственный источник истины по
структуре сайта (аналог FACTS, но для СТРУКТУРЫ, не данных). Без
механизированной проверки он неизбежно разойдётся с реальным HTML при
следующей правке — тот же урок, что и с AD-6 (схема сигнала) и FACTS
Фаза 5 (устаревшие данные): процедура без теста не держится в этом
проекте.

Проверяет ОБЕ стороны:
1. Каждая запись манифеста (title) должна встречаться в index.html —
   иначе панель удалена/переименована, а манифест не обновлён.
2. Каждый panel-title/acc-label в index.html (кроме известных
   JS-шаблонных срабатываний) должен иметь запись в манифесте —
   иначе появилась новая панель, которую забыли туда добавить.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Заголовки, которые технически совпадают с panel-title/acc-label, но не
# являются самостоятельными разделами сайта (плейсхолдеры, шум JS-рендера,
# заголовки повторно используемых внутри карточек под-меток) — не требуют
# отдельной записи в манифесте.
KNOWN_NON_ENTRIES = {
    "загрузка...",
}


def _load_manifest():
    with open(os.path.join(ROOT, "data", "site_map.json"), encoding="utf-8") as f:
        return json.load(f)


def _load_index_html():
    with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
        return f.read()


def _extract_static_titles(html: str) -> set:
    """panel-title/acc-label, встречающиеся как ЛИТЕРАЛЬНЫЙ текст (не JS-
    конкатенация вида ' + sanitize(x) + ') — те же критерии, что при сборке
    манифеста."""
    titles = re.findall(r'panel-title">([^<]+)</span>', html)
    titles += re.findall(r'acc-label">([^<]+)</span>', html)
    titles += re.findall(r'instrument-ticker">([^<]+)</span>', html)
    clean = set()
    for t in titles:
        t = t.strip()
        if not t or "' +" in t or "sanitize(" in t or t in KNOWN_NON_ENTRIES:
            continue
        clean.add(t)
    return clean


def test_manifest_is_valid_json():
    manifest = _load_manifest()
    assert "entries" in manifest
    assert len(manifest["entries"]) > 0


def test_manifest_entries_have_required_fields():
    manifest = _load_manifest()
    required = {"id", "title", "cluster", "tab", "source", "kind", "keywords"}
    for e in manifest["entries"]:
        missing = required - set(e.keys())
        assert not missing, f"entry {e.get('id')} missing fields: {missing}"


def test_manifest_ids_are_unique():
    manifest = _load_manifest()
    ids = [e["id"] for e in manifest["entries"]]
    assert len(ids) == len(set(ids)), "дублирующиеся id в манифесте"


def test_manifest_source_values_are_documented():
    manifest = _load_manifest()
    valid_sources = set(manifest["_source_meaning"].keys())
    for e in manifest["entries"]:
        assert e["source"] in valid_sources, (
            f"{e['id']}: source={e['source']!r} не описан в _source_meaning"
        )


def test_every_manifest_title_exists_in_html():
    """Ловит: панель переименовали/удалили, манифест не обновили.
    Пропускает записи с dynamic:true — их контент целиком генерируется
    JS без статичного literal-текста для сверки (например, дайджест
    сигналов, собираемый по кластерам динамически)."""
    manifest = _load_manifest()
    html = _load_index_html()
    html_titles = _extract_static_titles(html)
    missing = [
        e["title"] for e in manifest["entries"]
        if not e.get("dynamic") and e["title"] not in html_titles
    ]
    assert not missing, (
        "Записи манифеста не найдены в index.html (панель переименована/"
        "удалена, манифест не обновлён): " + str(missing)
    )


def test_every_html_panel_title_is_in_manifest():
    """Ловит: появилась новая панель, её забыли занести в манифест."""
    manifest = _load_manifest()
    html = _load_index_html()
    html_titles = _extract_static_titles(html)
    manifest_titles = {e["title"] for e in manifest["entries"]}
    missing = html_titles - manifest_titles
    assert not missing, (
        "panel-title/acc-label в index.html без записи в data/site_map.json: "
        + str(missing)
    )
