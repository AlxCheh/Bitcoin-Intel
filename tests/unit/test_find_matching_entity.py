"""
tests/unit/test_find_matching_entity.py
Bitcoin Intel — регрессионный тест findMatchingEntity() (AI-анализатор,
кнопки preset_question, вкладка Сигналы).

КОНТЕКСТ
--------
docs/BACKLOG.md зафиксировал баг: findMatchingEntity() сравнивал каждый
значимый токен вопроса с ПОЛНОЙ строкой кандидата (e.id или e.name) —
работало только для однословных сущностей (foundry, antpool, strive).
Для многословных (mara_holdings/"MARA Holdings", trump_media/"Trump Media
& Technology Group Corp." и т.д.) естественный вопрос не матчился вообще —
подтверждено на 5 сущностях за 5 сессий (см. BACKLOG.md для полной истории
находки).

Исправление — entityMatchTokens() + token-set сравнение в findMatchingEntity()
(ratio ≥ 0.5 различительных токенов кандидата найдены во вводе, вместо
токен-против-целой-строки). Этот тест — не копия логики, а сам production-
код, извлечённый из js/app-main.js тем же методом (extract_js_function/
run_node_js), что уже используется test_js_python_equivalence.py (ADR-010) и
test_xss_sanitization.py — иначе тест дрейфует от реального поведения сайта.

Тест проверяет ТРИ вещи одновременно:
1. Регрессия: 5 ранее подтверждённых сломанных случаев теперь матчатся.
2. Не сломано: однословные сущности, которые уже работали (foundry,
   antpool, strive), продолжают работать.
3. Защита от ложных срабатываний: общие/несвязанные вопросы не матчатся
   ни на одну сущность (ratio ≥ 0.5 — не настолько мягкий порог, чтобы
   давать случайные совпадения).

Требует Node.js в PATH (уже требуется test_js_python_equivalence.py).
"""
import json
import re
import shutil
from pathlib import Path

import pytest
from tests.conftest import extract_js_function, run_node_js

REPO_ROOT = Path(__file__).parent.parent.parent
APP_MAIN_JS = REPO_ROOT / "js" / "app-main.js"
ENTITIES_JSON = REPO_ROOT / "ENTITIES.json"

NODE_AVAILABLE = shutil.which("node") is not None


def _extract_ai_stop_words(src: str) -> str:
    """
    AI_STOP_WORDS — const с многострочным Set(), не function — extract_js_function
    не подходит (ищет `function <name>`). Извлекаем от объявления до первого
    закрывающего `]);` после него (набор плоский, вложенных скобок нет).
    """
    start = src.find("const AI_STOP_WORDS")
    assert start != -1, "AI_STOP_WORDS not found in js/app-main.js — renamed or removed?"
    end = src.find("]);", start)
    assert end != -1, "Closing ']);' for AI_STOP_WORDS not found"
    return src[start:end + 3] + "\n"


def _extract_entity_match_boilerplate(src: str) -> str:
    """
    ENTITY_MATCH_BOILERPLATE — тоже const с Set(), не function (тот же случай,
    что AI_STOP_WORDS выше).
    """
    start = src.find("const ENTITY_MATCH_BOILERPLATE")
    assert start != -1, "ENTITY_MATCH_BOILERPLATE not found in js/app-main.js — renamed or removed?"
    end = src.find(");", start)
    assert end != -1, "Closing ');' for ENTITY_MATCH_BOILERPLATE not found"
    return src[start:end + 2] + "\n"


@pytest.fixture(scope="module")
def js_source() -> str:
    """
    Реальные production-функции: AI_STOP_WORDS, aiTokenize, aiSignificantTokens,
    levenshtein, ENTITY_MATCH_BOILERPLATE, entityMatchTokens, findMatchingEntity —
    извлечены из js/app-main.js в порядке зависимостей, плюс глобальный ENTITIES
    из реального ENTITIES.json (та же сущность, что видит сайт).
    """
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    entities = json.loads(ENTITIES_JSON.read_text(encoding="utf-8"))
    entities_list = entities["entities"] if isinstance(entities, dict) and "entities" in entities else entities

    parts = [
        _extract_ai_stop_words(src),
        extract_js_function(src, "aiTokenize"),
        extract_js_function(src, "aiSignificantTokens"),
        extract_js_function(src, "levenshtein"),
        _extract_entity_match_boilerplate(src),
        extract_js_function(src, "entityMatchTokens"),
        extract_js_function(src, "findMatchingEntity"),
        f"const ENTITIES = {json.dumps(entities_list)};\n",
    ]
    return "\n".join(parts)


