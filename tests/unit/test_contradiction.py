"""
tests/unit/test_contradiction.py
Тесты Contradiction Detector: semantic_inverse_score.
"""
import os
import sys
import json
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _import_detector():
    """Импортирует функции из contradiction_detector."""
    from scripts.contradiction_detector import (
        semantic_inverse_score,
        suggest_contradictions,
    )
    return semantic_inverse_score, suggest_contradictions


def make_signal(sid: str, macro_impl: str, direction: str = "pos") -> dict:
    return {
        "id": sid,
        "dir": direction,
        "macro_implication": macro_impl,
        "links": {"confirms": [], "contradicts": [], "context_chain": []},
    }


# ─── semantic_inverse_score ──────────────────────────────────────────────────

def test_obvious_contradiction_inflow_outflow():
    """ETF-приток vs ETF-отток — score >= 0.5."""
    score_fn, _ = _import_detector()
    a = "ETF-приток как структурный спрос создаёт давление покупки на рынке BTC"
    b = "ETF-отток сигнализирует о выходе институционального капитала из BTC-позиций"
    score = score_fn(a, b)
    assert score >= 0.4, f"Expected contradiction score >= 0.4, got {score}"


def test_same_direction_no_contradiction():
    """Два позитивных ETF сигнала — score < 0.5."""
    score_fn, _ = _import_detector()
    a = "ETF-приток как структурный спрос создаёт давление покупки"
    b = "Институциональный приток через ETF укрепляет позицию BTC как резервного актива"
    score = score_fn(a, b)
    assert score < 0.5, f"Expected no contradiction (score < 0.5), got {score}"


def test_empty_strings_return_zero():
    """Пустые строки → 0.0, не исключение."""
    score_fn, _ = _import_detector()
    assert score_fn("", "что угодно") == 0.0
    assert score_fn("что угодно", "") == 0.0
    assert score_fn("", "") == 0.0


def test_deterministic():
    """Одинаковые входы → одинаковый результат."""
    score_fn, _ = _import_detector()
    a = "BTC-накопление корпорациями как защита от инфляции"
    b = "Продажа BTC-резервов корпорациями под давлением долговой нагрузки"
    results = {score_fn(a, b) for _ in range(5)}
    assert len(results) == 1, f"Non-deterministic: {results}"


def test_score_in_range():
    """Score всегда в [0.0, 1.0]."""
    score_fn, _ = _import_detector()
    pairs = [
        ("рост накопления BTC институционалами", "падение и ликвидация BTC-позиций"),
        ("ETF приток", "ETF отток"),
        ("укрепление", "ослабление"),
        ("одно и то же", "одно и то же"),
    ]
    for a, b in pairs:
        score = score_fn(a, b)
        assert 0.0 <= score <= 1.0, f"Score out of range for ({a!r}, {b!r}): {score}"


def test_symmetry():
    """score(a, b) ≈ score(b, a) — симметричность."""
    score_fn, _ = _import_detector()
    a = "ETF-приток создаёт структурный спрос"
    b = "ETF-отток давит на цену BTC через ликвидацию"
    diff = abs(score_fn(a, b) - score_fn(b, a))
    assert diff < 0.15, f"Asymmetric score: {score_fn(a,b)} vs {score_fn(b,a)}"


# ─── suggest_contradictions (интеграция) ─────────────────────────────────────

def test_suggest_contradictions_returns_list():
    """suggest_contradictions возвращает список без исключений."""
    _, suggest_fn = _import_detector()
    signals = [
        make_signal("A", "ETF-приток создаёт структурный спрос на BTC", "pos"),
        make_signal("B", "ETF-отток давит на цену BTC через ликвидацию позиций", "neg"),
        make_signal("C", "Lightning Network достигла рекорда транзакций", "pos"),
    ]
    result = suggest_fn(signals)
    assert isinstance(result, list)


