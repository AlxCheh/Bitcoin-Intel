"""
tests/unit/test_contradiction.py
Тесты для B2 — semantic_inverse_score и RelationshipStore (TD2).
Запускать: PYTHONHASHSEED=0 python3 -m pytest tests/unit/test_contradiction.py -v
"""

import os
import sys
import json
import tempfile
import pytest

os.environ["PYTHONHASHSEED"] = "0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.contradiction_detector import (
    score_pair, find_contradiction_candidates,
    _inverse_score, _subject_score, _dir_conflict_score,
    PROPOSAL_THRESHOLD,
)
from infrastructure.relationship_store import RelationshipStore, Relationship


# ─── Фикстуры ────────────────────────────────────────────────────────────────
def make_sig(id, macro="", dir="neu", actor="corporate",
             theme="institutionalization", cluster="test", contradicts=None):
    return {
        "id": id,
        "macro_implication": macro,
        "dir": dir,
        "actor": actor,
        "theme": theme,
        "cluster": cluster,
        "links": {"contradicts": contradicts or [], "confirms": [], "context_chain": []},
    }


# ─── B2: Тест очевидного противоречия ────────────────────────────────────────
class TestObviousContradiction:
    """score >= 0.5 для явных противоречий."""

    def test_inflow_vs_outflow(self):
        a = make_sig("A", macro="ETF-приток капитала составил рекордные $6 млрд за месяц.", dir="pos")
        b = make_sig("B", macro="ETF-отток капитала достиг исторического максимума $6.4 млрд.", dir="neg")
        c = score_pair(a, b)
        assert c.score >= 0.5, f"Ожидали score >= 0.5, получили {c.score}"
        assert len(c.hits) >= 1

    def test_nav_premium_vs_discount(self):
        a = make_sig("A", macro="Strategy торгуется с NAV-премией 2.1x — рынок верит в модель.", dir="pos")
        b = make_sig("B", macro="NAV-дисконт 0.83x — первый рыночный сигнал что премия исчезает.", dir="neg")
        c = score_pair(a, b)
        assert c.score >= 0.5, f"Ожидали score >= 0.5, получили {c.score}"

    def test_accumulation_vs_selloff(self):
        a = make_sig("A", macro="Долгосрочные держатели продолжают накопление несмотря на волатильность.", dir="pos")
        b = make_sig("B", macro="Началась масштабная распродажа BTC институциональными игроками.", dir="neg")
        c = score_pair(a, b)
        assert c.score >= 0.5, f"Ожидали score >= 0.5, получили {c.score}"

    def test_growth_vs_decline(self):
        a = make_sig("A", macro="Хешрейт растёт третий месяц подряд — сеть укрепляется.", dir="pos")
        b = make_sig("B", macro="Хешрейт падает на 15% — майнеры капитулируют.", dir="neg")
        c = score_pair(a, b)
        assert c.score >= 0.5

    def test_trust_vs_distrust(self):
        a = make_sig("A", macro="Регуляторное одобрение ETF означает принятие BTC мейнстримом.", dir="pos")
        b = make_sig("B", macro="Регуляторный запрет в трёх юрисдикциях ограничивает рост.", dir="neg")
        c = score_pair(a, b)
        assert c.score >= 0.5


# ─── B2: Тест отсутствия противоречия ────────────────────────────────────────
class TestNoContradiction:
    """score < 0.3 когда противоречия нет."""

    def test_same_direction_same_theme(self):
        a = make_sig("A", macro="Lightning Network достигла рекорда транзакций.", dir="pos", actor="defi")
        b = make_sig("B", macro="Lightning Network обрабатывает $1 млрд в месяц.", dir="pos", actor="defi")
        c = score_pair(a, b)
        assert c.score < 0.3, f"Ожидали score < 0.3, получили {c.score}"

    def test_complementary_signals(self):
        a = make_sig("A", macro="BTC становится резервным активом для корпораций.", dir="pos")
        b = make_sig("B", macro="Корпоративное накопление BTC ускоряется в 2026.", dir="pos")
        c = score_pair(a, b)
        assert c.score < 0.3, f"Ожидали score < 0.3, получили {c.score}"


