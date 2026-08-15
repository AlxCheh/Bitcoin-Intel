"""
tests/unit/test_entity_candidates.py
Bitcoin Intel — тесты scripts/find_entity_candidates.py (AD-9, случай 2).

КОНТЕКСТ
--------
AD-9 (docs/NIES.md) зарегистрировал четыре проверки, держащиеся на
процедурной дисциплине сессии. Случай 2 — критерий значимости сущности для
ENTITIES.json («участник события, а не просто сравнение») — семантическое
суждение, полностью автоматизировать которое нельзя. Автоматизируется только
механический подвопрос: какие имена в тексте сигнала вообще не
зарегистрированы. Скрипт — подсказка, не гейт.

ЧТО ЗДЕСЬ ПРОВЕРЯЕТСЯ
---------------------
Не «правильно ли скрипт определяет значимость» (он этого и не делает), а
что механическая часть не врёт: известные сущности не всплывают как новые,
заведомый мусор отсеян, флаг источника ставится там, где нужно.

Отдельно — регрессия на баг, который прототип реально допустил: без
разбиения известных имён по словам «IREN» из текста не матчился на
зарегистрированную «IREN Limited», и скрипт предлагал добавить уже
существующую сущность (то же с Canaan / Fidelity / Riot).
"""
import json
from pathlib import Path

import pytest

from scripts.find_entity_candidates import (
    analyze,
    build_known_names,
    extract_candidates,
    looks_like_source,
)

# ВАЖНО: пути резолвятся от __file__, не от cwd. Autouse-фикстура
# isolated_environment (tests/conftest.py) делает chdir(tmp_path) для КАЖДОГО
# теста и кладёт туда ЗАГЛУШКИ signals.json/ENTITIES.json с пустым списком.
# Чтение по относительному пути дало бы либо TypeError, либо — что хуже —
# молчаливый skip на пустых данных, маскирующий неработающий тест. Этот
# класс бага уже был в проекте (B1 ARR v3), правило зафиксировано в докстринге
# conftest.py; первая версия этого файла в него сразу же и попала.
REPO_ROOT = Path(__file__).parent.parent.parent


def _load_real_corpus() -> tuple[list[dict], list[dict]]:
    entities = json.loads((REPO_ROOT / "ENTITIES.json").read_text(encoding="utf-8"))["entities"]
    signals  = json.loads((REPO_ROOT / "signals.json").read_text(encoding="utf-8"))["signals"]
    assert entities and signals, "реальный корпус пуст — путь резолвится в песочницу, а не в репозиторий"
    return entities, signals


@pytest.fixture
def known():
    """Реальные формы имён из ENTITIES.json — составные, с суффиксами и скобками."""
    return build_known_names([
        {"id": "iren", "name": "IREN Limited"},
        {"id": "canaan", "name": "Canaan Inc."},
        {"id": "strategy", "name": "Strategy (MSTR)"},
        {"id": "el_salvador", "name": "El Salvador (Strategic Bitcoin Reserve)"},
    ])


def _signal(text: str, source: str = "") -> dict:
    return {"id": "STR-2026-0101-001", "signal": text, "data": [], "context": "", "source": source}


class TestKnownEntityFiltering:

    def test_known_entity_short_form_not_reported(self, known):
        """
        Регрессия на реальный баг прототипа: «IREN» и «Canaan» в тексте — это
        уже зарегистрированные «IREN Limited» и «Canaan Inc.», не новые
        сущности. Без разбиения известных имён по словам скрипт предлагал
        добавить существующее.
        """
        found = extract_candidates(_signal("IREN и Canaan увеличили хешрейт"), known)
        assert "IREN" not in found
        assert "Canaan" not in found

    def test_known_entity_full_form_not_reported(self, known):
        found = extract_candidates(_signal("IREN Limited отчиталась за квартал"), known)
        assert not [f for f in found if "IREN" in f]

    def test_name_from_parenthetical_not_reported(self, known):
        """«El Salvador» из «El Salvador (Strategic Bitcoin Reserve)» — известное имя."""
        found = extract_candidates(_signal("El Salvador нарастил резерв"), known)
        assert "El Salvador" not in found

    def test_genuinely_new_name_is_reported(self, known):
        found = extract_candidates(_signal("Franklin Templeton подала заявку"), known)
        assert "Franklin Templeton" in found


