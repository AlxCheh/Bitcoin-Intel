"""
tests/unit/test_wiki_audit_connections.py
Bitcoin Intel — систематический аудит связей Пар 8/9 LLM Wiki (2026-08-03).
См. CLAUDE.md, раздел "LLM Wiki — систематический аудит-чекпоинт для Пар 8/9".

Проверяет три новых механизма:
1. renderOneCrosslink() в THEORY-пунктах теперь поддерживает type:'entity'
   (не только siteMapGoTo/crosslinkGo между панелями) - тот же паттерн,
   что уже был в renderFunctionCard().
2. showEntityPopup() теперь рендерит theory_refs как кликабельные бейджи
   "СВЯЗАННЫЕ ПАНЕЛИ ТЕОРИИ" (поле существовало в данных с 2026-08-02
   у coinkite, но ни разу не имело визуального представления).
3. Референциальная целостность всех 5 новых связей, найденных при
   систематическом проходе: Runes↔OP_RETURN, Tangem↔Multisig,
   $DOG Mode↔Governance, Foundry↔Governance, Breez↔Lightning-routing.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
APP_MAIN_JS = REPO_ROOT / "js" / "app-main.js"
NODE_AVAILABLE = shutil.which("node") is not None


def _extract_function(src: str, signature: str) -> str:
    start_marker = f"function {signature}"
    start = src.find(start_marker)
    assert start != -1, f"Function '{signature}' not found in app-main.js"
    brace_open = src.find("{", start)
    depth = 0
    i = brace_open
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1] + "\n"
        i += 1
    raise AssertionError(f"Unbalanced braces extracting '{signature}'")


@pytest.fixture(scope="module")
def app_src() -> str:
    return APP_MAIN_JS.read_text(encoding="utf-8")


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestTheoryItemEntityCrosslink:

    def test_render_acc_item_supports_entity_type_crosslink(self, app_src):
        render_source = "\n\n".join([
            _extract_function(app_src, "sanitize"),
            _extract_function(app_src, "sanitizeStrong"),
            _extract_function(app_src, "renderToolBlock"),
            _extract_function(app_src, "renderAccItem"),
            _extract_function(app_src, "sourceFooterHtml"),
        ])
        item = {
            "icon": "01", "label": "Тест",
            "crosslinks": [{"type": "entity", "entity_id": "test_entity", "text": "T", "label": "L"}]
        }
        js = render_source + f"""
const item = {json.dumps(item)};
console.log(JSON.stringify({{ html: renderAccItem(item) }}));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert "showEntityPopup('test_entity')" in html

    def test_theory_crosslink_still_uses_site_map_go_to(self, app_src):
        """Обратная совместимость - существующий type:'theory'/без type не сломан новым веткой type:'entity'."""
        render_source = "\n\n".join([
            _extract_function(app_src, "sanitize"),
            _extract_function(app_src, "sanitizeStrong"),
            _extract_function(app_src, "renderToolBlock"),
            _extract_function(app_src, "renderAccItem"),
            _extract_function(app_src, "sourceFooterHtml"),
        ])
        item = {
            "icon": "01", "label": "Тест",
            "crosslinks": [{"target_tab": "tech", "target_panel": "Панель Х", "text": "T", "target_label": "L"}]
        }
        js = render_source + f"""
const item = {json.dumps(item)};
console.log(JSON.stringify({{ html: renderAccItem(item) }}));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert "siteMapGoTo('tech','Панель Х')" in html


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestEntityPopupTheoryRefs:

    def _run_popup(self, app_src: str, entity: dict, topics: list) -> str:
        popup_source = "\n\n".join([
            _extract_function(app_src, "sanitize"),
            _extract_function(app_src, "showEntityPopup"),
        ])
        js = f"""
{popup_source}
const ENTITIES = [{json.dumps(entity)}];
const BITCOIN_FUNCTIONS = [];
const THEORY_TOPICS = {json.dumps(topics)};
const TYPE_META = {{}};

function makeEl() {{
  const classes = new Set();
  return {{
    _text: '', _html: '',
    get textContent() {{ return this._text; }}, set textContent(v) {{ this._text = v; }},
    get innerHTML() {{ return this._html; }}, set innerHTML(v) {{ this._html = v; }},
    classList: {{ add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c) }}
  }};
}}
const registry = {{}};
['ep-name','ep-type','ep-summary','ep-metrics','ep-notable','ep-refs','ep-function-refs','ep-theory-refs','entity-popup','ep-overlay'].forEach(id => registry[id] = makeEl());
const document = {{ getElementById: id => registry[id] }};