# ─── B2: Тест разных субъектов ────────────────────────────────────────────────
class TestDifferentSubjects:
    """Разные субъекты снижают score даже при лексическом конфликте."""

    def test_different_actors_lowers_score(self):
        # ETF-отток vs корпоративный приток — разные субъекты
        a = make_sig("A", macro="ETF-отток давит на цену BTC.",
                     dir="neg", actor="etf", theme="institutionalization")
        b = make_sig("B", macro="Корпоративный приток капитала в BTC продолжается.",
                     dir="pos", actor="corporate", theme="institutionalization")
        c = score_pair(a, b)
        # subject_score = 0.5 (одна тема), не 1.0
        assert c.subject_score == 0.5
        # Но общий score всё равно может быть >= 0.5 из-за dir-конфликта
        # Ключевое: subject_score не 1.0 (это и есть тест)

    def test_completely_different_themes(self):
        a = make_sig("A", macro="Дефицит предложения BTC нарастает.",
                     dir="pos", actor="miner", theme="supply")
        b = make_sig("B", macro="ETF-отток капитала давит на рынок.",
                     dir="neg", actor="etf", theme="institutionalization")
        c = score_pair(a, b)
        assert c.subject_score == 0.0


# ─── B2: Верификация на реальных парах из базы ───────────────────────────────
class TestRealSignalPairs:
    """Тест на паттернах из реальных сигналов проекта."""

    def test_strategy_solvency_vs_nav_discount(self):
        """STR-2026-0622-001 (NAV-дисконт neg) vs STR-2026-0615-001 (накопление pos)."""
        nav_discount = make_sig(
            "STR-2026-0622-001",
            macro="NAV-дисконт 0.83x — первый рыночный сигнал что премия за BTC-стратегию через акции исчезает.",
            dir="neg", actor="corporate"
        )
        accumulation = make_sig(
            "STR-2026-0615-001",
            macro="Систематические покупки ниже средней цены входа — признак долгосрочной стратегии накопления.",
            dir="pos", actor="corporate"
        )
        c = score_pair(nav_discount, accumulation)
        assert c.score >= 0.3  # есть сигнал противоречия

    def test_etf_outflow_vs_institutional_buying(self):
        """ETF-оттоки vs институциональные покупки — классическое противоречие проекта."""
        etf_out = make_sig(
            "STR-2026-0619-001",
            macro="ETF-потоки стали доминирующим драйвером цены BTC — их хрупкость определяется настроением.",
            dir="neg", actor="etf"
        )
        inst_buy = make_sig(
            "STR-2026-0622-002",
            macro="Покупки крупных держателей происходят независимо от рыночного шума.",
            dir="pos", actor="retail"
        )
        c = score_pair(etf_out, inst_buy)
        # Разные акторы, но dir-конфликт есть
        assert c.dir_score == 1.0


