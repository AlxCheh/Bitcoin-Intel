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
from scripts.find_similar_signals import find_similar, signal_text, load_signals

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _sig(id_, cluster, signal="", context="", tension="", macro_implication=""):
    return {
        "id": id_,
        "cluster": cluster,
        "signal": signal,
        "context": context,
        "tension": tension,
        "macro_implication": macro_implication,
    }


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
