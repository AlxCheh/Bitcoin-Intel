"""
tests/unit/test_entity_theory_refs.py
Bitcoin Intel — референциальная целостность нового поля theory_refs в
ENTITIES.json (добавлено 2026-08-01, по запросу пользователя — связь
сущности coinkite с полноценной панелью theory-dice-seed).

Тот же принцип, что уже применяется к signal_refs (validate_integrity.py) —
theory_refs обязан ссылаться на реально существующий topic.id в
THEORY_TOPICS.json, не на произвольную строку.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def test_all_theory_refs_point_to_real_topics():
    entities = json.loads((REPO_ROOT / "ENTITIES.json").read_text(encoding="utf-8"))["entities"]
    topic_ids = {
        t["id"] for t in json.loads((REPO_ROOT / "THEORY_TOPICS.json").read_text(encoding="utf-8"))["topics"]
    }

    invalid = []
    for e in entities:
        for ref in e.get("theory_refs", []):
            if ref not in topic_ids:
                invalid.append((e["id"], ref))

    assert not invalid, f"theory_refs ссылаются на несуществующие топики: {invalid}"


def test_coinkite_has_theory_ref_to_dice_seed():
    """Регрессия на конкретный кейс, ради которого поле появилось."""
    entities = json.loads((REPO_ROOT / "ENTITIES.json").read_text(encoding="utf-8"))["entities"]
    coinkite = next((e for e in entities if e["id"] == "coinkite"), None)
    assert coinkite is not None, "Сущность coinkite не найдена"
    assert "theory-dice-seed" in coinkite.get("theory_refs", []), (
        "coinkite.theory_refs должен указывать на theory-dice-seed"
    )