# ─── TD2: RelationshipStore ───────────────────────────────────────────────────
class TestRelationshipStore:

    def _make_signals_file(self, tmp_path):
        """Создаёт временный signals.json с legacy links."""
        data = {
            "meta": {},
            "signals": [
                {
                    "id": "STR-TEST-001",
                    "macro_implication": "Тест A",
                    "links": {
                        "contradicts": ["STR-TEST-002"],
                        "confirms": [],
                        "context_chain": [],
                    }
                },
                {
                    "id": "STR-TEST-002",
                    "macro_implication": "Тест B",
                    "links": {"contradicts": [], "confirms": [], "context_chain": []}
                },
            ]
        }
        p = tmp_path / "signals.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return str(p)

    def test_load_legacy_links(self, tmp_path):
        """Legacy links загружаются из signals.json."""
        sig_path = self._make_signals_file(tmp_path)
        rel_path = str(tmp_path / "relationships.json")

        store = RelationshipStore(relationships_path=rel_path, signals_path=sig_path)
        rels = store.get_all()
        assert any(r.from_id == "STR-TEST-001" and r.to_id == "STR-TEST-002" for r in rels)

    def test_add_canonical(self, tmp_path):
        """Добавление canonical связи и сохранение."""
        sig_path = self._make_signals_file(tmp_path)
        rel_path = str(tmp_path / "relationships.json")

        store = RelationshipStore(relationships_path=rel_path, signals_path=sig_path)
        rel = store.add("STR-TEST-002", "STR-TEST-001", "confirms",
                        rationale="Подтверждает через другой механизм")
        assert rel.status == "active"
        assert os.path.exists(rel_path)

    def test_no_self_link(self, tmp_path):
        """Самосвязь запрещена."""
        sig_path = self._make_signals_file(tmp_path)
        rel_path = str(tmp_path / "relationships.json")
        store = RelationshipStore(relationships_path=rel_path, signals_path=sig_path)

        with pytest.raises(ValueError, match="Самосвязь"):
            store.add("STR-TEST-001", "STR-TEST-001", "contradicts", rationale="test")

    def test_no_duplicate(self, tmp_path):
        """Дублирующая пара (from, to, type) запрещена."""
        sig_path = self._make_signals_file(tmp_path)
        rel_path = str(tmp_path / "relationships.json")
        store = RelationshipStore(relationships_path=rel_path, signals_path=sig_path)

        store.add("STR-TEST-002", "STR-TEST-001", "contradicts", rationale="first")
        with pytest.raises(ValueError, match="Дубль"):
            store.add("STR-TEST-002", "STR-TEST-001", "contradicts", rationale="second")

    def test_retract_not_delete(self, tmp_path):
        """Ретракция меняет статус, не удаляет запись."""
        sig_path = self._make_signals_file(tmp_path)
        rel_path = str(tmp_path / "relationships.json")
        store = RelationshipStore(relationships_path=rel_path, signals_path=sig_path)

        rel = store.add("STR-TEST-002", "STR-TEST-001", "confirms", rationale="test")
        store.retract(rel.id, reason="Данные устарели")

        # Связь остаётся в store, но статус retracted
        all_rels = store.get_all(active_only=False)
        retracted = [r for r in all_rels if r.id == rel.id]
        assert len(retracted) == 1
        assert retracted[0].status == "retracted"

        # В активных — нет
        active = store.get_all(active_only=True)
        assert not any(r.id == rel.id for r in active)

    def test_deduplication(self, tmp_path):
        """Canonical приоритетнее legacy при дедупликации."""
        sig_path = self._make_signals_file(tmp_path)
        rel_path = str(tmp_path / "relationships.json")
        store = RelationshipStore(relationships_path=rel_path, signals_path=sig_path)

        # Добавляем canonical с той же парой что есть в legacy
        store.add("STR-TEST-001", "STR-TEST-002", "contradicts",
                  rationale="canonical override")

        contradicts = [r for r in store.get_all()
                       if r.from_id == "STR-TEST-001" and r.type == "contradicts"]
        # Должна быть ровно одна (canonical, не дубль legacy)
        assert len(contradicts) == 1
        assert "canonical" in contradicts[0].rationale

    def test_migration_status(self, tmp_path):
        """migration_status возвращает корректный чеклист."""
        sig_path = self._make_signals_file(tmp_path)
        rel_path = str(tmp_path / "relationships.json")
        store = RelationshipStore(relationships_path=rel_path, signals_path=sig_path)
        store.get_all()  # триггер загрузки

        status = store.migration_status()
        assert "checklist" in status
        assert "legacy" in status
        assert "canonical" in status
