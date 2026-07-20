"""
tests/unit/test_xss_sanitization.py
Bitcoin Intel — регрессионный тест XSS-защиты (B2 ARR v3, SECURITY.md T1).

index.html — единственный файл сайта (CLAUDE.md), поэтому sanitize() и
highlightEntities() живут как inline JS внутри index.html, а не как отдельный
импортируемый модуль. Этот тест извлекает РЕАЛЬНЫЙ исходный код этих функций
прямо из index.html (тем же способом, каким он будет исполняться в браузере)
и запускает его через Node.js — это проверяет именно то, что физически
задеплоено на сайт, а не отдельную копию логики, которая могла бы разойтись
с production-кодом.

Требует Node.js в PATH (доступен на GitHub Actions ubuntu-latest по умолчанию).
"""
import re
import json
import subprocess
import shutil
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).parent.parent.parent
INDEX_HTML = REPO_ROOT / "index.html"

NODE_AVAILABLE = shutil.which("node") is not None


def _extract_function(html: str, signature: str) -> str:
    """
    Извлекает тело функции `function <signature> {...}` из index.html по
    балансу фигурных скобок (устойчиво к любому уровню отступа закрывающей
    скобки — regex с фиксированным отступом однажды уже обрезал
    synthesizeNarrativeAdvanced на первой вложенной '}' с совпадающим
    отступом, см. tests/unit/test_uncertainty_indicator.py).
    """
    base_name = signature.split("(")[0].strip()
    start = html.find(f"function {base_name}")
    assert start != -1, f"Function '{signature}' not found in index.html — was it renamed or removed?"
    brace_open = html.find("{", start)
    assert brace_open != -1, f"No opening brace found for '{signature}'"
    depth = 0
    i = brace_open
    while i < len(html):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return html[start:i + 1]
        i += 1
    raise AssertionError(f"Unbalanced braces while extracting '{signature}'")


def _run_js(js_code: str) -> dict:
    """Запускает JS-сниппет через node и возвращает распарсенный JSON из stdout."""
    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, f"Node execution failed:\n{result.stderr}"
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def sanitize_and_highlight_source() -> str:
    """Реальный исходник sanitize() + highlightEntities() из index.html."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    sanitize_fn   = _extract_function(html, "sanitize(str)")
    highlight_fn  = _extract_function(html, "highlightEntities(text)")
    return sanitize_fn + "\n\n" + highlight_fn


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestXSSSanitization:
    """B2 ARR v3: данные сигналов/сущностей не должны исполняться как HTML/JS."""

    def test_sanitize_escapes_script_payload(self, sanitize_and_highlight_source):
        """Классический XSS-payload полностью обезврежен."""
        js = sanitize_and_highlight_source + """
const out = sanitize('<img src=x onerror=alert(1)>');
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert "<img" not in result["out"]
        assert "&lt;img" in result["out"]
        assert "onerror" in result["out"]  # текст остаётся, но не как тег

    def test_sanitize_escapes_all_five_special_chars(self, sanitize_and_highlight_source):
        """&, <, >, \", ' — все пять экранируются."""
        js = sanitize_and_highlight_source + """
const out = sanitize(`&<>"'`);
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert result["out"] == "&amp;&lt;&gt;&quot;&#x27;"

    def test_sanitize_handles_null_and_undefined(self, sanitize_and_highlight_source):
        """null/undefined → пустая строка, не исключение."""
        js = sanitize_and_highlight_source + """
console.log(JSON.stringify({
    n: sanitize(null),
    u: sanitize(undefined),
    num: sanitize(123),
}));
"""
        result = _run_js(js)
        assert result["n"] == ""
        assert result["u"] == ""
        assert result["num"] == "123"

    def test_sanitize_idempotent_on_plain_text(self, sanitize_and_highlight_source):
        """Обычный текст без спецсимволов не искажается."""
        js = sanitize_and_highlight_source + """
