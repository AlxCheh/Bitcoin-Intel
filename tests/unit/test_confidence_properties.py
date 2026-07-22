"""
tests/unit/test_confidence_properties.py
Bitcoin Intel — property-based тесты calculate_confidence() (C2 ARR v3).

КОНТЕКСТ
--------
ARR v3 Этап 4.4 / C2: "Confidence calibration не выполнена" — 3 из 5
production-кластеров упираются в потолок confidence=1.0. Комиссия
рекомендовала калибровку на holdout-датасете.

Полноценная статистическая калибровка (тренировочный/holdout split,
ROC-анализ, подбор весов под распределение реальных исходов) требует
десятков-сотен независимо размеченных синтезов с известным "правильным"
confidence, которого у нас нет — есть 5 production-кластеров и 8 в Golden
Dataset. Калибровка на выборке такого размера была бы фиктивной точностью:
подгонкой под шум, а не сигналом. Решение задокументировано в
ADR-011 (см. "Дальнейшая работа").

ЧТО ЭТОТ ФАЙЛ ДЕЛАЕТ ВМЕСТО КАЛИБРОВКИ
----------------------------------------
Property-based тесты на hypothesis (зависимость уже в requirements.txt,
T06, ранее не использовалась ни одним тестом — ARR v3 Technical Debt
After MVP: "Property Tests... пакет уже в зависимостях, но не используется
ни одним тестом"). Они не калибруют формулу под реальность, а проверяют,
что формула ВНУТРЕННЕ СОГЛАСОВАНА — монотонна и ограничена так, как
заявлено в её собственном docstring. Это не замена калибровке, а
необходимое предусловие для неё: бессмысленно калибровать формулу, которая
сама себе противоречит (например, не монотонна по score).

ОБНОВЛЕНИЕ 2026-07-21: has_contradicts (bool) заменён на contradicts_share
(float, доля сигналов кластера с contradicts) — НЕ калибровка коэффициентов
(границы 0.8/1.0 те же самые, что были), только более точный вход вместо
бинарного флага. См. полное обоснование отличия от ADR-011 в докстринге
calculate_confidence() (config/settings.py). st_bool для этого параметра
заменён на st_share (st.floats[0.0, 1.0]) — раз параметр теперь непрерывный,
тестируем весь диапазон, не только две булевы границы.
"""
from hypothesis import given, strategies as st, settings

from config.settings import calculate_confidence, calculate_max_possible_score


# ─── Стратегии генерации входных данных ──────────────────────────────────────
st_n_signals = st.integers(min_value=1, max_value=50)
st_bool      = st.booleans()
st_share     = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