showEntityPopup('{entity["id"]}');
console.log(JSON.stringify({{ html: registry['ep-theory-refs'].innerHTML }}));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        return json.loads(result.stdout)["html"]

    def test_theory_ref_renders_clickable_badge_with_looked_up_title(self, app_src):
        entity = {"id": "e1", "name": "E1", "type": "protocol", "status": "active", "summary": "S",
                   "theory_refs": ["topic1"]}
        topics = [{"id": "topic1", "panel_title": "Панель Один"}]
        html = self._run_popup(app_src, entity, topics)
        assert "goToPanelFromPopup('theory','Панель Один')" in html
        assert "Панель Один" in html

    def test_no_theory_refs_renders_empty(self, app_src):
        entity = {"id": "e1", "name": "E1", "type": "protocol", "status": "active", "summary": "S"}
        html = self._run_popup(app_src, entity, [])
        assert html == ""

    def test_real_dog_mode_entity_has_working_theory_ref(self, app_src):
        """Регрессия на реальные данные - конкретный кейс аудита 2026-08-03."""
        entities = json.loads((REPO_ROOT / "ENTITIES.json").read_text(encoding="utf-8"))["entities"]
        dog_mode = next((e for e in entities if e["id"] == "dog_mode"), None)
        assert dog_mode is not None
        assert "theory-governance" in dog_mode.get("theory_refs", [])

        topics = json.loads((REPO_ROOT / "THEORY_TOPICS.json").read_text(encoding="utf-8"))["topics"]
        html = self._run_popup(app_src, dog_mode, topics)
        assert "Bitcoin Governance" in html
        assert "goToPanelFromPopup('theory'," in html


def test_all_five_audit_connections_referentially_intact():
    """
    Референциальная целостность всех 5 связей, найденных при
    систематическом проходе 2026-08-03 - обе стороны каждой связи
    существуют и указывают друг на друга корректно.
    """
    entities = {e["id"]: e for e in json.loads((REPO_ROOT / "ENTITIES.json").read_text(encoding="utf-8"))["entities"]}
    functions = {f["id"]: f for f in json.loads((REPO_ROOT / "BITCOIN_FUNCTIONS.json").read_text(encoding="utf-8"))["functions"]}
    topics = json.loads((REPO_ROOT / "THEORY_TOPICS.json").read_text(encoding="utf-8"))["topics"]

    # Runes <-> OP_RETURN
    assert "op-return-blockchain-notary" in entities["runes"]["function_refs"]
    assert any(
        cl.get("entity_id") == "runes"
        for cl in functions["op-return-blockchain-notary"].get("crosslinks", [])
    )

    # Tangem <-> Multisig
    assert "multisig-2of3" in entities["tangem"]["function_refs"]
    assert any(
        cl.get("entity_id") == "tangem"
        for cl in functions["multisig-2of3"].get("crosslinks", [])
    )

    # $DOG Mode, Foundry <-> theory-governance/Enforcement
    assert "theory-governance" in entities["dog_mode"]["theory_refs"]
    assert "theory-governance" in entities["foundry"]["theory_refs"]
    gov_topic = next(t for t in topics if t["id"] == "theory-governance")
    enforcement_item = next(i for i in gov_topic["items"] if i["label"] == "Enforcement")
    linked_entity_ids = {cl.get("entity_id") for cl in enforcement_item.get("crosslinks", [])}
    assert "dog_mode" in linked_entity_ids
    assert "foundry" in linked_entity_ids

    # Breez <-> lightning-routing/HTLC
    assert "lightning-routing" in entities["breez"]["theory_refs"]
    lr_topic = next(t for t in topics if t["id"] == "lightning-routing")
    htlc_item = next(i for i in lr_topic["items"] if i["label"] == "Сеть каналов и HTLC")
    assert any(cl.get("entity_id") == "breez" for cl in htlc_item.get("crosslinks", []))


def test_coinkite_multisig_link_not_disturbed_by_audit():
    """
    Регрессия - добавление Tangem, затем BitGo к multisig-2of3.crosslinks
    не должно было затронуть уже существующие связи (Coinkite - более
    ранняя сессия, Tangem - первый проход аудита 2026-08-03, BitGo -
    второй проход, расширивший скан за пределы типа l2/protocol/
    infrastructure).
    """
    functions = json.loads((REPO_ROOT / "BITCOIN_FUNCTIONS.json").read_text(encoding="utf-8"))["functions"]
    multisig = next(f for f in functions if f["id"] == "multisig-2of3")
    entity_ids = {cl.get("entity_id") for cl in multisig.get("crosslinks", []) if cl.get("type") == "entity"}
    assert "coinkite" in entity_ids
    assert "tangem" in entity_ids
    assert "bitgo" in entity_ids


def test_bitgo_second_pass_connection_referentially_intact():
    """BitGo <-> Multisig 2-of-3 (второй проход аудита, type=exchange - за пределами исходного фильтра l2/protocol/infrastructure)."""
    entities = {e["id"]: e for e in json.loads((REPO_ROOT / "ENTITIES.json").read_text(encoding="utf-8"))["entities"]}
    assert "multisig-2of3" in entities["bitgo"]["function_refs"]
