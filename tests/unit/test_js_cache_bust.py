"""
tests/unit/test_js_cache_bust.py
Bitcoin Intel — страж синхронности cache-busting хешей (2026-07-25).

КОНТЕКСТ: scripts/update_js_cache_bust.py вписывает ?v=<content-hash> в
<script src="js/app-*.js?v=...">. Это производный артефакт — если кто-то
поправит js/app-main.js и забудет перезапустить скрипт перед коммитом,
index.html будет ссылаться на СТАРЫЙ хеш, но браузер получит НОВОЕ
содержимое файла по факту (сам путь без хеша в имени, хеш только в
query) — то есть застревание кэша, ради предотвращения которого весь
механизм и создавался, тихо не сработает. Тот же класс защиты, что
test_signals_md_sync.py/test_site_map_sync.py — процедура без теста не
держится в этом проекте (AD-6).
"""
import hashlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"

HASH_LENGTH = 10
JS_FILES = ["js/app-early.js", "js/app-main.js"]


def _content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:HASH_LENGTH]


def _declared_hash_in_html(html: str, js_relpath: str) -> str | None:
    m = re.search(
        r'<script src="' + re.escape(js_relpath) + r'\?v=([0-9a-f]+)"></script>',
        html,
    )
    return m.group(1) if m else None


def test_js_files_are_referenced_with_cache_bust_param():
    """Каждый JS-файл должен подключаться с ?v=<hash>, не голым src —
    иначе защита от устаревшего кэша браузера отсутствует вовсе."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for js_relpath in JS_FILES:
        declared = _declared_hash_in_html(html, js_relpath)
        assert declared is not None, (
            f"<script src=\"{js_relpath}\"> не содержит ?v=<hash> — "
            "запусти python3 scripts/update_js_cache_bust.py"
        )


def test_declared_hash_matches_actual_file_content():
    """Ловит именно забытый перезапуск скрипта после правки JS: если
    содержимое файла изменилось, а index.html всё ещё ссылается на
    старый хеш — тест должен упасть, не проходить молча."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    mismatches = []
    for js_relpath in JS_FILES:
        js_path = REPO_ROOT / js_relpath
        actual = _content_hash(js_path)
        declared = _declared_hash_in_html(html, js_relpath)
        if declared != actual:
            mismatches.append((js_relpath, declared, actual))

    assert not mismatches, (
        "Хеш cache-busting в index.html не совпадает с реальным содержимым "
        f"файла: {mismatches}. Запусти python3 scripts/update_js_cache_bust.py "
        "перед коммитом — правил js/app-early.js или js/app-main.js и забыл "
        "пересчитать хеш."
    )


def test_hash_length_matches_script_convention():
    """Явная проверка длины хеша — если кто-то поменяет HASH_LENGTH в
    самом скрипте, не обновив этот тест, расхождение будет заметно, а не
    тихо подстроится под что угодно."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for js_relpath in JS_FILES:
        declared = _declared_hash_in_html(html, js_relpath)
        assert declared is not None
        assert len(declared) == HASH_LENGTH, (
            f"{js_relpath}: длина хеша {len(declared)}, ожидалось {HASH_LENGTH}"
        )
