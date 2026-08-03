"""
tests/unit/test_crosslink_target_length.py
Bitcoin Intel — регрессия на переполнение метки-CTA в crosslink (2026-08-01,
класс переименован в .crosslink-cta 2026-08-02 при переходе на Вариант 5).

КОНТЕКСТ: найдено пользователем на реальном скриншоте — crosslink с
target_label, равным полному названию панели ("Сид на костях: как создать
ключ, не доверяя генератору", 56 символов), утекал за пределы экрана.
CSS-класс (тогда .crosslink-target, теперь .crosslink-cta после перехода
на Вариант 5 — разделённая строка/кнопка) был рассчитан на короткие метки
вроде "DCA · 01" (8-20 символов у существующих статичных crosslink'ов в
index.html) — white-space: nowrap + flex-shrink: 0 не давали тексту ни
перенестись, ни сжаться.

Два независимых уровня защиты:
1. CSS исправлен (white-space: normal) — переполнение станет просто
   некрасивым переносом, не будет вылезать за экран, даже если контент
   снова окажется длинным.
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


def test_css_crosslink_cta_does_not_force_nowrap():
    """CSS-уровень защиты: длинная метка не должна снова уметь вылезать за экран."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r"\.crosslink-cta\s*\{([^}]*)\}", html)
    assert m, ".crosslink-cta CSS-правило не найдено (переименовано из .crosslink-target 2026-08-02)"
    rule_body = m.group(1)
    rule_body_no_comments = re.sub(r"/\*.*?\*/", "", rule_body, flags=re.DOTALL)
    rule_body_normalized = re.sub(r"\s+", "", rule_body_no_comments)
    assert "white-space:nowrap" not in rule_body_normalized, (
        "white-space:nowrap вернулся в .crosslink-cta — длинный target_label "
        "снова будет утекать за пределы экрана вместо переноса (см. находку 2026-08-01)"
    )


def test_theory_essays_crosslink_target_labels_stay_short():
    """
    Контентный уровень защиты — для THEORY_ESSAYS.json. Проверяет
    crosslinks (массив, единственный формат с 2026-08-02 — старое
    единственное число item.crosslink убрано полностью).
    """
    import json
    data = json.loads(THEORY_ESSAYS_JSON.read_text(encoding="utf-8"))
    offenders = []
    for item in data["items"]:
        for cl in item.get("crosslinks", []):
            if len(cl.get("target_label", "")) > MAX_TARGET_LABEL_LENGTH:
                offenders.append((item["id"], cl["target_label"]))
    assert not offenders, (
        f"target_label длиннее {MAX_TARGET_LABEL_LENGTH} символов (короткий тег "
        f"вроде 'DCA · 01', не полное название панели): {offenders}"
    )


def test_theory_topics_crosslink_target_labels_stay_short():
    """
    Тот же контентный уровень защиты — для THEORY_TOPICS.json. Проверяет
    crosslinks (массив, единственный формат с 2026-08-02).
    """
    import json
    data = json.loads((REPO_ROOT / "THEORY_TOPICS.json").read_text(encoding="utf-8"))
    offenders = []
    for topic in data["topics"]:
        for item in topic.get("items", []):
            for cl in item.get("crosslinks", []):
                if len(cl.get("target_label", "")) > MAX_TARGET_LABEL_LENGTH:
                    offenders.append((topic["id"], item.get("icon"), cl["target_label"]))
    assert not offenders, f"target_label длиннее {MAX_TARGET_LABEL_LENGTH} символов: {offenders}"


def test_no_singular_crosslink_field_remains():
    """
    2026-08-02: единый формат — только crosslinks (массив). Регрессия на
    случайный возврат старого item.crosslink (единственное число) в любом
    из двух файлов — по запросу пользователя старый формат убран
    полностью, не должен появиться снова незамеченным.
    """
    import json
    theory_essays = json.loads(THEORY_ESSAYS_JSON.read_text(encoding="utf-8"))
    theory_topics = json.loads((REPO_ROOT / "THEORY_TOPICS.json").read_text(encoding="utf-8"))

    offenders = [item["id"] for item in theory_essays["items"] if "crosslink" in item]
    for topic in theory_topics["topics"]:
        for item in topic.get("items", []):
            if "crosslink" in item:
                offenders.append(f"{topic['id']}/{item.get('icon')}")

    assert not offenders, f"Найден старый формат item.crosslink (единственное число): {offenders}"


def test_bitcoin_functions_crosslinks_labels_stay_short():
    """
    Тот же контентный уровень защиты — для BITCOIN_FUNCTIONS.json (поле
    crosslinks, добавлено 2026-08-02, использует тот же .crosslink-target
    визуальный класс, что и THEORY_ESSAYS/THEORY_TOPICS).
    """
    import json
    functions = json.loads((REPO_ROOT / "BITCOIN_FUNCTIONS.json").read_text(encoding="utf-8"))["functions"]
    offenders = []
    for fn in functions:
        for cl in fn.get("crosslinks", []):
            if len(cl.get("label", "")) > MAX_TARGET_LABEL_LENGTH:
                offenders.append((fn["id"], cl["label"]))
    assert not offenders, f"label длиннее {MAX_TARGET_LABEL_LENGTH} символов: {offenders}"
