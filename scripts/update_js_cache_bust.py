"""
scripts/update_js_cache_bust.py
Bitcoin Intel — content-hash cache-busting для js/app-early.js и
js/app-main.js (2026-07-25).

ПРОБЛЕМА: после выноса JS из index.html в отдельные файлы (v8.15),
<script src="js/app-main.js"> подключается без версионирования — если
GitHub Pages отдаёт статические .js с кэшируемыми заголовками, браузер
пользователя со старой закэшированной версией файла может не увидеть
новый код после деплоя, пока кэш не истечёт сам. Раньше (JS инлайн в
index.html) это было невозможно — новый HTML всегда нёс актуальный код
с собой.

РЕШЕНИЕ: query-параметр ?v=<hash>, где hash — усечённый SHA256 от
содержимого самого файла (не timestamp, не номер коммита) — тот же
принцип, что используют бандлеры (webpack contenthash). Меняется
содержимое файла -> меняется hash -> меняется URL -> браузер обязан
перезапросить, даже при агрессивном Cache-Control. Не меняется
содержимое -> тот же hash -> кэш работает как задумано, лишних
перезапросов нет (в отличие от timestamp/Date.now(), который бастил бы
кэш при КАЖДОЙ загрузке страницы без необходимости).

Производный артефакт (query-параметр в index.html) — не редактируется
руками, тот же класс, что SIGNALS.md/facts.json/site_map.json: пересчёт
через этот скрипт, синхронность проверяет tests/unit/test_js_cache_bust.py.

Использование (запускать после ЛЮБОЙ правки js/app-early.js или
js/app-main.js, перед коммитом):
    python3 scripts/update_js_cache_bust.py
"""
import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"

# Короче полного SHA256 — этого достаточно для целей cache-busting
# (не криптографическая защита, просто детерминированный отпечаток
# содержимого); 10 hex-символов = 40 бит, коллизия практически невозможна
# для пары файлов, которые между собой заведомо разные.
HASH_LENGTH = 10

JS_FILES = ["js/app-early.js", "js/app-main.js"]


def content_hash(path: Path, length: int = HASH_LENGTH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:length]


def update_script_tag(html: str, js_relpath: str, new_hash: str) -> str:
    """
    Заменяет <script src="js/app-X.js"> или <script src="js/app-X.js?v=OLD">
    на <script src="js/app-X.js?v=NEW"> — работает и при первом запуске
    (параметра ещё нет), и при последующих (параметр уже есть, меняется).
    """
    pattern = re.compile(
        r'<script src="' + re.escape(js_relpath) + r'(?:\?v=[0-9a-f]+)?"></script>'
    )
    replacement = f'<script src="{js_relpath}?v={new_hash}"></script>'
    new_html, count = pattern.subn(replacement, html)
    if count == 0:
        raise ValueError(
            f"Тег <script src=\"{js_relpath}\"> (с параметром ?v= или без) "
            "не найден в index.html — переименовали файл или изменили формат тега?"
        )
    if count > 1:
        raise ValueError(
            f"Найдено {count} тегов для {js_relpath} — ожидался ровно один, "
            "проверить index.html на дубликаты"
        )
    return new_html


def main() -> int:
    html = INDEX_HTML.read_text(encoding="utf-8")
    changed = False

    for js_relpath in JS_FILES:
        js_path = REPO_ROOT / js_relpath
        if not js_path.exists():
            print(f"::error::{js_relpath} не найден", file=sys.stderr)
            return 1
        new_hash = content_hash(js_path)
        old_html = html
        html = update_script_tag(html, js_relpath, new_hash)
        if html != old_html:
            changed = True
            print(f"{js_relpath}: ?v={new_hash}")

    if changed:
        INDEX_HTML.write_text(html, encoding="utf-8")
        print("OK: index.html обновлён")
    else:
        print("OK: хеши уже актуальны, index.html не изменён")
    return 0


if __name__ == "__main__":
    sys.exit(main())
