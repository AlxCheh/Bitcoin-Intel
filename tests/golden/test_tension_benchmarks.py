"""
tests/golden/test_tension_benchmarks.py
Bitcoin Intel — Sprint 0 / GH Issue #81 (Narrative Benchmarks).

Golden Dataset (tests/golden/) ловит СТРУКТУРНЫЕ регрессии алгоритма синтеза.
quality_report.py::tension_valid() уже проверяет формулу (заглавная буква +
наличие маркера vs/несмотря на/при условии/вопреки/тире) — этот файл НЕ
дублирует ту проверку, а добавляет то, чего там нет: длину и различимость
двух сторон конфликта.

╔══════════════════════════════════════════════════════════════════════╗
║ ЯВНАЯ ГРАНИЦА SCOPE (см. docs/SPRINT0_PLAN.md, docs/ERB_REPORT_v1.md   ║
║ Этап 4): это МЕХАНИЧЕСКИЕ синтаксические эвристики — длина, наличие    ║
║ маркера, пересечение слов между сторонами конфликта. Это НЕ оценка     ║
║ смысловой убедительности/связности tension. Настоящая семантическая    ║
║ оценка потребовала бы либо LLM-judge, либо человеческой разметки —     ║
║ и то, и другое противоречило бы принципу "детерминированный алгоритм,  ║
║ не LLM-инференс в проде", уже установленному для synthesizer.py.       ║
║ Ложные срабатывания в обе стороны здесь ожидаемы и допустимы.          ║
╚══════════════════════════════════════════════════════════════════════╝

Фикстуры "хороший/плохой tension" взяты из уже курированных таблиц ❌/✅ в
CLAUDE.md/docs/ALGORITHM.md (2 примера) и реальных записанных сигналов из
signals.json (4 примера, скопированы как строковые литералы — не читаются
из живого файла, чтобы тест не ломался при будущих правках данных).
"""
import re

import pytest

from scripts.quality_report import TENSION_MARKERS

MIN_LENGTH = 40
MAX_LENGTH = 220
MIN_WORDS_PER_SIDE = 3
MAX_WORD_OVERLAP_RATIO = 0.5

# Мини-стоп-лист — не NLP-грамматика, просто самые частые служебные слова,
# которые не несут различительной информации о механизме по обе стороны.
STOPWORDS = {
    "и", "в", "на", "не", "с", "со", "за", "для", "из", "при", "к", "ко",
    "от", "по", "что", "это", "как", "но", "а", "то", "же", "уже", "ещё",
    "чем", "или", "vs", "btc", "bitcoin",
}