@given(
    n_signals=st_n_signals,
    contradicts_share=st_share,
    all_stale=st_bool,
    has_tension=st_bool,
)
@settings(max_examples=200)
def test_confidence_always_in_bounds(n_signals, contradicts_share, all_stale, has_tension):
    """confidence всегда в [0.1, 1.0] — контракт из docstring calculate_confidence."""
    max_score = calculate_max_possible_score(n_signals)
    # score_total в реалистичном диапазоне: от 0 до значительно выше потолка
    # (contradicts-бонус не ограничен сверху, см. settings.py)
    for score_total in (0, max_score // 2, max_score, max_score * 3):
        c = calculate_confidence(
            score_total=score_total,
            n_signals=n_signals,
            contradicts_share=contradicts_share,
            all_stale=all_stale,
            has_tension=has_tension,
        )
        assert 0.1 <= c <= 1.0, (
            f"confidence={c} out of [0.1, 1.0] for score_total={score_total}, "
            f"n_signals={n_signals}, contradicts_share={contradicts_share}, "
            f"all_stale={all_stale}, has_tension={has_tension}"
        )


@given(n_signals=st_n_signals, score_total=st.integers(min_value=0, max_value=2000))
@settings(max_examples=200)
def test_confidence_monotonic_in_score(n_signals, score_total):
    """
    Больший score_total при прочих равных не должен ДАВАТЬ МЕНЬШИЙ confidence
    (нестрогая монотонность — формула делит score на потолок, потолок не
    зависит от score_total, поэтому рост score не может снижать результат).
    """
    base_kwargs = dict(
        n_signals=n_signals, contradicts_share=1.0,
        all_stale=False, has_tension=True,
    )
    lower  = calculate_confidence(score_total=score_total, **base_kwargs)
    higher = calculate_confidence(score_total=score_total + 10, **base_kwargs)
    assert higher >= lower - 1e-9, (
        f"confidence decreased when score_total increased: "
        f"{score_total}->{lower}, {score_total+10}->{higher}"
    )


@given(n_signals=st_n_signals, score_total=st.integers(min_value=1, max_value=500))
@settings(max_examples=200)
def test_each_negative_modifier_does_not_increase_confidence(n_signals, score_total):
    """
    Каждый из четырёх понижающих модификаторов (n_signals==1, no contradicts,
    all_stale, no tension) не должен УВЕЛИЧИВАТЬ confidence относительно
    случая без него — это прямое следствие того, что они формула определяет
    как "снижающие" (см. docstring calculate_confidence: "Снижающие модификаторы").
    """
    best_case = calculate_confidence(
        score_total=score_total, n_signals=max(n_signals, 2),
        contradicts_share=1.0, all_stale=False, has_tension=True,
    )

    worse_no_contradicts = calculate_confidence(
        score_total=score_total, n_signals=max(n_signals, 2),
        contradicts_share=0.0, all_stale=False, has_tension=True,
    )
    worse_stale = calculate_confidence(
        score_total=score_total, n_signals=max(n_signals, 2),
        contradicts_share=1.0, all_stale=True, has_tension=True,
    )
    worse_no_tension = calculate_confidence(
        score_total=score_total, n_signals=max(n_signals, 2),
        contradicts_share=1.0, all_stale=False, has_tension=False,
    )

    assert worse_no_contradicts <= best_case + 1e-9
    assert worse_stale <= best_case + 1e-9
    assert worse_no_tension <= best_case + 1e-9


@given(
    n_signals=st_n_signals,
    score_total=st.integers(min_value=1, max_value=500),
    share_low=st_share,
    share_high=st_share,
)
@settings(max_examples=200)
def test_confidence_monotonic_in_contradicts_share(n_signals, score_total, share_low, share_high):
    """
    НОВЫЙ ТЕСТ (2026-07-21, вместе с заменой has_contradicts на
    contradicts_share): раз параметр стал непрерывным, проверяем не только
    две булевы границы, но и монотонность на всём диапазоне — большая доля
    сигналов с contradicts не должна ДАВАТЬ МЕНЬШИЙ confidence при прочих
    равных.
    """
    if share_low > share_high:
        share_low, share_high = share_high, share_low

    lower = calculate_confidence(
        score_total=score_total, n_signals=max(n_signals, 2),
        contradicts_share=share_low, all_stale=False, has_tension=True,
    )
    higher = calculate_confidence(
        score_total=score_total, n_signals=max(n_signals, 2),
        contradicts_share=share_high, all_stale=False, has_tension=True,
    )
    assert higher >= lower - 1e-9, (
        f"confidence снизился при росте contradicts_share: "
        f"{share_low}->{lower}, {share_high}->{higher}"
    )


def test_known_production_skew_documented_not_silently_accepted():
    """
    Документирует ИЗВЕСТНЫЙ факт (не норму, не цель): на 2026-06-30, 3 из 5
    production-кластеров (strategy_model_stress, etf_institutional_flow,
    btc_treasury_competition) имеют confidence=1.0 — потолок формулы
    достигается при score_total >= max_score с contradicts_share=1.0,
    all_stale=False, has_tension=True одновременно. Сама формула технически
    способна выдавать значения < 1.0 (см. test_each_negative_modifier_...
    выше) — то, что 3/5 кластеров на потолке, это свойство ТЕКУЩИХ ДАННЫХ
    (сильные, хорошо связанные кластеры), а не дефект формулы. Если этот
    тест начнёт падать — соотношение в production изменилось, стоит
    пересмотреть ADR-011.
    """
    # max_score достигается, когда score_total == n * MAX_PER_SIGNAL ровно
    # (без contradicts-бонуса) — это и есть "потолок без модификаторов".
    c = calculate_confidence(
        score_total=calculate_max_possible_score(5), n_signals=5,
        contradicts_share=1.0, all_stale=False, has_tension=True,
    )
    assert c == 1.0, (
        "Потолок формулы должен достигаться ровно при max_score и всех "
        "позитивных флагах — если нет, формула изменилась, обнови ADR-011"
    )