def test_suggest_no_self_contradictions():
    """Сигнал не предлагается как противоречие самому себе."""
    _, suggest_fn = _import_detector()
    signals = [
        make_signal("A", "ETF-приток создаёт структурный спрос", "pos"),
        make_signal("B", "ETF-отток давит на цену BTC", "neg"),
    ]
    result = suggest_fn(signals)
    for item in result:
        assert item.get("from_id") != item.get("to_id"), "Self-contradiction found"


def test_precision_on_golden_pairs():
    """
    Precision на Golden Dataset >= 60% (B1 ARR v3 / B2 ARR v2).

    Путь к fixture резолвится от расположения этого тестового файла
    (Path(__file__)), а НЕ от текущей рабочей директории. Это намеренно:
    tests/conftest.py содержит autouse-фикстуру isolated_environment,
    которая на каждом тесте делает monkeypatch.chdir(tmp_path) — относительный
    путь от cwd в такой ситуации всегда резолвился бы в пустую песочницу и
    тест молча скипал бы (это и было причиной бага B1 в ARR v3: тест никогда
    не выполнялся, ни локально, ни в CI). Использование __file__ делает тест
    независимым от того, кто и откуда его запускает.
    """
    import json
    from pathlib import Path
    from scripts.contradiction_detector import semantic_inverse_score

    THRESHOLD = 0.5
    pairs_file = Path(__file__).parent.parent / "golden" / "fixtures" / "contradiction_pairs.json"
    assert pairs_file.exists(), (
        f"contradiction_pairs.json must exist at {pairs_file} — "
        "это не опциональный fixture, а обязательный quality gate (B1 ARR v3)"
    )

    dataset = json.loads(pairs_file.read_text(encoding="utf-8"))
    pairs   = dataset.get("pairs", [])
    assert len(pairs) >= 15, f"Need >= 15 pairs, got {len(pairs)}"

    correct = 0
    errors  = []
    for p in pairs:
        score    = semantic_inverse_score(p["a"], p["b"])
        predicted = score >= THRESHOLD
        if predicted == p["expected"]:
            correct += 1
        else:
            errors.append(
                f"  WRONG: expected={p['expected']}, got={predicted} "
                f"(score={score:.3f}) — {p.get('note','')}"
            )

    precision = correct / len(pairs)
    error_msg = (
        f"Precision {precision:.1%} below 60% threshold.\n"
        f"Correct: {correct}/{len(pairs)}\n"
        + "\n".join(errors[:5])
    )
    assert precision >= 0.6, error_msg


def test_suggest_contradictions_cli():
    """
    B2: suggest_contradictions() возвращает предложения для аналитика.
    Проверяет что workflow замкнут: детектор → список → аналитик.
    """
    from scripts.contradiction_detector import suggest_contradictions

    signals = [
        {"id": "A", "macro_implication": "ETF-приток создаёт устойчивый структурный спрос на BTC",
         "dir": "pos", "actor": "etf",
         "links": {"confirms":[], "contradicts":[], "context_chain":[]}},
        {"id": "B", "macro_implication": "ETF-отток сигнализирует о выходе капитала из BTC позиций",
         "dir": "neg", "actor": "etf",
         "links": {"confirms":[], "contradicts":[], "context_chain":[]}},
        {"id": "C", "macro_implication": "Lightning Network масштабируется как платёжный слой BTC",
         "dir": "pos", "actor": "defi",
         "links": {"confirms":[], "contradicts":[], "context_chain":[]}},
    ]

    suggestions = suggest_contradictions(signals)

    # Должен найти пару A-B как contradicts
    found_ab = any(
        (s.get("from_id") == "A" and s.get("to_id") == "B") or
        (s.get("from_id") == "B" and s.get("to_id") == "A")
        for s in suggestions
    )
    assert found_ab, (
        f"Detector must suggest A↔B as contradicts. "
        f"Got suggestions: {suggestions}"
    )

    # C не должен быть в contradicts с A (они об одном направлении)
    ab_scores = [s["score"] for s in suggestions
                 if "C" not in [s.get("from_id"), s.get("to_id")]]
    c_scores   = [s["score"] for s in suggestions
                  if "C" in [s.get("from_id"), s.get("to_id")]]
    # Пара A-B должна иметь более высокий score чем пары с C
    if ab_scores and c_scores:
        assert max(ab_scores) > max(c_scores), (
            f"A-B contradiction score ({max(ab_scores):.3f}) should exceed "
            f"C-pair scores ({max(c_scores):.3f})"
        )