def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[а-яa-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def _find_marker(tension: str) -> str | None:
    # Длинные маркеры сначала — "при условии" не должен матчиться как часть
    # чего-то короче.
    for marker in sorted(TENSION_MARKERS, key=len, reverse=True):
        if marker.strip() and marker in tension:
            return marker
    return None


def has_two_distinct_mechanisms(tension: str) -> tuple[bool, str]:
    """
    Возвращает (прошёл_ли, причина). Причина — для читаемого сообщения
    в assert, не для программной логики.
    """
    if not (MIN_LENGTH <= len(tension) <= MAX_LENGTH):
        return False, f"длина {len(tension)} вне диапазона [{MIN_LENGTH}, {MAX_LENGTH}]"

    marker = _find_marker(tension)
    if marker is None:
        return False, "маркер противопоставления не найден"

    idx = tension.find(marker)
    left, right = tension[:idx], tension[idx + len(marker):]
    left_words, right_words = _significant_words(left), _significant_words(right)

    if len(left_words) < MIN_WORDS_PER_SIDE or len(right_words) < MIN_WORDS_PER_SIDE:
        return False, (
            f"недостаточно слов по одну из сторон "
            f"({len(left_words)} / {len(right_words)}, минимум {MIN_WORDS_PER_SIDE})"
        )

    overlap = left_words & right_words
    smaller = min(len(left_words), len(right_words))
    overlap_ratio = len(overlap) / smaller if smaller else 1.0
    if overlap_ratio > MAX_WORD_OVERLAP_RATIO:
        return False, (
            f"стороны слишком похожи по словам (overlap={overlap_ratio:.2f}, "
            f"общие: {overlap})"
        )

    return True, "ok"


# ─── Golden-фикстуры ────────────────────────────────────────────────────────

# Источник: CLAUDE.md / docs/ALGORITHM.md, таблица «Правила хорошего tension»
GOOD_TENSIONS_FROM_DOCS = [
    "Strategy наращивает долг для покупки BTC vs рынок ставит NAV-дисконт 0.83x",
    "ETF-оттоки как поверхностное давление vs долгосрочные держатели покупают в 10x больше",
]

# Источник: реальные записанные сигналы signals.json (скопированы как литералы)
GOOD_TENSIONS_FROM_REAL_SIGNALS = [
    "Рекордный отток из ETF на фоне падения BTC — розничный инвестор выходит именно когда институционал покупает",
    "LTH держат рекордные 14.8 млн BTC несмотря на 5.58 млн в убытке — vs рынок в режиме медвежьего дна с 10.83 млн",
    "Strategy покупает BTC пока рынок отвлечён SpaceX — институциональное накопление не коррелирует с медиа-повесткой",
    "Регулятор создаёт очередь на мощности — майнеры с гибкой нагрузкой получают структурное преимущество перед чисто майнинговыми операторами",
]

# Источник: CLAUDE.md таблица «❌ Плохо» + сконструированные анти-паттерны
BAD_TENSIONS = [
    "Strategy продолжает покупать BTC",  # факт, не конфликт, нет маркера
    "ETF показал отток",                 # то же самое, слишком коротко
    "BTC vs BTC",                        # маркер есть, но нет различимых сторон
    "Рынок падает vs рынок снижается",   # маркер есть, стороны — перефраз друг друга
    "X vs Y",                            # формально валиден по маркеру, содержательно пуст
]


@pytest.mark.parametrize("tension", GOOD_TENSIONS_FROM_DOCS + GOOD_TENSIONS_FROM_REAL_SIGNALS)
def test_good_tension_passes_benchmark(tension):
    passed, reason = has_two_distinct_mechanisms(tension)
    assert passed, f"Ожидался PASS для «{tension}», получено: {reason}"


@pytest.mark.parametrize("tension", BAD_TENSIONS)
def test_bad_tension_fails_benchmark(tension):
    passed, reason = has_two_distinct_mechanisms(tension)
    assert not passed, f"Ожидался FAIL для «{tension}», но эвристика пропустила"


def test_all_real_signals_tension_pass_benchmark():
    """
    Не просто golden-фикстуры — реальная база на момент запуска. Явно НЕ
    падает тест сюит целиком при одном плохом tension (это бы противоречило
    non-blocking духу мониторинга Sprint 0) — печатает список нарушителей,
    падает только если ДОЛЯ нарушений подозрительно высокая (>20%), что
    сигнализировало бы о системной проблеме, не об единичном случае.
    """
    import json
    from pathlib import Path

    signals_path = Path(__file__).resolve().parents[2] / "signals.json"
    with open(signals_path, encoding="utf-8") as f:
        signals = json.load(f)["signals"]

    failures = []
    for s in signals:
        tension = s.get("tension", "")
        passed, reason = has_two_distinct_mechanisms(tension)
        if not passed:
            failures.append((s.get("id", "?"), reason))

    failure_ratio = len(failures) / len(signals) if signals else 0.0
    if failures:
        print(f"\n{len(failures)}/{len(signals)} сигналов не прошли benchmark (эвристика, не приговор):")
        for sig_id, reason in failures:
            print(f"  {sig_id}: {reason}")

    assert failure_ratio <= 0.2, (
        f"{failure_ratio*100:.0f}% сигналов не проходят narrative benchmark — "
        f"это уже не единичные ложные срабатывания эвристики, а возможный "
        f"системный сдвиг в качестве tension"
    )