def _run_match(js_source: str, question: str) -> str | None:
    """Прогоняет вопрос через реальный findMatchingEntity(), возвращает entity id или None."""
    snippet = js_source + f"""
const inputTokens = aiSignificantTokens({json.dumps(question)});
const matched = findMatchingEntity(inputTokens);
console.log(JSON.stringify(matched ? matched.id : null));
"""
    result = run_node_js(snippet)
    assert result.returncode == 0, f"Node error for {question!r}: {result.stderr}"
    return json.loads(result.stdout.strip())


# (question, expected_entity_id) — 5 подтверждённых ранее сломанных случаев,
# см. docs/BACKLOG.md для истории находки каждого.
MULTIWORD_REGRESSION_CASES = [
    ("Сколько BTC у MARA Holdings?", "mara_holdings"),
    ("Сколько BTC у Twenty One Capital?", "twenty_one_capital"),
    ("Сколько BTC держит Trump Media?", "trump_media"),
    ("Что случилось с Samourai Wallet?", "samourai_wallet"),
    ("Сколько BTC заложено у Riot Platforms?", "riot_platforms"),
]

# Однословные сущности — уже работали до фикса, не должны сломаться.
SINGLE_WORD_REGRESSION_CASES = [
    ("Сколько сети контролирует Foundry?", "foundry"),
    ("Какая доля хешрейта у AntPool?", "antpool"),
    ("Сколько BTC у Strive?", "strive"),
]

# Частичное упоминание (только первое/самое узнаваемое слово) — должно
# матчиться благодаря ratio ≥ 0.5, не только полному названию.
PARTIAL_MENTION_CASES = [
    ("Сколько BTC у MARA?", "mara_holdings"),
    ("Продаёт ли Riot свой биткоин?", "riot_platforms"),
]

# Общие/несвязанные вопросы — НЕ должны матчиться ни на одну сущность.
FALSE_POSITIVE_GUARD_CASES = [
    "Сколько всего компаний держат биткоин?",
    "Какая сейчас цена биткоина?",
    "Что такое CoinJoin?",
]


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js not found in PATH")
@pytest.mark.parametrize("question,expected_id", MULTIWORD_REGRESSION_CASES)
def test_multiword_entities_now_match(js_source, question, expected_id):
    matched_id = _run_match(js_source, question)
    assert matched_id == expected_id, (
        f"{question!r} ожидался матч на {expected_id!r}, получено {matched_id!r} — "
        f"регрессия найденного и исправленного бага (docs/BACKLOG.md)"
    )


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js not found in PATH")
@pytest.mark.parametrize("question,expected_id", SINGLE_WORD_REGRESSION_CASES)
def test_single_word_entities_still_match(js_source, question, expected_id):
    matched_id = _run_match(js_source, question)
    assert matched_id == expected_id, (
        f"{question!r} ожидался матч на {expected_id!r}, получено {matched_id!r} — "
        f"регрессия ранее работавшего поведения"
    )


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js not found in PATH")
@pytest.mark.parametrize("question,expected_id", PARTIAL_MENTION_CASES)
def test_partial_mention_matches_via_ratio(js_source, question, expected_id):
    matched_id = _run_match(js_source, question)
    assert matched_id == expected_id, (
        f"{question!r} (частичное упоминание) ожидался матч на {expected_id!r}, "
        f"получено {matched_id!r}"
    )


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js not found in PATH")
@pytest.mark.parametrize("question", FALSE_POSITIVE_GUARD_CASES)
def test_generic_questions_do_not_false_match(js_source, question):
    matched_id = _run_match(js_source, question)
    assert matched_id is None, (
        f"{question!r} (общий вопрос без сущности) неожиданно матчится на "
        f"{matched_id!r} — ratio-порог слишком мягкий, ложное срабатывание"
    )