class TestNoiseFiltering:

    def test_tickers_filtered(self, known):
        """Тикеры (MSTR, IBIT, GBTC) — не сущности, а обозначения бумаг."""
        found = extract_candidates(_signal("Бумаги IBIT и GBTC выросли"), known)
        assert "IBIT" not in found
        assert "GBTC" not in found

    def test_signal_ids_filtered(self, known):
        found = extract_candidates(_signal("Продолжение STR-2026-0706-001 по той же линии"), known)
        assert not [f for f in found if f.startswith("STR-2026")]

    def test_stopword_abbreviations_filtered(self, known):
        found = extract_candidates(_signal("SEC одобрила ETF, CEO прокомментировал"), known)
        for noise in ("SEC", "ETF", "CEO"):
            assert noise not in found

    def test_short_fragments_filtered(self, known):
        """Слишком короткие обрывки не несут информации о сущности."""
        found = extract_candidates(_signal("Q2 дал рост"), known)
        assert "Q2" not in found


class TestSourceFlagging:

    def test_name_present_in_source_is_flagged(self):
        signal = _signal("Glassnode зафиксировал отток", source="Glassnode (август 2026)")
        assert looks_like_source("Glassnode", signal) is True

    def test_name_absent_from_source_not_flagged(self):
        signal = _signal("Polymarket открыл рынок", source="CoinDesk (август 2026)")
        assert looks_like_source("Polymarket", signal) is False

    def test_flagged_candidates_sorted_after_unflagged(self, known):
        """
        Непомеченные кандидаты интереснее для проверки — они идут первыми.
        Сам факт пометки НЕ скрывает кандидата: на реальных данных в `source`
        попадают Bitwise/VanEck, которые как раз настоящие участники событий
        (см. докстринг скрипта — почему это флаг, а не фильтр).
        """
        signals = [
            _signal("Glassnode зафиксировал отток", source="Glassnode (август 2026)"),
            _signal("Polymarket открыл рынок", source="CoinDesk (август 2026)"),
        ]
        rows = analyze(signals, known)
        names = [r[0] for r in rows]
        flags = {r[0]: r[2] for r in rows}

        assert "Glassnode" in names, "помеченный кандидат обязан остаться в выдаче, не исчезнуть"
        assert flags["Glassnode"] is True
        assert flags["Polymarket"] is False
        assert names.index("Polymarket") < names.index("Glassnode")


class TestRealCorpusRegression:
    """
    Прогон на настоящих данных, не на синтетике — тот же принцип, что уже
    применён в этой сессии трижды: формула, выглядящая правдоподобно на
    моках, может оказаться бесполезной на реальном корпусе.
    """

    def test_finds_known_real_gap_stratum_v2(self):
        """
        Stratum V2 — реальный пробел, найденный первым прогоном скрипта:
        CLAUDE.md приводит его как пример типа `protocol` в таблице «Типы
        артефактов», но в ENTITIES.json его нет.

        Тест намеренно устроен так, чтобы стать бессмысленным ровно тогда,
        когда пробел закроют: если Stratum V2 добавят в ENTITIES.json, он
        перестанет быть кандидатом и тест сам себя отключит с явным
        сообщением — это сигнал удалить его, а не чинить скрипт.
        """
        entities, signals = _load_real_corpus()

        if any("stratum" in e["name"].lower() for e in entities):
            pytest.skip("Stratum V2 добавлен в ENTITIES.json — регрессия больше не актуальна, тест можно удалить")

        names = {row[0] for row in analyze(signals, build_known_names(entities))}
        assert "Stratum V2" in names

    def test_does_not_report_any_already_registered_entity(self):
        """
        Главный инвариант на реальных данных: ни одно уже зарегистрированное
        имя не должно попасть в кандидаты. Это и есть проверка, что
        сопоставление по словам работает на всём разнообразии форм записи
        (скобки, юрсуффиксы, тикеры в названии), а не только на фикстуре.
        """
        entities, signals = _load_real_corpus()
        candidate_names = {row[0].lower() for row in analyze(signals, build_known_names(entities))}
        registered = {e["name"].lower() for e in entities}
        collisions = candidate_names & registered
        assert not collisions, (
            f"Уже зарегистрированные сущности предложены как новые: {sorted(collisions)}"
        )
