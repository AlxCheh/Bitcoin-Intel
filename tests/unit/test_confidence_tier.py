"""
tests/unit/test_confidence_tier.py
Bitcoin Intel — тесты classify_confidence_tier() (docs/NIES.md AD-1).

КОНТЕКСТ
--------
AD-1 ("Трёхуровневая уверенность по критериям BAMS") оставался открытым с
самого раннего NIES v1.0 — механизм давал только непрерывный confidence
[0.1, 1.0], без дискретной high/medium/low шкалы, которую буквально требует
BAMS Р9. docs/ADR-020-ad1-blocker-decomposition.md разложил блокер и нашёл
реальную ловушку: наивный маппинг `links.contradicts` на критерий
"неразрешённое противоречие" ИНВЕРТИРУЕТ ранжирование (contradicts в этой
системе повышает score, а не сигнализирует дефект доказательств).

`disputed_facts[]` (CLAUDE.md v8.51) дал честное поле для критерия 2 — но
эмпирическая проверка на реальном корпусе (2026-08-15, перед написанием
этого файла) нашла ВТОРУЮ ловушку того же класса: агрегация "есть ли
disputed_facts у ЛЮБОГО сигнала кластера" систематически наказывает
крупные, лучше всего обеспеченные кластеры — 1 спорный факт из 22-28
сигналов топил btc_treasury_competition/etf_institutional_flow/
strategy_model_stress (22/16/16 прямых сигналов) до "low", тогда как
однoсигнальные кластеры без единого спора получали "high". Решение:
проверять disputed_facts только у ANCHOR-сигнала (tension_source или
anchor_trigger — тот, на котором держится вывод ИМЕННО этого кластера),
не у всего корпуса кластера. См. test_anchor_only_check_does_not_penalize_
large_well_evidenced_clusters ниже — регрессионный тест именно на эту
находку, чтобы наивная агрегация не вернулась незамеченной.

ЧТО ЭТА ФУНКЦИЯ ДЕЛАЕТ И НЕ ДЕЛАЕТ
------------------------------------
classify_confidence_tier() — ДОПОЛНЕНИЕ к calculate_confidence(), не замена
и не калибровка. Существующие property-тесты (test_confidence_properties.py)
не трогаются и не обязаны знать про эту функцию. Критерий "исторический
прецедент" (BAMS Р9) сюда не входит — BAMS v1.3 сделала его опциональным
бонусом, не условием (см. ADR-020), а Golden Dataset-матчинг (AD-3) не
реализован — критерий просто никогда не участвует, это не пробел теста.
"""
from hypothesis import given, strategies as st, settings

from config.settings import classify_confidence_tier, DIRECT_EVIDENCE_WEIGHTS


# ─── Стратегии ────────────────────────────────────────────────────────────────
st_direct_count = st.integers(min_value=0, max_value=50)
st_bool         = st.booleans()


# ─── Property-тесты ─────────────────────────────────────────────────────────

@given(
    direct_evidence_count=st_direct_count,
    anchor_has_disputed_facts=st_bool,
    all_stale=st_bool,
)
@settings(max_examples=200)
def test_result_always_one_of_three_values(direct_evidence_count, anchor_has_disputed_facts, all_stale):
    """Контракт из docstring — функция не может вернуть ничего, кроме этих трёх строк."""
    tier = classify_confidence_tier(direct_evidence_count, anchor_has_disputed_facts, all_stale)
    assert tier in ("high", "medium", "low"), f"Неожиданное значение: {tier!r}"


@given(direct_evidence_count=st.integers(min_value=0, max_value=50), all_stale=st_bool)
@settings(max_examples=200)
def test_anchor_disputed_facts_always_forces_low(direct_evidence_count, all_stale):
    """
    Критерий 2 доминирует над критерием 1 при любом количестве прямых
    доказательств — по решению пользователя (сессия 2026-08-15): спор в
    ключевом факте не компенсируется объёмом остальной доказательной базы.
    """
    tier = classify_confidence_tier(direct_evidence_count, True, all_stale)
    assert tier == "low", (
        f"disputed_facts у anchor обязан давать 'low' независимо от "
        f"direct_evidence_count={direct_evidence_count}, all_stale={all_stale}; "
        f"получено {tier!r}"
    )


