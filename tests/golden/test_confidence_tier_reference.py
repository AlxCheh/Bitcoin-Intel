"""
tests/golden/test_confidence_tier_reference.py
Bitcoin Intel — регрессия правила Р9 против эталонного набора (AD-3, частично).

КОНТЕКСТ
--------
BAMS Р13 требует прогонять любое изменение методологии против эталонного
набора ДО внедрения и отклонять изменение, если оно понижает соответствие
эталонным выводам. До сих пор это было невозможно ни для одного правила:
Р4/Р5/Р6 исполняются суждением аналитика, не кодом (docs/ADR-021, Находка 3).

`classify_confidence_tier()` (Р9, закрытие AD-1, 2026-08-15) — первое
правило методологии, реализованное кодом ПОЛНОСТЬЮ, без человеческого шага
внутри. Этот файл — регрессия для него.

ЧЕМ ЭТО ОТЛИЧАЕТСЯ ОТ SNAPSHOT-ТЕСТА
-------------------------------------
`expected_tier` каждого кейса ВЫВЕДЕН из текста критериев BAMS Р9 (поле
`derivation` в фикстуре), а не скопирован из вывода кода. Если код разойдётся
с выводом — неправ код. Обратный порядок (заморозить текущее поведение и
назвать его эталоном) отклонён явно как альтернатива 4 в ADR-021: он
проверял бы код против им же придуманных ожиданий.

ВАЖНО ПРО ГРАНИЦЫ ПОКРЫТИЯ
---------------------------
Этот файл НЕ закрывает AD-3. Он покрывает Р9 — одно правило из шести
разделов BAMS Р4–Р9. Р4 (причинность), Р5 (гипотезы), Р6 (доказательства)
регрессии не поддаются в принципе, а не «пока не сделали».
"""
import json
from pathlib import Path

import pytest

from config.settings import classify_confidence_tier

# Путь от __file__, не от cwd: autouse-фикстура conftest делает chdir в
# песочницу (см. докстринг tests/conftest.py — этот класс бага уже приводил
# к молчаливому скипу теста precision на много дней).
FIXTURE = Path(__file__).parent / "fixtures" / "confidence_tier_reference.json"

VALID_TIERS = {"high", "medium", "low"}


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _cases() -> list[dict]:
    return _load()["cases"]


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_rule_matches_reference_derivation(case):
    """
    Ядро регрессии Р13: код обязан согласовываться с выводом, сделанным из
    текста методологии.

    Падение здесь НЕ означает «поправь тест». По BAMS Р13 регресс на
    эталонном кейсе — основание отклонить изменение методологии, «независимо
    от того, насколько разумным оно выглядит в отрыве от данных». Если
    изменение всё же верно, а устарел эталон — обновить `derivation` в
    фикстуре и утвердить вручную (см. `_meta.update_rule`).
    """
    actual = classify_confidence_tier(**case["inputs"])
    assert actual == case["expected_tier"], (
        f"Кейс {case['id']} ({case['origin']}):\n"
        f"  ожидалось {case['expected_tier']}, получено {actual}\n"
        f"  критерий Р9: {case['p9_criterion']}\n"
        f"  вывод из методологии: {case['derivation']}\n"
        f"  → см. _meta.update_rule: эталон не правится молча под новый код"
    )


def test_reference_set_covers_all_three_tiers():
    """
    BDKS R-06 (разнообразие исходов): проверка методологии на кейсах
    одного уровня недействительна. Формально то же требование, что «Golden
    Dataset обязан включать события с разным исходом, не только успешные»
    (BAMS Раздел 12, митигация survivorship bias).
    """
    tiers = {c["expected_tier"] for c in _cases()}
    assert tiers == VALID_TIERS, (
        f"Набор покрывает только {sorted(tiers)}, требуется все три уровня "
        f"{sorted(VALID_TIERS)} — иначе регрессия недействительна по BDKS R-06"
    )


