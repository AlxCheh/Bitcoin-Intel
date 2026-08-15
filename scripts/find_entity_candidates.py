#!/usr/bin/env python3
"""
scripts/find_entity_candidates.py
Bitcoin Intel — поиск имён, упомянутых в сигнале, но отсутствующих в
ENTITIES.json. Дешёвый первый фильтр для критерия значимости сущности
(CLAUDE.md, «База артефактов» → «Правила обновления»).

НАЗНАЧЕНИЕ И ГРАНИЦЫ
--------------------
Критерий CLAUDE.md — «сущность попадает в базу если упоминается в контексте
сигнала как УЧАСТНИК СОБЫТИЯ, а не просто как сравнение». Это семантическое
суждение, и оно таким и остаётся: скрипт **не решает**, кого добавлять, и не
является гейтом. Он отвечает на механический подвопрос — «какие имена в
тексте вообще не зарегистрированы» — чтобы человек не держал в голове 80
существующих сущностей при разборе каждого сигнала.

Зарегистрирован как частичное закрытие AD-9, случай 2 (docs/NIES.md).
Тот же класс инструмента и та же дисциплина, что у
scripts/find_keyword_wiki_candidates.py: ловит кандидатов, не выносит вердикт.

ИЗМЕРЕННЫЙ ПОТОЛОК МЕТОДА (2026-08-15, прогон по всему корпусу 125 сигналов)
----------------------------------------------------------------------------
В топ-30 кандидатов по частоте настоящими оказались примерно 8 —
**около трети**. Найденные реальные пробелы: Stratum V2 (сам CLAUDE.md
приводит его как пример типа `protocol`!), Ordinals, Polymarket, Bitwise,
VanEck, Franklin Templeton, Chivo, Nakamoto Inc.

Остальные две трети — систематические ложные срабатывания четырёх видов,
знать их полезно, чтобы быстро отсеивать глазами:
  1. Медиа и дата-провайдеры: Glassnode, CryptoQuant, CoinDesk, Bloomberg,
     Cointelegraph, CoinGlass, BitcoinTreasuries.net, Bitcoin Magazine.
     Помечаются флагом ⚑ (см. ниже), но НЕ скрываются — см. следующий абзац.
  2. Названия программ и инструментов: «BTC Monetization Program»,
     «Digital Credit Capital Framework».
  3. Индексы и обобщения: «Nasdaq-100», «BTC-ETF», «ETFs».
  4. Люди (Adam Back) — таксономия ENTITIES.json их не содержит (типы:
     l2 / protocol / corporate / fund / infrastructure / exchange).

ПОЧЕМУ ПОЯВЛЕНИЕ В `source` — ФЛАГ, А НЕ ФИЛЬТР
------------------------------------------------
Соблазнительно просто выкидывать всё, что встречается в поле `source`
сигнала — почти весь чистый шум из категории 1 действительно лежит там.
Проверено на реальных данных и отклонено: в `source` попадают ТАКЖЕ
Bitwise и VanEck — эмитенты ETF, то есть настоящие участники событий,
а не просто источники цитирования. Жёсткий фильтр убрал бы именно тех
кандидатов, ради которых скрипт и нужен. Поэтому такие имена помечаются
«⚑ возможно источник» и опускаются ниже в выдаче, но остаются видимыми.

ИСПОЛЬЗОВАНИЕ
-------------
    python scripts/find_entity_candidates.py STR-2026-0812-001   # один сигнал (Шаг 8)
    python scripts/find_entity_candidates.py --all               # панорама по корпусу
    python scripts/find_entity_candidates.py --all --top 50
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import ENTITIES_PATH, SIGNALS_PATH, ENCODING

# Аббревиатуры, единицы и обобщения, которые заведомо не являются сущностями.
# Не «все стоп-слова английского», а именно те, что реально встречаются в
# этом корпусе и создают шум — список пополняется по мере находок.
STOPWORDS = {
    "btc", "bitcoin", "etf", "etfs", "ai", "ceo", "cfo", "cto", "coo", "sec",
    "usd", "nav", "api", "hpc", "ath", "atm", "lth", "sth", "eh", "mw", "th",
    "q1", "q2", "q3", "q4", "usdt", "usdc", "nasdaq", "nyse", "ipo", "pipe",
    "ytd", "yoy", "qoq", "faq", "gaap", "ebitda", "defi", "nft", "dao", "p2p",
    "kyc", "aml", "imf", "gdp", "cpi", "fed", "fomc", "ecb", "boj", "form",
    "the", "and", "for", "llc", "inc", "ltd", "plc", "corp",
}

# Юридические суффиксы: имя, состоящее ТОЛЬКО из известных слов и суффиксов,
# кандидатом не считается («Riot Platforms» при известном «Riot Platforms»).
LEGAL_SUFFIXES = {
    "limited", "inc", "inc.", "corp", "corp.", "ltd", "ltd.", "llc", "plc",
    "holdings", "platforms", "technologies", "digital", "group", "capital",
    "partners", "assets", "labs", "foundation",
}

SIGNAL_ID_RE = re.compile(r"^(STR|SUP|INF|MAC|NAR)-\d{4}-\d{4}-\d{3}$")
TICKER_RE    = re.compile(r"^[A-Z]{2,5}$")
# Составное имя целиком: «Franklin Templeton», не «Franklin» + «Templeton»
NAME_RE      = re.compile(r"\b[A-Z][A-Za-z0-9&.\-]*(?:\s+[A-Z][A-Za-z0-9&.\-]*)*")

MIN_NAME_LENGTH = 4


def load_json(path: str):
    with open(path, encoding=ENCODING) as f:
        return json.load(f)


def build_known_names(entities: list[dict]) -> set[str]:
    """
    Множество известных имён — включая ОТДЕЛЬНЫЕ СЛОВА составных названий.

    Разбиение по словам критично: без него «IREN» из текста сигнала не
    сматчится на зарегистрированную «IREN Limited», и скрипт предложит
    добавить уже существующую сущность. Прототип этого скрипта реально
    допустил такую ошибку на IREN / Canaan / Fidelity / Riot — тест
    test_known_entity_short_form_not_reported закрывает эту регрессию.
    """
    known: set[str] = set()
    for entity in entities:
        known.add(entity["id"].replace("_", " ").lower())
        for part in entity["id"].split("_"):
            if len(part) > 2:
                known.add(part.lower())
        for chunk in re.split(r"[()/,]", entity["name"]):
            chunk = chunk.strip()
            if not chunk:
                continue
            known.add(chunk.lower())
            for word in chunk.split():
                word = word.strip(".,").lower()
                if len(word) > 2:
                    known.add(word)
    return known


def extract_candidates(signal: dict, known: set[str]) -> list[str]:
    """Имена из текста одного сигнала, которых нет среди известных."""
    text = " ".join([
        signal.get("signal", "") or "",
        " ".join(signal.get("data") or []),
        signal.get("context", "") or "",
    ])
    out: list[str] = []
    for match in NAME_RE.findall(text):
        name = match.strip(" .-")
        if len(name) < MIN_NAME_LENGTH:
            continue
        lowered = name.lower()
        if lowered in known or lowered in STOPWORDS:
            continue
        if SIGNAL_ID_RE.match(name) or TICKER_RE.match(name):
            continue
        words = [w.strip(".,").lower() for w in name.split()]
        if all(w in known or w in STOPWORDS or w in LEGAL_SUFFIXES for w in words):
            continue
        out.append(name)
    return out


def looks_like_source(name: str, signal: dict) -> bool:
    """Имя встречается в поле `source` — вероятно источник, не участник."""
    return name.lower() in (signal.get("source", "") or "").lower()


def analyze(signals: list[dict], known: set[str]) -> list[tuple[str, int, bool]]:
    """
    Возвращает [(имя, частота, похоже_на_источник)], отсортированные так,
    что непомеченные кандидаты идут первыми (они интереснее для проверки).
    """
    counts: Counter = Counter()
    source_like: dict[str, bool] = {}
    for signal in signals:
        for name in extract_candidates(signal, known):
            counts[name] += 1
            # Помечаем, если ХОТЯ БЫ в одном сигнале имя стояло в source
            source_like[name] = source_like.get(name, False) or looks_like_source(name, signal)
    return sorted(
        ((n, c, source_like[n]) for n, c in counts.items()),
        key=lambda row: (row[2], -row[1], row[0]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("signal_id", nargs="?", help="id сигнала (напр. STR-2026-0812-001)")
    parser.add_argument("--all", action="store_true", help="прогон по всему корпусу")
    parser.add_argument("--top", type=int, default=30, help="сколько кандидатов показать (для --all)")
    args = parser.parse_args()

    if not args.signal_id and not args.all:
        parser.error("укажи id сигнала или --all")

    entities = load_json(ENTITIES_PATH)["entities"]
    signals  = load_json(SIGNALS_PATH)["signals"]
    known    = build_known_names(entities)

    if args.signal_id:
        signals = [s for s in signals if s.get("id") == args.signal_id]
        if not signals:
            print(f"Сигнал {args.signal_id} не найден в {SIGNALS_PATH}", file=sys.stderr)
            return 1

    rows = analyze(signals, known)
    limit = len(rows) if args.signal_id else args.top

    scope = args.signal_id or f"весь корпус ({len(signals)} сигналов)"
    print(f"Кандидаты в ENTITIES.json — {scope}")
    print(f"Известных сущностей: {len(entities)}")
    print("ТОЛЬКО подсказка. Решение «участник события или просто сравнение/источник» — за человеком.")
    print("Измеренный потолок: настоящих примерно треть от выдачи, см. докстринг скрипта.\n")

    if not rows:
        print("  Незарегистрированных имён не найдено")
        return 0

    for name, count, is_source in rows[:limit]:
        flag = "  ⚑ возможно источник" if is_source else ""
        freq = f" ×{count}" if count > 1 else ""
        print(f"  {name}{freq}{flag}")

    if len(rows) > limit:
        print(f"\n  … ещё {len(rows) - limit} (показать больше: --top N)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