const text = 'ETF-приток создаёт структурный спрос на BTC';
console.log(JSON.stringify({ out: sanitize(text), original: text }));
"""
        result = _run_js(js)
        assert result["out"] == result["original"]

    def test_highlight_entities_blocks_xss_while_preserving_entity_span(
        self, sanitize_and_highlight_source
    ):
        """
        Регрессия для T1 SECURITY.md: вредоносный payload в тексте сигнала не
        исполняется как HTML, а легитимное упоминание сущности (Strategy)
        всё ещё подсвечивается через <span data-entity-id>.
        """
        js = sanitize_and_highlight_source + """
const ENTITIES = [{ id: 'strategy', name: 'Strategy' }];
const payload = '<img src=x onerror=alert(1)> Strategy накапливает BTC';
const out = highlightEntities(payload);
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert "<img" not in result["out"], "XSS payload must not survive as a real tag"
        assert 'data-entity-id="strategy"' in result["out"], (
            "Legitimate entity highlighting must still work after sanitization"
        )
        assert "<span class=\"entity-link\"" in result["out"]

    def test_highlight_entities_sanitizes_even_without_entities(
        self, sanitize_and_highlight_source
    ):
        """Если ENTITIES пуст — highlightEntities всё равно обязана санитизировать (ранний return не должен пропускать XSS)."""
        js = sanitize_and_highlight_source + """
const ENTITIES = [];
const out = highlightEntities('<script>alert(1)</script>');
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert "<script>" not in result["out"]
        assert "&lt;script&gt;" in result["out"]


@pytest.fixture(scope="module")
def sanitize_strong_source() -> str:
    """Реальный исходник sanitize() + sanitizeStrong() из index.html."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    sanitize_fn = _extract_function(html, "sanitize(str)")
    strong_fn   = _extract_function(html, "sanitizeStrong(str)")
    return sanitize_fn + "\n\n" + strong_fn


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestSanitizeStrong:
    """
    sanitizeStrong() — узкий allowlist поверх sanitize(): экранирует всё,
    затем точечно возвращает буквально <strong>/</strong> (введена при
    миграции THEORY_TOPICS.json, PR #348 — параграфы эссе с инлайн-выделением).
    Контракт: НИКАКОЙ другой HTML и никакие атрибуты пройти не могут.
    """

    def test_preserves_bare_strong_tags(self, sanitize_strong_source):
        """<strong>слово</strong> выживает как настоящий тег."""
        js = sanitize_strong_source + """
const out = sanitizeStrong('канал имеет <strong>входящую</strong> ликвидность');
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert "<strong>входящую</strong>" in result["out"]
        assert "&lt;strong&gt;" not in result["out"]

    def test_blocks_strong_with_attributes(self, sanitize_strong_source):
        """
        <strong onclick=...> НЕ восстанавливается: allowlist матчит только
        буквальные '&lt;strong&gt;'/'&lt;/strong&gt;' — тег с любым атрибутом
        экранируется в &lt;strong onclick=...&gt; и таким остаётся.
        """
        js = sanitize_strong_source + """
const out = sanitizeStrong('<strong onclick=alert(1)>x</strong>');
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert "<strong onclick" not in result["out"]
        assert "&lt;strong onclick=alert(1)&gt;" in result["out"]
        # закрывающий тег без атрибутов при этом легально восстановлен
        assert "</strong>" in result["out"]

    def test_blocks_all_other_tags(self, sanitize_strong_source):
        """script/img/em — всё, кроме strong, остаётся экранированным."""
        js = sanitize_strong_source + """
const out = sanitizeStrong('<script>alert(1)<\\/script><img src=x onerror=alert(1)><em>i</em>');
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert "<script" not in result["out"]
        assert "<img" not in result["out"]
        assert "<em>" not in result["out"]
        assert "&lt;script&gt;" in result["out"]

    def test_escapes_other_special_chars_like_sanitize(self, sanitize_strong_source):
        """Вне strong-тегов поведение идентично sanitize(): все 5 спецсимволов."""
        js = sanitize_strong_source + """
