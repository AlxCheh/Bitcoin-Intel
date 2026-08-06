"""
tests/unit/test_find_keyword_wiki_candidates.py
Bitcoin Intel — тесты scripts/find_keyword_wiki_candidates.py.

КОНТЕКСТ
--------
Уровень 1 систематической проверки связей LLM Wiki (см. докстринг
самого скрипта) — дешёвый, объяснимый пре-фильтр по буквальным
ключевым словам, НЕ замена обязательному ручному/LLM-проходу (тот
ловит концептуальные связи, которые лексический метод в принципе не
может поймать — проверено на 7 уже найденных связях 2026-08-03, 3 из 7
не содержат буквального ключевого слова).
"""
import re
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from scripts.find_keyword_wiki_candidates import (
    entity_text, keyword_matches, entity_has_theory_link,
    entity_has_function_link, audit_entity_theory, audit_entity_function,
    load_json, ENTITIES_PATH, THEORY_TOPICS_PATH, BITCOIN_FUNCTIONS_PATH,
)

REPO_ROOT = Path(__file__).parent.parent.parent


def _entity(id_, name="E", summary="", what="", notable="", theory_refs=None, function_refs=None, type_="protocol"):
    return {
        "id": id_, "name": name, "type": type_, "status": "active",
        "summary": summary,
        "profile": {"what": what, "notable": notable},
        "theory_refs": theory_refs or [],
        "function_refs": function_refs or [],
    }


def _topic(id_, items):
    return {"id": id_, "panel_title": id_, "items": items}


def _item(label, audit_keywords=None):
    return {"label": label, "paragraphs": [], "audit_keywords": audit_keywords or []}


def _function(id_, name="F", audit_keywords=None):
    return {"id": id_, "name": name, "audit_keywords": audit_keywords or []}


class TestKeywordMatching:

    def test_exact_word_matches(self):
        assert keyword_matches("Использует OP_RETURN для метаданных", "OP_RETURN")

    def test_case_insensitive(self):
        assert keyword_matches("использует op_return для метаданных", "OP_RETURN")

    def test_word_boundary_does_not_match_mid_word(self):
        """
        Граница слева защищает от совпадения В СЕРЕДИНЕ постороннего
        слова - 'bip' не должен матчиться внутри 'kabip' (гипотетическое
        слово, где 'bip' - не начало, а часть середины/конца).
        """
        assert not keyword_matches("текст содержит слово kabip тут", "bip")

    def test_underscore_is_part_of_word(self):
        """
        \\b в Python regex трактует подчёркивание как часть "слова" -
        OP_RETURN матчится целиком, не как OP + RETURN по отдельности.
        """
        assert keyword_matches("текст про OP_RETURN здесь", "OP_RETURN")
        assert not keyword_matches("текст про RETURN здесь", "OP_RETURN")

    def test_cyrillic_word_boundaries(self):
        """
        Граница СЛЕВА не мешает совпадению корня слова с любым русским
        суффиксом (мультиподпис + -ных/-и/-ь) - намеренный дизайн, не
        баг: ключевые слова для русского текста задаются как основы.
        """
        assert keyword_matches("пионер мультиподписных кошельков", "мультиподпис")
        assert not keyword_matches("пионер однократных кошельков", "мультиподпис")

    def test_keyword_does_not_match_mid_word_substring(self):
        """
        Граница слева всё ещё защищает от совпадения ключевого слова
        В СЕРЕДИНЕ постороннего слова (не только в его начале) - хотя
        и не от совпадения как префикса другого слова (осознанный
        компромисс ради работы с русскими словоформами, см. keyword_matches).
        """
        assert not keyword_matches("текст содержит слово опера", "оп_ретёрн")

    def test_no_match_when_keyword_absent(self):
        assert not keyword_matches("Совершенно не связанный текст", "OP_RETURN")


class TestEntityText:

    def test_combines_summary_what_notable(self):
        e = _entity("e1", summary="S", what="W", notable="N")
        text = entity_text(e)
        assert "S" in text and "W" in text and "N" in text

    def test_handles_missing_fields_gracefully(self):
        e = {"id": "e1", "name": "E", "profile": {}}
        text = entity_text(e)
        assert text == ""


