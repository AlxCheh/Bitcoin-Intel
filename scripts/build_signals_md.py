"""
scripts/build_signals_md.py
Bitcoin Intel — детерминированный генератор SIGNALS.md из signals.json.

ПРОБЛЕМА, КОТОРУЮ РЕШАЕТ ЭТОТ СКРИПТ: SIGNALS.md с самого начала объявлял себя
"читаемой проекцией" signals.json ("регенерируется из него" — см. шапку файла),
но фактически годами редактировался руками при добавлении каждого сигнала
(правило CLAUDE.md "два файла одновременно"). Без механизма это неизбежно
разошлось: к 2026-07-19 обнаружено, что последние ~12 сигналов дописывались
в конец файла произвольно, а не в отсортированную по правилу файла позицию
("Сортировка — по date убыванию, при равенстве дат — по id") — тот же класс
проблемы, для которого в проекте уже заведены FACTS и SITE_MAP (AD-6:
процедура без механизма не держится).

РЕШЕНИЕ: SIGNALS.md больше не редактируется руками. Он — производный файл,
как data/facts.json — регенерируется этим скриптом целиком из signals.json.
Тест-страж (tests/unit/test_signals_md_sync.py) проверяет двусторонне, что
файл на диске совпадает с выводом генератора байт-в-байт.

Запускать после КАЖДОГО изменения signals.json (нового сигнала, правки
существующего):
    python3 scripts/build_signals_md.py

Тай-брейк сортировки (date DESC, при равенстве — id DESC) выведен эмпирически
из ещё не разъехавшейся части существовавшего файла (группы сигналов с
одинаковой date шли в убывающем алфавитном порядке id) — не выдуман заново.

Архивный хвост ("## Архивные заметки по разделам сайта") не выводится из
signals.json (доисторический контент без id/theme/links) — сохраняется
дословно как ARCHIVED_TAIL ниже; при следующей ручной правке этого раздела
редактировать ARCHIVED_TAIL в этом файле, не SIGNALS.md напрямую.
"""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIGNALS_JSON_PATH = os.path.join(REPO_ROOT, "signals.json")
SIGNALS_MD_PATH = os.path.join(REPO_ROOT, "SIGNALS.md")

HEADER = """# SIGNALS.md — База сигналов и накопленные материалы

> Часть проекта Bitcoin-Intel. Основной файл: [CLAUDE.md](CLAUDE.md)
> Источник истины по содержимому — `signals.json`; этот файл — его читаемая проекция, регенерируется из него.
>
> **Конвенция:** один сигнал = один блок `##`. Сортировка — по `date` убыванию, при равенстве дат — по `id`.
> Обновляется при каждом новом сигнале (правило «два файла одновременно», см. CLAUDE.md).

---

"""

# Дословно сохранённый архивный раздел (не выводится из signals.json —
# доисторический контент без id/theme/links). См. docstring выше.
ARCHIVED_TAIL = """## Архивные заметки по разделам сайта

> Не сигналы в текущей схеме (нет `id`/`theme`/`links`) — описания состояния отдельных блоков сайта на момент написания. Сохранены как есть, без привязки к формату сигнала.

### ⛏️ Майнинг — Production Cost (2026-06)
### ⛏️ Майнинг — блок «Последние блоки» (2026-06)
### ⛏️ Майнинг — вкладка ПУЛЫ (2026-06)
### 🏦 РЫНОК — единая база сигналов (2026-06)
### 🔗 Layer 2 — категория (2026-06)
### 🏛️ ВЛАДЕНИЕ — категория (2026-06)
### ⚡ LIGHTNING NETWORK — объём $1 млрд (2026-06-21)

Содержимое этих заметок на момент рефакторинга (2026-07-03) не восстановлено дословно — оригинальные тексты доступны в истории git (`git log -p -- SIGNALS.md`) при необходимости.
"""

DIR_EMOJI = {"pos": "🟢", "neg": "🔴", "neu": "⚪"}

ROLE_GLOSS = {
    "trigger": "открывает цепочку",
    "complication": "усложняет нарратив",
    "resolution": "закрывает противоречие",
    "background": "структурный контекст",
}

LINK_ORDER = ["confirms", "contradicts", "context_chain"]


def render_links(links: dict) -> str:
    """'confirms → A, B · contradicts → C' — пусто, если все три типа пусты."""
    parts = []
    for kind in LINK_ORDER:
        ids = links.get(kind) or []
        if ids:
            parts.append(f"{kind} → {', '.join(ids)}")
    return " · ".join(parts)


def render_signal_block(s: dict) -> str:
    header = (
        f"## {s['id']} · {s['catLabel']} · {s['date']} · "
        f"{DIR_EMOJI.get(s['dir'], '⚪')} {s['dir']} · {s['horizon']} · `{s['cluster']}`"
    )

    lines = [header, "", f"**Сигнал:** {s['signal']}", "", "**Данные:**"]
    for item in s.get("data", []):
        lines.append(f"- {item}")

    lines += ["", f"**Контекст:** {s['context']}", "", f"**Оговорки:** {s['caveat']}"]

    alternatives = s.get("alternatives_considered") or []
    if alternatives:
        lines += ["", "**Альтернативы:** " + " ".join(alternatives)]

    alt_scenario = s.get("alternative_scenario")
    if alt_scenario:
        lines += ["", f"**Альтернативный сценарий:** {alt_scenario}"]

    role = s["narrative_role"]
    lines += [
        "",
        f"**Нарратив:** {role} — {ROLE_GLOSS.get(role, '')}",
        f"**Tension:** «{s['tension']}»",
        "",
        f"**Макровывод:** {s['macro_implication']}",
    ]

    links_line = render_links(s.get("links", {}))
    if links_line:
        lines += ["", f"**Связи:** {links_line}"]

    lines += ["", f"**Источник:** {s['source']}", "", "---", ""]
    return "\n".join(lines)


def build(signals_json_path: str = SIGNALS_JSON_PATH) -> str:
    with open(signals_json_path, encoding="utf-8") as f:
        data = json.load(f)

    signals = sorted(
        data["signals"],
        key=lambda s: (s["date"], s["id"]),
        reverse=True,
    )

    body = "\n".join(render_signal_block(s) for s in signals)
    return HEADER + body + "\n" + ARCHIVED_TAIL


def main():
    output = build()
    with open(SIGNALS_MD_PATH, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"OK: SIGNALS.md перегенерирован ({SIGNALS_MD_PATH})")


if __name__ == "__main__":
    sys.exit(main())
