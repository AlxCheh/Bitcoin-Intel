"""
tests/unit/test_theory_dice_seed_mount_location.py
Bitcoin Intel — регрессия: точка монтирования theory-dice-seed-mount
обязана физически лежать внутри секции #tab-theory, не где-либо ещё
(2026-08-02).

КОНТЕКСТ: настоящая находка пользователя — крестик-накрестик правильные
все уровни диагностики (элемент найден, не дубликат, scrollIntoView
вызывается) не помогали, потому что элемент имел размер 0×0. Причина:
theory-dice-seed не имел собственной точки монтирования {id}-mount,
поэтому падал в общий запасной контейнер theory-topics-container — а
этот контейнер физически лежит внутри #tab-macrocontext, не #tab-theory.
Пока пользователь смотрит вкладку ТЕОРИЯ, #tab-macrocontext скрыт
(.section без .active — display:none), поэтому ВСЁ внутри него, включая
свежевставленную панель, получает нулевые размеры через getBoundingClientRect
— видимого перехода не происходит, хотя JS-код отрабатывает без единой
ошибки.

Другие уже существующие топики (theory-passphrase, theory-hashrate-units,
theory-governance, lightning-routing) имели явные точки монтирования
именно поэтому и работали корректно — этот тест не даёт новому топику
повторить тот же пропуск незамеченным.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _section_range(html: str, tab_id: str) -> tuple[int, int]:
    start = html.find(f'id="{tab_id}"')
    assert start != -1, f'Секция id="{tab_id}" не найдена в index.html'
    end = html.find("</section>", start)
    assert end != -1, f"Закрывающий </section> для {tab_id} не найден"
    return start, end


def test_theory_dice_seed_mount_exists_inside_tab_theory():
    html = INDEX_HTML.read_text(encoding="utf-8")
    start, end = _section_range(html, "tab-theory")
    assert 'id="theory-dice-seed-mount"' in html[start:end], (
        "theory-dice-seed-mount отсутствует внутри #tab-theory — топик "
        "провалится в запасной контейнер theory-topics-container, который "
        "физически лежит в #tab-macrocontext и невидим на вкладке ТЕОРИЯ "
        "(см. находку 2026-08-02: элемент найден, но 0×0 размера)"
    )


def test_all_theory_tab_topics_have_explicit_mounts():
    """
    Обобщение находки: любой топик, у которого нет естественной причины
    жить в запасном macrocontext-контейнере (theory-macro/theory-regulation
    — намеренное исключение, их место реально в macrocontext), обязан
    иметь свою явную точку монтирования внутри #tab-theory или
    #tab-lightning.
    """
    import json
    topics = json.loads((REPO_ROOT / "THEORY_TOPICS.json").read_text(encoding="utf-8"))["topics"]
    html = INDEX_HTML.read_text(encoding="utf-8")

    theory_start, theory_end = _section_range(html, "tab-theory")
    theory_html = html[theory_start:theory_end]

    lightning_start, lightning_end = _section_range(html, "tab-lightning")
    lightning_html = html[lightning_start:lightning_end]

    # Намеренное исключение — эти топики предназначены для #tab-macrocontext,
    # запасной контейнер там — их правильное, а не случайное место.
    INTENTIONAL_MACROCONTEXT_FALLBACK = {"theory-macro", "theory-regulation"}

    missing = []
    for topic in topics:
        tid = topic["id"]
        if tid in INTENTIONAL_MACROCONTEXT_FALLBACK:
            continue
        mount_marker = f'id="{tid}-mount"'
        if mount_marker not in theory_html and mount_marker not in lightning_html:
            missing.append(tid)

    assert not missing, (
        f"Топики без явной точки монтирования в #tab-theory/#tab-lightning: {missing} — "
        f"провалятся в запасной контейнер theory-topics-container (физически в "
        f"#tab-macrocontext) и будут иметь размер 0×0, пока смотрят вкладку ТЕОРИЯ. "
        f"Если это намеренно (топик для macrocontext) — добавь id в "
        f"INTENTIONAL_MACROCONTEXT_FALLBACK в этом тесте."
    )
