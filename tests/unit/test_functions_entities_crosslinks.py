"""
tests/unit/test_functions_entities_crosslinks.py
Bitcoin Intel — двусторонние кликабельные связи между BITCOIN_FUNCTIONS.json,
ENTITIES.json и THEORY_TOPICS.json (2026-08-02, по запросу пользователя:
"хотел бы, чтобы все связи между сущностями были кликабельные").

Первая реализованная пара: multisig-2of3 <-> coinkite <-> theory-dice-seed
(пункт 07). Три канала клика:
1. renderFunctionCard() -> showEntityPopup(id) для type:"entity"
2. renderFunctionCard() -> siteMapGoTo(tab, label) для type:"theory"
3. showEntityPopup() -> goToPanelFromPopup(tab, label) для function_refs
   (закрывает попап, затем siteMapGoTo — обёртка, не новая логика поиска)
"""
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
class TestFunctionCardCrosslinks:

    def test_entity_type_crosslink_calls_show_entity_popup(self, app_src):
        render_source = "\n\n".join([
            _extract_function(app_src, "sanitize"),
            _extract_function(app_src, "sanitizeStrong"),
            _extract_function(app_src, "renderToolBlock"),
            _extract_function(app_src, "renderFunctionCard"),
        ])
        import json
        fn = {
            "id": "x", "icon": "⚙", "name": "Тест",
            "crosslinks": [{"type": "entity", "entity_id": "coinkite", "text": "T", "label": "L"}]
        }
        js = render_source + f"""
const fn = {json.dumps(fn)};
console.log(JSON.stringify({{ html: renderFunctionCard(fn) }}));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert "showEntityPopup('coinkite')" in html

    def test_theory_type_crosslink_calls_site_map_go_to(self, app_src):
        render_source = "\n\n".join([
            _extract_function(app_src, "sanitize"),
            _extract_function(app_src, "sanitizeStrong"),
            _extract_function(app_src, "renderToolBlock"),
            _extract_function(app_src, "renderFunctionCard"),
        ])
        import json
        fn = {
            "id": "x", "icon": "⚙", "name": "Тест",
            "crosslinks": [{"type": "theory", "target_tab": "theory", "target_panel": "Панель X", "text": "T", "label": "L"}]
        }
        js = render_source + f"""
const fn = {json.dumps(fn)};
console.log(JSON.stringify({{ html: renderFunctionCard(fn) }}));
"""
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        html = json.loads(result.stdout)["html"]
        assert "siteMapGoTo('theory','Панель X')" in html


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestEntityPopupFunctionRefs:

    def _run_popup(self, app_src: str, entity: dict, functions: list) -> str:
        import json
        popup_source = "\n\n".join([
            _extract_function(app_src, "sanitize"),
            _extract_function(app_src, "showEntityPopup"),
        ])
        js = f"""
{popup_source}
const ENTITIES = [{json.dumps(entity)}];
const BITCOIN_FUNCTIONS = {json.dumps(functions)};
const THEORY_TOPICS = [];
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
console.log(JSON.stringify({{ html: registry['ep-function-refs'].innerHTML }}));
"""
        # 2026-08-02: тот же ARG_MAX-риск, что в test_theory_topic_essay_mount.py -
        # BITCOIN_FUNCTIONS.json растёт (новые crosslinks), полный дамп через
        # node -e рано или поздно упирается в системный лимит длины аргумента.
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as tmp:
            tmp.write(js)
            tmp_path = tmp.name
        try:
            result = subprocess.run(["node", tmp_path], capture_output=True, text=True, timeout=10)
        finally:
            os.unlink(tmp_path)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        return json.loads(result.stdout)["html"]

    def test_function_ref_renders_clickable_badge_with_looked_up_name(self, app_src):
        entity = {"id": "e1", "name": "E1", "type": "infrastructure", "status": "active", "summary": "S",
                   "function_refs": ["fn1"]}
        functions = [{"id": "fn1", "name": "Функция Один"}]
        html = self._run_popup(app_src, entity, functions)
        assert "goToPanelFromPopup('tech','Функция Один')" in html
        assert "Функция Один" in html

    def test_no_function_refs_renders_empty(self, app_src):
        entity = {"id": "e1", "name": "E1", "type": "infrastructure", "status": "active", "summary": "S"}
        html = self._run_popup(app_src, entity, [])
        assert html == ""

    def test_real_coinkite_entity_has_working_function_ref(self, app_src):
        """Регрессия на реальные данные - конкретный кейс, ради которого всё строилось."""
        import json
        entities = json.loads((REPO_ROOT / "ENTITIES.json").read_text(encoding="utf-8"))["entities"]
        coinkite = next((e for e in entities if e["id"] == "coinkite"), None)
        assert coinkite is not None
        assert "multisig-2of3" in coinkite.get("function_refs", [])

        functions = json.loads((REPO_ROOT / "BITCOIN_FUNCTIONS.json").read_text(encoding="utf-8"))["functions"]
        html = self._run_popup(app_src, coinkite, functions)
        assert "Multisig 2-of-3" in html
        assert "goToPanelFromPopup('tech'," in html


def test_referential_integrity_functions_entities_theory():
    """
    Целостность связей: crosslinks.entity_id существует в ENTITIES.json,
    function_refs существует в BITCOIN_FUNCTIONS.json, theory-crosslink
    target_panel из BITCOIN_FUNCTIONS совпадает с реальным acc-label в
    THEORY_TOPICS.json.
    """
    import json
    bf = json.loads((REPO_ROOT / "BITCOIN_FUNCTIONS.json").read_text(encoding="utf-8"))["functions"]
    entities = json.loads((REPO_ROOT / "ENTITIES.json").read_text(encoding="utf-8"))["entities"]
    topics = json.loads((REPO_ROOT / "THEORY_TOPICS.json").read_text(encoding="utf-8"))["topics"]

    entity_ids = {e["id"] for e in entities}
    function_ids = {f["id"] for f in bf}
    all_item_labels = set()
    for t in topics:
        for it in t.get("items", []):
            all_item_labels.add(it["label"])

    for fn in bf:
        for cl in fn.get("crosslinks", []):
            if cl["type"] == "entity":
                assert cl["entity_id"] in entity_ids, f"{fn['id']}: crosslink на несуществующую сущность {cl['entity_id']}"
            elif cl["type"] == "theory":
                assert cl["target_panel"] in all_item_labels, (
                    f"{fn['id']}: crosslink target_panel '{cl['target_panel']}' не совпадает "
                    f"ни с одним acc-label в THEORY_TOPICS.json"
                )

    for e in entities:
        for fid in e.get("function_refs", []):
            assert fid in function_ids, f"{e['id']}: function_refs ссылается на несуществующую функцию {fid}"