const out = sanitizeStrong(`&<>"'`);
console.log(JSON.stringify({ out }));
"""
        result = _run_js(js)
        assert result["out"] == "&amp;&lt;&gt;&quot;&#x27;"

    def test_handles_null_and_undefined(self, sanitize_strong_source):
        """null/undefined → пустая строка (унаследовано от sanitize())."""
        js = sanitize_strong_source + """
console.log(JSON.stringify({
    n: sanitizeStrong(null),
    u: sanitizeStrong(undefined),
}));
"""
        result = _run_js(js)
        assert result["n"] == ""
        assert result["u"] == ""

    def test_plain_text_untouched(self, sanitize_strong_source):
        """Обычный текст без спецсимволов не искажается."""
        js = sanitize_strong_source + """
const text = 'Метод Diceware: бросаешь кости, число указывает на слово';
console.log(JSON.stringify({ out: sanitizeStrong(text), original: text }));
"""
        result = _run_js(js)
        assert result["out"] == result["original"]


def test_all_signal_text_fields_pass_through_sanitize_or_highlight():
    """
    Статическая проверка: каждое поле сигнала, которое в index.html вставляется
    через innerHTML (signal, context, caveat, source, data, catLabel,
    theory_ref), обёрнуто либо sanitize(...), либо highlightEntities(...)
    (которая сама вызывает sanitize внутри).

    Эта проверка — защита от регрессии: если кто-то добавит новое поле сигнала
    в innerHTML без оборачивания, тест укажет на конкретную непрошедшую строку.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")

    # Паттерны небезопасной прямой вставки — поле сигнала сразу после '+' без
    # sanitize(...)/highlightEntities(...) перед закрывающей кавычкой/конкатенацией.
    unsafe_patterns = [
        r"\+\s*s\.signal\s*\+",
        r"\+\s*s\.context\s*\+",
        r"\+\s*s\.caveat\s*\+",
        r"\+\s*s\.source\s*\+",
        r"\+\s*s\.catLabel\s*\+",
        r"\+\s*s\.theory_ref\s*\+",
        r"\+\s*e\.name\s*\+",
        r"\+\s*e\.summary\s*\+",
    ]
    violations = []
    for pattern in unsafe_patterns:
        if re.search(pattern, html):
            violations.append(pattern)

    assert not violations, (
        f"Found unwrapped signal/entity field(s) directly concatenated into "
        f"innerHTML-bound strings (must go through sanitize() or "
        f"highlightEntities()): {violations}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Структурный страж sanitize-покрытия (ratchet/трещотка)
#
# Проблема прежнего стража выше (test_all_signal_text_fields_...): он ловит
# только 8 заранее перечисленных ИМЁН полей. Новое поле нового реестра
# (THEORY_TOPICS, THEORY_ESSAYS, ...) в innerHTML проходит незамеченным —
# ровно тот класс регрессий, против которого в проекте заведены FACTS и
# SITE_MAP (процедура без механизма не держится, AD-6 в docs/NIES.md).
#
# Этот страж работает структурно: находит ВСЕ конкатенации property-access
# выражений в строковые литералы ('...' + obj.field + '...') внутри <script>,
# отбрасывает заведомо безопасные (обёрнутые в санитайзеры, числовые методы
# toFixed/toLocaleString, литеральную арифметику, палитру C.*) и сверяет
# остаток с BASELINE — вручную классифицированным снимком 2026-07-17
# (75 выражений / 99 вхождений, см. JS_AUDIT_SPEC.md Часть 1).
#
# Сверка двусторонняя (паттерн test_site_map_sync):
#   - НОВОЕ выражение или рост счётчика → тест падает: либо оберни в
#     sanitize()/sanitizeStrong()/highlightEntities(), либо осознанно добавь
#     в baseline с комментарием, почему безопасно.
#   - Выражение исчезло/счётчик упал → тест тоже падает: убери из baseline,
#     чтобы список не протухал.
#
# Известные ограничения (осознанные):
#   - Анализ построчный: конкатенация, разорванная переносом строки между
#     '+' и выражением, не попадает в контур. Ratchet ловит доминирующий
#     стиль кодовой базы, не претендуя на полноту AST-анализа.
#   - Bare-идентификаторы (локальные переменные без точки) вне контура:
#     статически неотличимы числа от строк, а шум обесценил бы страж.
# ═══════════════════════════════════════════════════════════════════════════

_CONCAT_RE = re.compile(r"""['"`]\s*\+\s*([^+]+?)\s*\+\s*['"`]""")

# Выражение считается безопасным без записи в baseline:
_SAFE_WRAPPER_RE = re.compile(r"^(sanitize|sanitizeStrong|highlightEntities)\s*\(")
_SAFE_METHOD_RE = re.compile(
    r"\.(toFixed|toLocaleString|toISOString|padStart|padEnd"
    r"|toUpperCase|toLowerCase|join)\([^)]*\)$"
)
_NUMERIC_LITERAL_RE = re.compile(r"^[\d\s+\-*/%().]+$")
_MATH_RE = re.compile(r"^Math\.\w+")

# Контур: property-access (поля объектов данных); палитра C.* — константы кода.
_IN_SCOPE_RE = re.compile(r"^\(?[a-zA-Z_$][\w$]*\.[\w$.]+")
_CODE_CONST_RE = re.compile(r"^C\.\w+$")


def _extract_all_script_js(html: str) -> str:
    """Содержимое всех <script>-блоков index.html одной строкой."""
    return "\n".join(re.findall(r"<script>(.*?)</script>", html, re.S))


def _find_unsanitized_property_concats(js: str) -> dict:
    """
    Счётчик {нормализованное выражение: число вхождений} для всех
    property-access конкатенаций в строковые литералы, не прошедших
    allowlist безопасности.
    """
    from collections import Counter

    counts: Counter = Counter()
    for line in js.split("\n"):
        for m in _CONCAT_RE.finditer(line):
            expr = " ".join(m.group(1).strip().split())
            if not _IN_SCOPE_RE.match(expr):
                continue
            if _CODE_CONST_RE.match(expr):
                continue
            if (
                _SAFE_WRAPPER_RE.match(expr)
                or _SAFE_METHOD_RE.search(expr)
                or _NUMERIC_LITERAL_RE.match(expr)
                or _MATH_RE.match(expr)
            ):
                continue
            counts[expr] += 1
    return dict(counts)


# Снимок 2026-07-17. Классификация по категориям риска — JS_AUDIT_SPEC.md,
# Часть 1, таблица B. Ни одно выражение здесь не читает пользовательский
# ввод: все источники — файлы собственного репозитория. Записи с пометкой
# [1.3] — кандидаты на оборачивание в sanitize по шагу 1.3 аудита; после
# него их счётчики уменьшатся и baseline обновится тем же PR.
SANITIZE_RATCHET_BASELINE = {
    # ── числовые поля (вывод заведомо числовой, sanitize избыточен) ──
    "(cl.neg||0)": 1,
    "(cl.neu||0)": 1,
    "(cl.pos||0)": 1,
    "(counts.neu||0.1)": 1,
    "(dir.neg||0)": 1,
    "(dir.neu||0.1)": 1,
    "(dir.pos||0)": 1,
    "SIGNALS.length": 1,
    "counts.neg": 3,
    "counts.neu": 2,
    "counts.pos": 3,
    "e.drop_pct": 1,
    "e.years": 1,
    "engine.history.length": 1,
    "filteredClosed.length": 1,
    "first.cat.pct": 3,
    "h.rank": 1,
    "ids.length": 1,
    "last.cat.pct": 2,
    "peak.cat.pct": 1,
    "r.n": 1,
    "score.freshness": 1,
    "score.roles": 1,
    "score.tension": 1,
    "score.total": 2,
    "score.weight": 1,
    "sorted.length": 1,
    "v.pct": 2,
    # ── тернарники с литеральными исходами (оба исхода — строки в коде) ──
    "(freshness.stale ? 'rgba(194,96,96,.4)' : 'rgba(122,139,160,.35)')": 1,
    "(freshness.stale ? 'var(--red)' : 'var(--dim)')": 1,
    "(item.open ? ' open' : '')": 1,
    # ── словари-константы кода (значения — литералы в index.html) ──
    "actorMeta.label": 1,
    "d.icon": 1,
    "d.label": 1,
    "flowMeta.icon": 1,
    "flowMeta.label": 1,
    "meta.label": 1,
    "phaseInfo.border": 1,
    "phaseInfo.color": 2,
    "phaseInfo.label": 1,
    # ── данные из репозиторных JSON/JS-файлов (низкий риск; [1.3]) ──
    "(TREASURY_META.public_holders_count || '?')": 1,
    "(anchorObj.weight || '?')": 1,
    "(s.theory_ref === 'theory-network' ? 'СЕМЬ СЕТЕВЫХ ЭФФЕКТОВ' : safeTheoryRef.replace('theory-','').toUpperCase())": 1,
    "c.label": 2,
    "cluster.label": 1,
    "etfEx.as_of": 1,
    "fact.signal_id": 1,
    "first.date": 3,
    "h.date": 1,
    "item.source": 1,
    "item.target": 2,
    "item.title": 1,
    "last.date": 2,
    "n.event": 1,
    "p.country": 1,
    "p.history": 1,
    "p.name": 1,
    "p.notes": 1,
    "p.owner": 1,
    "peak.date": 1,
    "r.name": 2,
    "s.date": 2,
    "s.dir": 1,
    # не-HTML контекст: сборка текстового промпта AI-анализатора
    # (snapshotText) — детектор не различает HTML/текст, sanitize здесь
    # был бы вреден (внёс бы &quot; в промпт)
    "s.event": 1,
    "t.key": 1,
    "t.label": 2,
    "t.note": 1,
    "tab.label": 1,
    "top100.as_of": 1,
    "w.event": 1,
    "w.label": 2,
    "w.note": 1,
    "w.wave": 2,
    "w.year": 2,
}


def test_no_new_unsanitized_property_concats_ratchet():
    """
    Ratchet: любое НОВОЕ property-access выражение в innerHTML-конкатенации
    (или рост счётчика существующего) без sanitize-обёртки ломает тест.
    Двусторонняя сверка не даёт baseline протухать.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    current = _find_unsanitized_property_concats(_extract_all_script_js(html))

    new_or_grown = {
        expr: n for expr, n in current.items()
        if n > SANITIZE_RATCHET_BASELINE.get(expr, 0)
    }
    gone_or_shrunk = {
        expr: n for expr, n in SANITIZE_RATCHET_BASELINE.items()
        if current.get(expr, 0) < n
    }

    assert not new_or_grown, (
        "Новые несанитизированные вставки данных в HTML-строки: "
        f"{new_or_grown}. Оберни в sanitize()/sanitizeStrong()/"
        "highlightEntities() — либо, если вывод заведомо безопасен "
        "(число, литерал), осознанно добавь в SANITIZE_RATCHET_BASELINE "
        "с комментарием-категорией."
    )
    assert not gone_or_shrunk, (
        "Выражения из SANITIZE_RATCHET_BASELINE исчезли из index.html "
        f"или их стало меньше: {gone_or_shrunk}. Обнови baseline тем же "
        "PR (уменьши счётчики/удали записи), чтобы список не протухал."
    )


def test_ratchet_detector_catches_injected_unsafe_concat():
    """
    Проверка самого детектора на подставном кейсе (паттерн
    test_check_stale_facts_catches_injected_stale_copy): инжектированная
    небезопасная вставка ловится, а sanitize-обёрнутая — нет.
    """
    injected = """
el.innerHTML = '<div class="x">' + s.brandNewField + '</div>';
safe.innerHTML = '<div class="y">' + sanitize(s.otherField) + '</div>';
num.innerHTML = '<td>' + row.total.toFixed(2) + '</td>';
"""
    found = _find_unsanitized_property_concats(injected)
    assert found == {"s.brandNewField": 1}, (
        f"Детектор должен поймать ровно s.brandNewField, получено: {found}"
    )