def test_precision_test_cannot_silently_skip():
    """
    Регрессия для B1 ARR v3: исторически этот тест проходил мимо CI, потому
    что путь к fixture резолвился от cwd, а conftest.py меняет cwd на пустую
    песочницу для каждого теста (autouse isolated_environment).

    Эта проверка фиксирует инвариант: тест precision обязан читать fixture
    по абсолютному пути от __file__ и НЕ должен содержать pytest.skip() по
    причине отсутствия файла — отсутствие fixture обязано быть hard failure,
    а не тихим пропуском, иначе баг B1 может повториться в будущем для
    любого нового golden-fixture теста.
    """
    import inspect
    source = inspect.getsource(test_precision_on_golden_pairs)
    assert "pytest.skip" not in source, (
        "test_precision_on_golden_pairs не должен скипать при отсутствии "
        "fixture — отсутствие Golden Dataset обязано проваливать сборку"
    )
    assert "__file__" in source, (
        "Путь к fixture должен резолвиться от __file__, а не от cwd — "
        "иначе тест снова станет уязвим к chdir в autouse-фикстурах"
    )


def test_score_pair_does_not_double_count_direction():
    """
    Регрессия: score_pair() (полный режим для реальных сигналов с известным
    dir) не должен использовать polarity-сигнал из текста — direction уже
    достоверно дан полем `dir`. Если бы polarity дублировала dir_score,
    почти любая pos/neg-пара получала бы завышенный score независимо от
    реального лексического конфликта (баг, найденный и исправленный при
    закрытии B1 ARR v3 — изначально давал 406 кандидатов на 45 сигналах
    вместо ожидаемых единиц-десятков).
    """
    from scripts.contradiction_detector import score_pair
    from config.settings import CONTRADICTION_PROPOSAL_THRESHOLD

    # Два сигнала с противоположным dir, но БЕЗ единого лексического хита
    # INVERSE_PAIRS и без общего actor/theme — единственный сигнал конфликта
    # это поле dir.
    sig_a = {
        "id": "A", "dir": "pos", "actor": "etf", "theme": "institutionalization",
        "macro_implication": "Институциональный капитал находит новый канал входа в BTC",
    }
    sig_b = {
        "id": "B", "dir": "neg", "actor": "miner", "theme": "infrastructure",
        "macro_implication": "Майнеры сокращают операционные расходы перед халвингом",
    }
    result = score_pair(sig_a, sig_b)
    # Только dir_score (0.2 веса) должен сработать — score не должен пересекать
    # порог предложения аналитику только из-за противоположного dir.
    assert result.score < CONTRADICTION_PROPOSAL_THRESHOLD, (
        f"score_pair завысил score ({result.score}) на паре без лексического "
        f"конфликта и без общего subject — подозрение на дублирование dir "
        f"через polarity. inverse={result.inverse_score} subject={result.subject_score} "
        f"dir={result.dir_score}"
    )


def test_contradiction_threshold_sourced_from_settings():
    """
    N2 ARR v3: PROPOSAL_THRESHOLD должен быть вынесен в config/settings.py
    (CONTRADICTION_PROPOSAL_THRESHOLD), а не быть локальной константой
    только в contradiction_detector.py.
    """
    from scripts.contradiction_detector import PROPOSAL_THRESHOLD
    from config.settings import CONTRADICTION_PROPOSAL_THRESHOLD
    assert PROPOSAL_THRESHOLD == CONTRADICTION_PROPOSAL_THRESHOLD
