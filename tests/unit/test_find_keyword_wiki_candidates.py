"""
tests/unit/test_find_keyword_wiki_candidates.py
Bitcoin Intel — тесты для scripts/find_keyword_wiki_candidates.py
(2026-08-06, продолжение аудита связей LLM Wiki 2026-08-03).
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from find_keyword_wiki_candidates import (
    find_keyword_match,
    entity_text,
    audit_entity_theory,
    audit_entity_function,
)


class TestFindKeywordMatch:

    def test_exact_case_insensitive_match(self):
        assert find_keyword_match("Компания использует OP_RETURN для метаданных", ["op_return"]) == "op_return"

    def test_short_keyword_can_prefix_match_unrelated_word_documented_tradeoff(self):
        """
        Документированный компромисс (не баг) — граница только слева
        позволяет ловить русские словоформы ("ликвидност" -> "ликвидности"),
        но ценой того, что короткое ключевое слово ("BIP") может случайно
        совпасть с началом несвязанного слова ("Biplanet" тоже начинается
        с "Bip"). Решение — ответственность куратора: использовать
        специфичные ключевые слова ("BIP-360"), не голые короткие акронимы.
        """
        assert find_keyword_match("Компания Biplanet купила BTC", ["BIP"]) == "BIP"
        # но специфичный вариант такой ложной сработки уже не даёт:
        assert find_keyword_match("Компания Biplanet купила BTC", ["BIP-360"]) is None

    def test_word_boundary_allows_underscore_keyword_as_whole_word(self):
        """OP_RETURN с подчёркиванием — \\b должен распознать его как одно целое слово."""
        assert find_keyword_match("текст содержит op_return целиком", ["OP_RETURN"]) == "OP_RETURN"

    def test_cyrillic_word_boundary_works(self):
        assert find_keyword_match("производитель мультиподписных кошельков", ["мультиподпис"]) == "мультиподпис"

    def test_cyrillic_short_stem_also_subject_to_same_tradeoff(self):
        """Тот же компромисс, что и с BIP/Biplanet, но на кириллице — 'ключ' совпадёт с началом 'ключевой'."""
        assert find_keyword_match("ключевой момент истории", ["ключ"]) == "ключ"

    def test_no_match_returns_none(self):
        assert find_keyword_match("совершенно посторонний текст", ["OP_RETURN", "мультиподпис"]) is None

    def test_returns_first_matching_keyword_for_explainability(self):
        result = find_keyword_match("текст про ликвидность и маршрутизацию", ["маршрутизацию", "ликвидность"])
        assert result == "маршрутизацию"  # первое совпавшее по порядку в списке


class TestEntityText:

    def test_combines_summary_what_notable(self):
        e = {"summary": "A", "profile": {"what": "B", "notable": "C"}}
        assert entity_text(e) == "A B C"

    def test_handles_missing_fields_gracefully(self):
        e = {"summary": "A"}
        assert entity_text(e) == "A"


class TestAuditEntityTheory:

    def test_finds_genuine_candidate(self):
        entities = [{"id": "e1", "name": "E1", "summary": "Продукт про ликвидность Lightning", "profile": {}}]
        topics = [{"id": "t1", "items": [{"label": "Проблема ликвидности", "audit_keywords": ["ликвидность"]}]}]
        results = audit_entity_theory(entities, topics)
        assert len(results) == 1
        assert results[0]["entity_id"] == "e1"
        assert results[0]["matched_keyword"] == "ликвидность"

    def test_skips_already_linked_entity(self):
        """Регрессия — если у сущности УЖЕ есть theory_refs на этот топик, кандидатом он быть не должен."""
        entities = [{"id": "e1", "name": "E1", "summary": "Про ликвидность",
                     "profile": {}, "theory_refs": ["t1"]}]
        topics = [{"id": "t1", "items": [{"label": "Ликвидность", "audit_keywords": ["ликвидность"]}]}]
        results = audit_entity_theory(entities, topics)
        assert results == []

    def test_item_without_audit_keywords_is_silently_skipped(self):
        """Пункт без audit_keywords — ожидаемо (курирование ещё не дошло до него), не ошибка."""
        entities = [{"id": "e1", "name": "E1", "summary": "Всё что угодно", "profile": {}}]
        topics = [{"id": "t1", "items": [{"label": "Без ключевых слов"}]}]
        results = audit_entity_theory(entities, topics)
        assert results == []

    def test_entity_filter_restricts_scope(self):
        entities = [
            {"id": "e1", "name": "E1", "summary": "ликвидность", "profile": {}},
            {"id": "e2", "name": "E2", "summary": "ликвидность", "profile": {}},
        ]
        topics = [{"id": "t1", "items": [{"label": "L", "audit_keywords": ["ликвидность"]}]}]
        results = audit_entity_theory(entities, topics, entity_filter="e1")
        assert len(results) == 1
        assert results[0]["entity_id"] == "e1"


class TestAuditEntityFunction:

    def test_finds_genuine_candidate(self):
        entities = [{"id": "e1", "name": "E1", "summary": "пионер мультиподписных кошельков", "profile": {}}]
        functions = [{"id": "f1", "name": "Multisig", "audit_keywords": ["мультиподпис"]}]
        results = audit_entity_function(entities, functions)
        assert len(results) == 1
        assert results[0]["matched_keyword"] == "мультиподпис"

    def test_skips_already_linked_entity(self):
        entities = [{"id": "e1", "name": "E1", "summary": "мультиподпись",
                     "profile": {}, "function_refs": ["f1"]}]
        functions = [{"id": "f1", "name": "Multisig", "audit_keywords": ["мультиподпис"]}]
        results = audit_entity_function(entities, functions)
        assert results == []


class TestRealDataRegressionOnKnownGoodCases:
    """
    2026-08-06: проверка не на синтетике, а на реальных ENTITIES.json —
    честный тест метода перед ретроактивным курированием audit_keywords
    для всех 35 пунктов теории + 6 функций. Проверяет только то, что
    метод ФИЗИЧЕСКИ СПОСОБЕН найти уже известные (найденные вручную
    2026-08-03) совпадения, если keywords присутствуют — не полагается
    на то, что курирование уже сделано в живых данных.

    Первая прикидка (2026-08-03) казалась 4/7 — построение и тестирование
    самого скрипта заставило перепроверить буквальный текст внимательнее
    (не по памяти о смысле), нашлось ещё 2 (dog_mode через "governance",
    foundry через "консенсус"/"голосование") — реальный счёт 6/7.
    """
    import json as _json

    def _load_real_entity(self, entity_id: str) -> dict:
        entities = self._json.loads((REPO_ROOT / "ENTITIES.json").read_text(encoding="utf-8"))["entities"]
        return next(e for e in entities if e["id"] == entity_id)

    def test_runes_matches_op_return_keyword(self):
        runes = self._load_real_entity("runes")
        text = entity_text(runes)
        assert find_keyword_match(text, ["OP_RETURN"]) == "OP_RETURN"

    def test_bitgo_matches_multisig_keyword(self):
        bitgo = self._load_real_entity("bitgo")
        text = entity_text(bitgo)
        assert find_keyword_match(text, ["мультиподпис"]) == "мультиподпис"

    def test_lightning_labs_matches_liquidity_keyword(self):
        ll = self._load_real_entity("lightning_labs")
        text = entity_text(ll)
        assert find_keyword_match(text, ["ликвидност"]) == "ликвидност"

    def test_breez_matches_routing_keyword(self):
        breez = self._load_real_entity("breez")
        text = entity_text(breez)
        assert find_keyword_match(text, ["маршрутиз"]) == "маршрутиз"

    def test_dog_mode_matches_governance_keyword(self):
        """
        Найдено при построении скрипта (2026-08-06) — более ранняя
        ручная оценка 2026-08-03 ошибочно посчитала эту связь чисто
        концептуальной, не проверив буквальный текст внимательно.
        "governance" реально присутствует ("governance-споре").
        """
        dog_mode = self._load_real_entity("dog_mode")
        text = entity_text(dog_mode)
        assert find_keyword_match(text, ["governance"]) == "governance"

    def test_foundry_matches_consensus_or_voting_keyword(self):
        """Аналогично dog_mode — найдено при перепроверке, не в первой оценке."""
        foundry = self._load_real_entity("foundry")
        text = entity_text(foundry)
        assert find_keyword_match(text, ["консенсус", "голосование"]) is not None

    def test_honest_limitation_tangem_has_no_literal_multisig_keyword(self):
        """
        Единственный из 7 случаев, где буквального совпадения в тексте
        сущности действительно нет — связь существует через рассуждение
        ("конкурент Coinkite" + "та же логика разнородности вендоров"),
        не через явное упоминание мультиподписи. Задокументированный,
        проверенный предел метода, не баг.
        """
        tangem = self._load_real_entity("tangem")
        text = entity_text(tangem)
        assert find_keyword_match(text, ["мультиподпис", "multisig", "quorum", "кворум"]) is None


class TestPolysemousKeywordNoiseIsExpectedNotABug:
    """
    2026-08-06: сквозной тест на реальных данных с временными
    audit_keywords выявил — "ликвидность" как ключевое слово для
    Lightning-панели совпадает не только с Lightning Labs (честная
    связь), но и с Strategy ("управление ликвидностью и дивидендов" -
    корпоративный смысл) и Hyperliquid ("годами форы по ликвидности" -
    биржевой смысл). Это ОЖИДАЕМОЕ поведение генератора кандидатов, не
    поломка - каждый кандидат всё равно проверяется человеком (см.
    докстринг модуля, раздел "РУКОВОДСТВО ДЛЯ КУРИРОВАНИЯ"). Тест
    фиксирует это явно, чтобы будущая правка случайно не "исправила"
    ожидаемый шум, сломав тем самым честное покрытие Lightning Labs.
    """

    def test_generic_liquidity_keyword_matches_both_relevant_and_irrelevant_entities(self):
        entities = json.loads((REPO_ROOT / "ENTITIES.json").read_text(encoding="utf-8"))["entities"]
        strategy = next(e for e in entities if e["id"] == "strategy")
        lightning_labs = next(e for e in entities if e["id"] == "lightning_labs")

        # оба технически "совпадают" - это ожидаемо, разбор на честность
        # переносится на человека, не на сам скрипт
        assert find_keyword_match(entity_text(strategy), ["ликвидност"]) == "ликвидност"
        assert find_keyword_match(entity_text(lightning_labs), ["ликвидност"]) == "ликвидност"