def test_reference_set_contains_real_and_boundary_cases():
    """
    Набор должен стоять на реальных данных, а не только на придуманных
    границах — иначе это снова проверка кода против воображения. И наоборот:
    только production-кейсы не покрывают границы (в проде сейчас нет ни
    одного кластера с нулём прямых доказательств).
    """
    origins = [c["origin"] for c in _cases()]
    assert any(o.startswith("production") for o in origins), "нет ни одного реального кейса"
    assert any(o.startswith("boundary") for o in origins), "нет ни одного граничного кейса"


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_every_case_has_non_empty_derivation(case):
    """
    Кейс без вывода из методологии — это snapshot, а не эталон. Проверка
    защищает главное свойство набора (см. `_meta.not_a_snapshot`) от
    постепенного размывания: добавить кейс, не объяснив его, будет нельзя.
    """
    derivation = (case.get("derivation") or "").strip()
    assert len(derivation) >= 40, (
        f"Кейс {case['id']}: derivation пуст или слишком короток — "
        "эталонное значение обязано быть выведено из текста Р9, не скопировано из кода"
    )
    assert case.get("p9_criterion"), f"Кейс {case['id']}: не указан критерий Р9"


def test_case_ids_unique():
    ids = [c["id"] for c in _cases()]
    assert len(ids) == len(set(ids)), "дублирующиеся id кейсов"


def test_inputs_match_function_signature():
    """
    Фикстура вызывается через **inputs — ключи обязаны точно совпадать с
    параметрами функции. Ловит рассинхрон, если параметр переименуют, а
    фикстуру забудут (тот же класс дрейфа, что AD-6 для схемы сигнала).
    """
    expected_keys = {"direct_evidence_count", "anchor_has_disputed_facts", "all_stale"}
    for case in _cases():
        assert set(case["inputs"]) == expected_keys, (
            f"Кейс {case['id']}: ключи inputs {sorted(case['inputs'])} не совпадают "
            f"с параметрами classify_confidence_tier {sorted(expected_keys)}"
        )


def test_staleness_caveat_stays_visible_until_ad10_closed():
    """
    История вопроса (важна, чтобы тест не выпотрошили при следующей правке).

    Изначально формулировался так: «правило all_stale → low не является
    буквальным критерием Р9». При разборе оказалось точнее: свежесть УЖЕ была
    в методологии — BAMS Раздел 3, четвёртый критерий качества сигнала — но
    Р9 на неё не ссылался. BAMS v1.4 связь дописала, и в этой части вопрос
    закрыт: уровень «Низкая» при полностью устаревших доказательствах теперь
    опирается на текст, а не на интерпретацию.

    ОСТАЁТСЯ другое расхождение — `docs/NIES.md` AD-10: Р3 требует различать
    скорость устаревания по категориям («рыночные устаревают быстро,
    инфраструктурные — медленно»), а код применяет единый STALE_THRESHOLD ко
    всем. Пока AD-10 открыт, кейсы, чей уровень задаётся устареванием, обязаны
    нести оговорку — иначе следующая сессия примет их за полностью
    методологически обоснованные и закрепит завышенный порог как норму.
    """
    meta = _load()["_meta"]
    assert "AD-10" in (meta.get("open_question") or ""), (
        "из фикстуры пропала ссылка на AD-10 — либо долг закрыт (тогда обнови "
        "фикстуру, derivation кейсов и этот тест), либо оговорка потерялась молча"
    )

    stale_driven = [
        c for c in _cases()
        if c["p9_criterion"] == "low_stale_evidence_uniform_threshold_caveat"
    ]
    assert stale_driven, "нет ни одного кейса, помеченного оговоркой про единый порог"

    for case in stale_driven:
        assert case["inputs"]["all_stale"] is True, (
            f"Кейс {case['id']} помечен оговоркой про устаревание, но all_stale=False"
        )
        assert "AD-10" in case["derivation"], (
            f"Кейс {case['id']}: derivation не называет AD-10 — читатель не узнает, "
            "что уровень отражает текущее поведение кода, а не категорийную мерку Р3"
        )