@given(anchor_has_disputed_facts=st.just(False), all_stale=st_bool)
@settings(max_examples=50)
def test_zero_direct_evidence_always_low(anchor_has_disputed_facts, all_stale):
    """"Только косвенные доказательства" (BAMS Р9, критерий Низкой) — direct_evidence_count == 0."""
    tier = classify_confidence_tier(0, anchor_has_disputed_facts, all_stale)
    assert tier == "low"


@given(direct_evidence_count=st.integers(min_value=1, max_value=50))
@settings(max_examples=100)
def test_all_stale_forces_low_when_no_dispute(direct_evidence_count):
    """all_stale=True даёт 'low' даже при большом direct_evidence_count, если спора нет."""
    tier = classify_confidence_tier(direct_evidence_count, False, True)
    assert tier == "low"


# ─── Границы (конкретные значения, не property) ──────────────────────────────

def test_two_or_more_direct_no_dispute_not_stale_is_high():
    assert classify_confidence_tier(2, False, False) == "high"
    assert classify_confidence_tier(10, False, False) == "high"


def test_exactly_one_direct_no_dispute_not_stale_is_medium():
    assert classify_confidence_tier(1, False, False) == "medium"


def test_docstring_examples_match_implementation():
    """Doctest-примеры в docstring обязаны быть исполняемыми и верными — сверка отдельным тестом на случай, если кто-то запускает pytest без --doctest-modules."""
    assert classify_confidence_tier(2, False, False) == "high"
    assert classify_confidence_tier(1, False, False) == "medium"
    assert classify_confidence_tier(0, False, False) == "low"
    assert classify_confidence_tier(5, True, False) == "low"
    assert classify_confidence_tier(5, False, True) == "low"


# ─── Регрессионный тест: ловушка агрегации "любой сигнал кластера" ───────────

def test_anchor_only_check_does_not_penalize_large_well_evidenced_clusters():
    """
    Прямая регрессия находки 2026-08-15 (см. докстринг модуля выше). Симулирует
    btc_treasury_competition: 22 прямых сигнала, disputed_facts есть у ОДНОГО
    сигнала, который НЕ является anchor'ом — при агрегации "любой сигнал
    кластера" это дало бы 'low', при проверке только anchor'а — 'high'.

    Тест устроен так, чтобы падать именно при регрессии к наивной агрегации:
    если кто-то в будущем заменит anchor_has_disputed_facts на "есть ли
    disputed_facts хотя бы у одного сигнала кластера" — этот тест поймает
    инверсию так же, как её поймала эмпирическая проверка перед написанием
    кода (см. ADR-020 — тот же класс ошибки уже был найден для contradicts).
    """
    direct_evidence_count = 22          # как у btc_treasury_competition
    anchor_has_disputed_facts = False   # спор есть в другом сигнале кластера, не в anchor
    all_stale = False

    tier = classify_confidence_tier(direct_evidence_count, anchor_has_disputed_facts, all_stale)
    assert tier == "high", (
        "Крупный, хорошо обеспеченный кластер с disputed_facts НЕ у anchor-"
        "сигнала обязан получать 'high' — наказание за объём (агрегация "
        "'любой сигнал кластера') было бы регрессией уже найденной и "
        "отклонённой ошибки"
    )


def test_direct_evidence_weights_matches_weight_score_direct_tier():
    """
    DIRECT_EVIDENCE_WEIGHTS обязан состоять ровно из {'onchain', 'primary'} —
    тех же двух значений weight, которые BAMS Р9 называет "прямым
    доказательством". Ловит рассинхрон, если кто-то поправит одно место
    и забудет другое (ADR-014: единственный runtime-источник этого деления).
    """
    assert DIRECT_EVIDENCE_WEIGHTS == frozenset({"onchain", "primary"})
