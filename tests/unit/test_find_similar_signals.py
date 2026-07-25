"""
tests/unit/test_find_similar_signals.py
Bitcoin Intel — тесты scripts/find_similar_signals.py (ADR-018, Фаза 1).

КОНТЕКСТ
--------
TF-IDF-кандидаты для Шага 5 (связывание) — не автоматические confirms/
contradicts, только расширение пула кандидатов для честной ручной
проверки (см. ADR-018). Тесты проверяют: (1) похожие по тексту сигналы
ранжируются выше несвязанных; (2) по умолчанию исключается тот же
cluster, что у target; (3) обработку ошибок и граничных случаев;
(4) что скрипт не падает на реальных данных.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from scripts.find_similar_signals import (
    find_similar, signal_text, load_signals,
    build_signal_entity_map, find_shared_entity_candidates,
    is_opposite_dir_same_theme,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _sig(id_, cluster, signal="", context="", tension="", macro_implication="", dir_=None, theme=None):
    s = {
        "id": id_,
        "cluster": cluster,
        "signal": signal,
        "context": context,
        "tension": tension,
        "macro_implication": macro_implication,
    }
    if dir_ is not None:
        s["dir"] = dir_
    if theme is not None:
        s["theme"] = theme
    return s


class TestSimilarityRanking:

    def test_similar_signal_ranks_above_unrelated(self):
        target = _sig(
            "TGT-001", "cluster_a",
            signal="Корпорация нарастила BTC-казначейство и долговую нагрузку",
            macro_implication="Долговая модель накопления BTC под давлением рынка",
        )
        similar = _sig(
            "SIM-001", "cluster_b",
            signal="Другая корпорация нарастила BTC-казначейство через долговое финансирование",
            macro_implication="Долговая модель накопления BTC остаётся под давлением",
        )
        unrelated = _sig(
            "UNR-001", "cluster_b",
            signal="Новый Bitcoin L2 запустил мейннет с фокусом на приватных платежах",
            macro_implication="Расширение технической инфраструктуры Lightning-экосистемы",
        )
        signals = [target, similar, unrelated]

        ranked = find_similar("TGT-001", signals, top_n=5)
        ranked_ids = [s["id"] for s, _score in ranked]

        assert ranked_ids[0] == "SIM-001"
        sim_score = dict((s["id"], sc) for s, sc in ranked)
        assert sim_score["SIM-001"] > sim_score["UNR-001"]

    def test_same_cluster_excluded_by_default(self):
        target = _sig("TGT-002", "cluster_a", signal="BTC-казначейство и долговая нагрузка компании")
        same_cluster_similar = _sig("SC-001", "cluster_a", signal="BTC-казначейство и долговая нагрузка другой компании")
        other_cluster = _sig("OC-001", "cluster_b", signal="Совершенно другая тема про майнинг-пулы")
        signals = [target, same_cluster_similar, other_cluster]

        ranked = find_similar("TGT-002", signals, top_n=5)
        ranked_ids = [s["id"] for s, _score in ranked]

        assert "SC-001" not in ranked_ids
        assert "OC-001" in ranked_ids

    def test_same_cluster_included_with_flag(self):
        target = _sig("TGT-003", "cluster_a", signal="BTC-казначейство и долговая нагрузка компании")
        same_cluster_similar = _sig("SC-002", "cluster_a", signal="BTC-казначейство и долговая нагрузка другой компании")
        signals = [target, same_cluster_similar]

        ranked = find_similar("TGT-003", signals, top_n=5, same_cluster_ok=True)
        ranked_ids = [s["id"] for s, _score in ranked]

        assert "SC-002" in ranked_ids

    def test_unknown_signal_id_raises(self):
        signals = [_sig("A-001", "cluster_a", signal="что-то")]
        with pytest.raises(ValueError, match="не найден"):
            find_similar("NOPE-001", signals)

    def test_no_candidates_outside_cluster_returns_empty(self):
        target = _sig("TGT-004", "cluster_a", signal="что-то")
        same_cluster_only = _sig("SC-003", "cluster_a", signal="что-то ещё")
        signals = [target, same_cluster_only]

        ranked = find_similar("TGT-004", signals, top_n=5)
        assert ranked == []

    def test_top_n_larger_than_candidates_does_not_crash(self):
        target = _sig("TGT-005", "cluster_a", signal="что-то про BTC")
        other = _sig("OC-002", "cluster_b", signal="что-то другое про BTC")
        signals = [target, other]

        ranked = find_similar("TGT-005", signals, top_n=100)
        assert len(ranked) == 1


class TestSignalTextField:

    def test_excludes_caveat_and_alternatives(self):
        s = {
            "signal": "заголовок",
            "context": "контекст",
            "tension": "напряжение",
            "macro_implication": "вывод",
            "caveat": "ОГОВОРКА_НЕ_ДОЛЖНА_ПОПАСТЬ",
            "alternatives_considered": ["АЛЬТЕРНАТИВА_НЕ_ДОЛЖНА_ПОПАСТЬ"],
        }
        text = signal_text(s)
        assert "ОГОВОРКА_НЕ_ДОЛЖНА_ПОПАСТЬ" not in text
        assert "АЛЬТЕРНАТИВА" not in text
        assert "заголовок" in text
        assert "вывод" in text

    def test_handles_missing_fields_gracefully(self):
        assert signal_text({}) == ""

    def test_strips_embedded_signal_ids(self):
        """Найдено при ручной инспекции TF-IDF-весов: ID других сигналов,
        упомянутые в context, засоряли словарь как ложные "редкие термины"."""
        s = {
            "signal": "заголовок",
            "context": "продолжение эпизода NAR-2026-0711-001 и STR-2026-0706-002",
        }
        text = signal_text(s)
        assert "NAR-2026-0711-001" not in text
        assert "STR-2026-0706-002" not in text
        assert "заголовок" in text
        assert "продолжение эпизода" in text

    def test_does_not_strip_short_non_id_hyphenated_tokens(self):
        """Паттерн ID специфичен (буквы-YYYY-MMDD-NNN) — не должен случайно
        резать обычные слова с дефисом."""
        s = {"signal": "BIP-110 — не то же самое, что какой-то текст"}
        text = signal_text(s)
        assert "BIP-110" in text
        assert "какой-то" in text


class TestStopWords:

    def test_common_prepositions_excluded_from_similarity_weight(self):
        """Найдено при ручной инспекции: частые предлоги/союзы (через, на,
        же) получали ненулевой TF-IDF вес и вносили шум в каждое сравнение
        независимо от содержания. Проверяем, что после фикса общее слово
        'через' не завышает сходство двух иначе не связанных сигналов."""
        target = {
            "id": "TGT-010", "cluster": "cluster_a",
            "signal": "Уникальное_Слово_Альфа через что-то",
        }
        unrelated_shared_stopword = {
            "id": "UNR-010", "cluster": "cluster_b",
            "signal": "Совершенно_Другое_Слово_Бета через что-то ещё",
        }
        genuinely_similar = {
            "id": "SIM-010", "cluster": "cluster_b",
            "signal": "Уникальное_Слово_Альфа фигурирует снова",
        }
        signals = [target, unrelated_shared_stopword, genuinely_similar]

        ranked = find_similar("TGT-010", signals, top_n=5)
        ranked_ids = [s["id"] for s, _score in ranked]

        assert ranked_ids[0] == "SIM-010"


class TestBigrams:

    def test_bigram_phrase_boosts_genuine_similarity(self):
        """Найдено в обсуждении: одиночные слова часто недостаточно
        специфичны. Проверяем, что словосочетание ("консенсусный порог")
        помогает отличить содержательно похожий сигнал от того, что
        просто делит одно из двух слов с целевым."""
        target = _sig(
            "TGT-020", "cluster_a",
            signal="Спор о консенсусный порог активации софтфорка",
        )
        shares_phrase = _sig(
            "SIM-020", "cluster_b",
            signal="Новый спор про консенсусный порог для другого предложения",
        )
        shares_one_word_only = _sig(
            "UNR-020", "cluster_b",
            signal="Порог входа на биржу снижен для розничных инвесторов",
        )
        signals = [target, shares_phrase, shares_one_word_only]

        ranked = find_similar("TGT-020", signals, top_n=5)
        ranked_ids = [s["id"] for s, _score in ranked]

        assert ranked_ids[0] == "SIM-020"


class TestEntityOverlap:

    def test_build_signal_entity_map_from_signal_refs(self):
        entities = [
            {"id": "strategy", "signal_refs": ["STR-001", "STR-002"]},
            {"id": "rgb_protocol", "signal_refs": ["INF-001"]},
        ]
        m = build_signal_entity_map(entities)
        assert m["STR-001"] == {"strategy"}
        assert m["STR-002"] == {"strategy"}
        assert m["INF-001"] == {"rgb_protocol"}
        assert "NOPE-001" not in m

    def test_signal_referenced_by_multiple_entities(self):
        entities = [
            {"id": "strategy", "signal_refs": ["SIG-001"]},
            {"id": "bitcoin", "signal_refs": ["SIG-001"]},
        ]
        m = build_signal_entity_map(entities)
        assert m["SIG-001"] == {"strategy", "bitcoin"}

    def test_find_shared_entity_candidates_finds_cross_cluster_match(self):
        target = _sig("TGT-030", "cluster_a", signal="что-то про Strategy")
        shares_entity_different_words = _sig(
            "SIM-030", "cluster_b", signal="Совершенно другими словами про ту же компанию"
        )
        no_shared_entity = _sig("UNR-030", "cluster_b", signal="Другая история")
        signals = [target, shares_entity_different_words, no_shared_entity]

        signal_entity_map = {
            "TGT-030": {"strategy"},
            "SIM-030": {"strategy"},
            "UNR-030": {"rgb_protocol"},
        }

        results = find_shared_entity_candidates("TGT-030", signals, signal_entity_map)
        result_ids = [s["id"] for s, _shared in results]

        assert "SIM-030" in result_ids
        assert "UNR-030" not in result_ids

    def test_find_shared_entity_candidates_respects_same_cluster_exclusion(self):
        target = _sig("TGT-031", "cluster_a", signal="что-то")
        same_cluster = _sig("SC-031", "cluster_a", signal="что-то ещё")
        signals = [target, same_cluster]
        signal_entity_map = {"TGT-031": {"strategy"}, "SC-031": {"strategy"}}

        results = find_shared_entity_candidates("TGT-031", signals, signal_entity_map)
        assert results == []

        results_included = find_shared_entity_candidates(
            "TGT-031", signals, signal_entity_map, same_cluster_ok=True
        )
        assert len(results_included) == 1

    def test_find_shared_entity_candidates_unknown_id_raises(self):
        with pytest.raises(ValueError, match="не найден"):
            find_shared_entity_candidates("NOPE-999", [_sig("A-001", "cluster_a")], {})

    def test_find_shared_entity_candidates_empty_when_target_has_no_entities(self):
        target = _sig("TGT-032", "cluster_a", signal="что-то")
        other = _sig("OC-032", "cluster_b", signal="что-то ещё")
        signals = [target, other]
        signal_entity_map = {"OC-032": {"strategy"}}  # target не привязан ни к одной сущности

        results = find_shared_entity_candidates("TGT-032", signals, signal_entity_map)
        assert results == []


class TestOppositeDirSameTheme:

    def test_flags_opposite_dir_same_theme(self):
        target = _sig("TGT-040", "cluster_a", dir_="pos", theme="institutionalization")
        candidate = _sig("CAND-040", "cluster_b", dir_="neg", theme="institutionalization")
        assert is_opposite_dir_same_theme(target, candidate) is True

    def test_does_not_flag_same_dir(self):
        target = _sig("TGT-041", "cluster_a", dir_="pos", theme="institutionalization")
        candidate = _sig("CAND-041", "cluster_b", dir_="pos", theme="institutionalization")
        assert is_opposite_dir_same_theme(target, candidate) is False

    def test_does_not_flag_different_theme(self):
        target = _sig("TGT-042", "cluster_a", dir_="pos", theme="institutionalization")
        candidate = _sig("CAND-042", "cluster_b", dir_="neg", theme="infrastructure")
        assert is_opposite_dir_same_theme(target, candidate) is False

    def test_neu_never_flagged_as_opposite(self):
        """neu — 'нет направления', не третья полярность; не должен
        считаться противоположностью ни pos, ни neg."""
        target = _sig("TGT-043", "cluster_a", dir_="neu", theme="institutionalization")
        candidate = _sig("CAND-043", "cluster_b", dir_="pos", theme="institutionalization")
        assert is_opposite_dir_same_theme(target, candidate) is False
        candidate2 = _sig("CAND-044", "cluster_b", dir_="neg", theme="institutionalization")
        assert is_opposite_dir_same_theme(target, candidate2) is False


class TestRealDataSmoke:
    """Не падает на реальном signals.json, возвращает валидную структуру."""

    def test_runs_on_real_signals_without_crashing(self):
        signals_path_real = os.path.join(REPO_ROOT, "signals.json")
        if not os.path.exists(signals_path_real):
            pytest.skip("signals.json недоступен в этом окружении")

        signals = load_signals()
        assert len(signals) > 0

        target_id = signals[0]["id"]
        ranked = find_similar(target_id, signals, top_n=5)

        assert isinstance(ranked, list)
        for s, score in ranked:
            assert "id" in s
            assert 0.0 <= score <= 1.0 + 1e-9  # cosine similarity границы
