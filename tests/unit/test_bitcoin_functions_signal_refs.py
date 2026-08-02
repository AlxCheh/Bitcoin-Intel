"""
tests/unit/test_bitcoin_functions_signal_refs.py
Bitcoin Intel — референциальная целостность signal_refs в
BITCOIN_FUNCTIONS.json (добавлено 2026-08-02, по запросу пользователя —
"для того и создаём wiki, чтобы связывать информацию между собой").

Первое применение связи BITCOIN_FUNCTIONS.json -> signals.json (Пара 6
из архивного PLAN-llm-wiki-cross-linking.md была отклонена как
"недостаточно материала", 5 записей) — теперь 6 записей и реальная,
органическая связь появилась на практике, не через автоматизацию.

Тот же принцип, что уже применяется к signal_refs в ENTITIES.json и
THEORY_ESSAYS.json/THEORY_TOPICS.json — ссылка обязана указывать на
реально существующий id в signals.json.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def test_all_bitcoin_functions_signal_refs_point_to_real_signals():
    functions = json.loads((REPO_ROOT / "BITCOIN_FUNCTIONS.json").read_text(encoding="utf-8"))["functions"]
    signal_ids = {
        s["id"] for s in json.loads((REPO_ROOT / "signals.json").read_text(encoding="utf-8"))["signals"]
    }

    invalid = []
    for fn in functions:
        for ref in fn.get("signal_refs", []):
            if ref not in signal_ids:
                invalid.append((fn["id"], ref))

    assert not invalid, f"signal_refs ссылаются на несуществующие сигналы: {invalid}"


def test_op_return_has_expected_signal_refs():
    """Регрессия на конкретный кейс, ради которого поле появилось."""
    functions = json.loads((REPO_ROOT / "BITCOIN_FUNCTIONS.json").read_text(encoding="utf-8"))["functions"]
    op_return = next((f for f in functions if f["id"] == "op-return-blockchain-notary"), None)
    assert op_return is not None

    refs = op_return.get("signal_refs", [])
    assert "NAR-2026-0711-001" in refs
    assert "NAR-2026-0717-003" in refs
