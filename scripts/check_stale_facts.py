"""
scripts/check_stale_facts.py
Bitcoin Intel — сторожевой аудит против повторного дрейфа (FACTS Фаза 5).

Проблема, которую решает: миграция на FACTS (CLAUDE.md v8.2-8.3) была
процедурной — я вручную искал захардкоженные числа и переводил на
data-fact-key. Процедура без механизма проверки исторически не держится
в этом проекте (см. AD-6: схема сигнала расходилась с CLAUDE.md, пока не
появился test_claude_md_schema_sync.py). Этот скрипт — механизм: он не
чинит расхождения (как build_facts.py умеет для TREASURY_HOLDERS.json),
а НАХОДИТ их и явно указывает на находку, чтобы новая партия захардкоженных
копий не накопилась незамеченной за полгода, как уже случилось один раз.

Логика:
1. Для каждого отслеживаемого key берётся ПОЛНАЯ история значений из
   signals.json (build_facts.superseded_values), не только текущее.
2. index.html сканируется на предмет любого из УСТАРЕВШИХ значений,
   встреченного голым текстом — ВНЕ <span data-fact-key="...">...</span>
   (там устаревший текст безопасен — это просто placeholder до JS-рендера,
   applyFactsToDOM() его перезапишет при загрузке страницы).
3. TREASURY_HOLDERS.json проверяется отдельно (там build_facts.py уже
   чинит расхождения сам — эта проверка на случай если синхронизация
   почему-то не отработала, а не основной механизм для этого файла).

Это НЕ доказательство отсутствия дрейфа в принципе — только то, что
УЖЕ ИЗВЕСТНЫЕ отслеживаемые факты (facts[] в сигналах) не имеют забытых
копий устаревшего значения. Числа, которые вообще не заведены как факт,
этим скриптом не проверяются — см. CLAUDE.md 'Текущий охват'.

Использование:
    python3 scripts/check_stale_facts.py           # печатает отчёт, exit 1 если найдено
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_facts import load_signals, superseded_values  # noqa: E402

INDEX_HTML = REPO_ROOT / "index.html"
TREASURY_PATH = REPO_ROOT / "TREASURY_HOLDERS.json"

FACT_KEY_TAG_RE = re.compile(r'<(\w+)[^>]*\bdata-fact-key="[^"]*"[^>]*>.*?</\1>', re.S)
# JS-константы вида `const MSTR_BTC_RESERVE = 847363;` — намеренные
# fallback-значения на случай если facts.json не загрузился (см. приоритет
# в fetchMstrData: facts.json → meta → константа). Это не дублирующее
# отображение факта, а запасной вариант ниже по приоритету — исключаем
# явно, не молча, чтобы будущий читатель понимал почему.
JS_CONST_FALLBACK_RE = re.compile(r'const\s+\w+\s*=\s*[\d.]+;')


def strip_safe_spans(html: str) -> str:
    """Убирает содержимое ЛЮБОГО тега с data-fact-key (span, div и т.п.) —
    там placeholder-текст безопасен (перезаписывается JS при загрузке),
    не считается находкой. Также убирает JS-константы fallback (см. выше)."""
    html = FACT_KEY_TAG_RE.sub("", html)
    html = JS_CONST_FALLBACK_RE.sub("", html)
    return html


def number_variants(value) -> list[str]:
    """Правдоподобные текстовые представления числа в русской типографике
    сайта: с пробелом, с запятой, без разделителя, с неразрывным пробелом."""
    if isinstance(value, float) and value == int(value):
        value = int(value)
    base = f"{value:,}" if isinstance(value, int) else f"{value:,.2f}".rstrip("0").rstrip(".")
    variants = {
        base,
        base.replace(",", " "),
        base.replace(",", "\u00a0"),
        base.replace(",", ""),
    }
    return [v for v in variants if len(v) >= 3]  # короче 3 цифр — слишком много ложных совпадений


def find_stale_occurrences() -> list[tuple[str, object, str]]:
    """Возвращает список (key, устаревшее_значение, где_найдено)."""
    signals = load_signals()
    stale_map = superseded_values(signals)
    if not stale_map:
        return []

    findings = []

    html_raw = INDEX_HTML.read_text(encoding="utf-8")
    html_safe = strip_safe_spans(html_raw)
    for key, stale_values in stale_map.items():
        for val in stale_values:
            for variant in number_variants(val):
                if variant in html_safe:
                    findings.append((key, val, f"index.html (вариант '{variant}')"))
                    break  # одного найденного варианта достаточно для этого значения

    if TREASURY_PATH.exists():
        treasury = json.loads(TREASURY_PATH.read_text(encoding="utf-8"))
        for h in treasury.get("holders", []):
            for key, stale_values in stale_map.items():
                if h.get("btc") in stale_values:
                    findings.append((key, h["btc"], f"TREASURY_HOLDERS.json (\"{h['name']}\")"))

    return findings


def main() -> int:
    findings = find_stale_occurrences()
    if not findings:
        print("OK: устаревших значений отслеживаемых фактов не найдено")
        return 0

    print("::error::Найдены забытые копии устаревших значений фактов:")
    for key, val, where in findings:
        print(f"  - {key} = {val} (устарело) — {where}")
    print(
        "\nЕсли это новое место отображения — перевести на "
        '<span data-fact-key="' + (findings[0][0] if findings else "...") + '">, '
        "как остальные (см. CLAUDE.md 'FACTS'). "
        "Если это легитимный исторический нарратив (не текущее состояние) — "
        "явно исключить в этом скрипте с комментарием почему."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