class TestEntityLinkChecks:

    def test_entity_has_theory_link_true(self):
        e = _entity("e1", theory_refs=["topic1"])
        assert entity_has_theory_link(e, "topic1")

    def test_entity_has_theory_link_false(self):
        e = _entity("e1", theory_refs=["topic1"])
        assert not entity_has_theory_link(e, "topic2")

    def test_entity_has_function_link(self):
        e = _entity("e1", function_refs=["fn1"])
        assert entity_has_function_link(e, "fn1")
        assert not entity_has_function_link(e, "fn2")


class TestAuditEntityTheory:

    def test_finds_matching_candidate(self):
        entities = [_entity("runes", "Runes", what="использует OP_RETURN для метаданных")]
        topics = [_topic("t1", [_item("Пункт про данные", audit_keywords=["OP_RETURN"])])]
        results = audit_entity_theory(entities, topics)
        assert len(results) == 1
        assert results[0]["entity_id"] == "runes"
        assert results[0]["matched_keyword"] == "OP_RETURN"

    def test_excludes_already_linked_pair(self):
        """Не должен предлагать связь, которая уже существует - иначе ручной обзор захламляется уже сделанной работой."""
        entities = [_entity("e1", what="OP_RETURN тут", theory_refs=["t1"])]
        topics = [_topic("t1", [_item("П", audit_keywords=["OP_RETURN"])])]
        results = audit_entity_theory(entities, topics)
        assert results == []

    def test_no_match_when_no_keyword_present(self):
        entities = [_entity("e1", what="Совсем другой текст")]
        topics = [_topic("t1", [_item("П", audit_keywords=["OP_RETURN"])])]
        results = audit_entity_theory(entities, topics)
        assert results == []

    def test_no_match_when_audit_keywords_empty(self):
        """Пункты без проставленных ключевых слов не дают ложных совпадений (пустой список, не ошибка)."""
        entities = [_entity("e1", what="OP_RETURN тут есть")]
        topics = [_topic("t1", [_item("П", audit_keywords=[])])]
        results = audit_entity_theory(entities, topics)
        assert results == []

    def test_entity_filter_scopes_to_one_entity(self):
        entities = [
            _entity("e1", what="OP_RETURN тут"),
            _entity("e2", what="OP_RETURN тоже тут"),
        ]
        topics = [_topic("t1", [_item("П", audit_keywords=["OP_RETURN"])])]
        results = audit_entity_theory(entities, topics, entity_filter="e1")
        assert len(results) == 1
        assert results[0]["entity_id"] == "e1"


class TestAuditEntityFunction:

    def test_finds_matching_candidate(self):
        entities = [_entity("bitgo", "BitGo", notable="пионер мультиподписных кошельков")]
        functions = [_function("multisig-2of3", "Multisig", audit_keywords=["мультиподпис"])]
        results = audit_entity_function(entities, functions)
        assert len(results) == 1
        assert results[0]["function_id"] == "multisig-2of3"

    def test_excludes_already_linked_pair(self):
        entities = [_entity("e1", what="мультиподпись тут", function_refs=["fn1"])]
        functions = [_function("fn1", audit_keywords=["мультиподпис"])]
        results = audit_entity_function(entities, functions)
        assert results == []


class TestRealDataRegression:
    """Скрипт не должен падать на реальных данных, даже пока audit_keywords ещё не проставлены нигде."""

    def test_runs_cleanly_on_real_repo_data(self):
        entities = load_json(ENTITIES_PATH)["entities"]
        topics = load_json(THEORY_TOPICS_PATH)["topics"]
        functions = load_json(BITCOIN_FUNCTIONS_PATH)["functions"]

        # не должно бросать исключение, независимо от того, сколько
        # audit_keywords реально проставлено на момент прогона теста
        et = audit_entity_theory(entities, topics)
        ef = audit_entity_function(entities, functions)
        assert isinstance(et, list)
        assert isinstance(ef, list)

    def test_bitgo_multisig_would_be_found_if_keyword_present(self):
        """
        Сквозная проверка на реальном тексте BitGo (не синтетике) -
        подтверждает, что механизм действительно сработал бы на уже
        найденном вручную кейсе, если бы audit_keywords был проставлен.
        """
        entities = load_json(ENTITIES_PATH)["entities"]
        bitgo = next(e for e in entities if e["id"] == "bitgo")
        text = entity_text(bitgo)
        assert keyword_matches(text, "мультиподпис"), (
            "Текст BitGo больше не содержит 'мультиподпис' - реальный "
            "текст сущности изменился, проверь вручную, не сломалась ли "
            "предпосылка этого теста"
        )
