"""
tests/unit/test_crosslink_target_length.py
Bitcoin Intel — регрессия на переполнение .crosslink-target (2026-08-01).

КОНТЕКСТ: найдено пользователем на реальном скриншоте — crosslink с
target_label, равным полному названию панели ("Сид на костях: как создать
ключ, не доверяя генератору", 56 символов), утекал за пределы экрана.
CSS .crosslink-target был рассчитан на короткие метки вроде "DCA · 01"
(8-20 символов у существующих статичных crosslink'ов в index.html) —
white-space: nowrap + flex-shrink: 0 не давали тексту ни перенестись,
ни сжаться.

Два независимых уровня защиты:
1. CSS исправлен (white-space: normal, flex-shrink: 1) — переполнение
   станет просто некрасивым переносом, не будет вылезать за экран,
   даже если контент снова окажется длинным.
2. Контентная проверка здесь — не даёт длинной метке появиться вообще,
   по аналогии с существующими короткими ("DCA · 01", "Деньги · 05").
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
THEORY_ESSAYS_JSON = REPO_ROOT / "THEORY_ESSAYS.json"

# Существующие статичные target_label в index.html — самый длинный на
# сегодня 20 символов ("Сетевые эффекты · 07"). Порог с запасом, но далеко
# от полноразмерного названия панели (получилось 56 символов у находки).
MAX_TARGET_LABEL_LENGTH = 30


def test_css_crosslink_target_does_not_force_nowrap():
    """CSS-уровень защиты: длинная метка не должна снова уметь вылезать за экран."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r"\.crosslink-target\s*\{([^}]*)\}", html)
    assert m, ".crosslink-target CSS-правило не найдено"
    rule_body = m.group(1)
    rule_body_no_comments = re.sub(r"/\*.*?\*/", "", rule_body, flags=re.DOTALL)
    rule_body_normalized = re.sub(r"\s+", "", rule_body_no_comments)
    assert "white-space:nowrap" not in rule_body_normalized, (
        "white-space:nowrap вернулся в .crosslink-target — длинный target_label "
        "снова будет утекать за пределы экрана вместо переноса (см. находку 2026-08-01)"
    )


def test_theory_essays_crosslink_target_labels_stay_short():
    """Контентный уровень защиты — для THEORY_ESSAYS.json."""
    import json
    data = json.loads(THEORY_ESSAYS_JSON.read_text(encoding="utf-8"))
    offenders = []
    for item in data["items"]:
        cl = item.get("crosslink")
        if cl and "target_label" in cl:
            if len(cl["target_label"]) > MAX_TARGET_LABEL_LENGTH:
                offenders.append((item["id"], cl["target_label"]))
    assert not offenders, (
        f"target_label длиннее {MAX_TARGET_LABEL_LENGTH} символов (короткий тег "
        f"вроде 'DCA · 01', не полное название панели): {offenders}"
    )


def test_theory_topics_crosslink_target_labels_stay_short():
    """Тот же контентный уровень защиты — для THEORY_TOPICS.json (items внутри топиков тоже могут нести crosslink)."""
    import json
    data = json.loads((REPO_ROOT / "THEORY_TOPICS.json").read_text(encoding="utf-8"))
    offenders = []
    for topic in data["topics"]:
        for item in topic.get("items", []):
            cl = item.get("crosslink")
            if cl and "target_label" in cl:
                if len(cl["target_label"]) > MAX_TARGET_LABEL_LENGTH:
                    offenders.append((topic["id"], item.get("icon"), cl["target_label"]))
    assert not offenders, f"target_label длиннее {MAX_TARGET_LABEL_LENGTH} символов: {offenders}"
