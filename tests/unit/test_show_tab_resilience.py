"""
tests/unit/test_show_tab_resilience.py
Bitcoin Intel — тест на устойчивость showTab()/restoreLastActiveTab() к
исключению внутри triggerTabData() (2026-08-01).

КОНТЕКСТ: restoreLastActiveTab() восстанавливает последнюю активную вкладку
из localStorage СИНХРОННО при загрузке страницы — раньше, чем async fetch()
успевает наполнить данные (SIGNALS/THEORY_TOPICS/... — см. Promise.all() в
loadSignals()). Если рендер данных внутри triggerTabData() бросает исключение
(гонка — данные ещё пустые массивы), до этой правки currentTabId откатывался
на 'home', а видимый DOM (.active класс) оставался на сломанной вкладке —
рассинхрон, из-за которого более поздний триггер triggerTabData(currentTabId)
(после loadSignals()) чинил не ту вкладку, которую реально видел пользователь.
Уже дважды случалось для конкретных переменных (chartsInited, PRESET_SIGNALS_LIST,
см. комментарий в коде) — это системная защита, не точечная.

Извлекает реальный исходник из js/app-main.js (паттерн test_uncertainty_indicator.py).
"""
import shutil
from pathlib import Path

import pytest
from tests.conftest import extract_js_function, run_node_js

REPO_ROOT = Path(__file__).parent.parent.parent
APP_MAIN_JS = REPO_ROOT / "js" / "app-main.js"
NODE_AVAILABLE = shutil.which("node") is not None




@pytest.fixture(scope="module")
def show_tab_source() -> str:
    src = APP_MAIN_JS.read_text(encoding="utf-8")
    return extract_js_function(src, "showTab")


# Минимальный мок DOM — только то, что реально использует showTab():
# getElementById, querySelectorAll('.section'|'.cbar-btn'), classList.
_DOM_MOCK = """
function makeElement(id, tag) {
  const classes = new Set();
  return {
    id: id, _tag: tag,
    classList: {
      add: function(c) { classes.add(c); },
      remove: function(c) { classes.delete(c); },
      contains: function(c) { return classes.has(c); }
    }
  };
}

const REGISTRY = {};
function registerElement(id, tag) {
  REGISTRY[id] = makeElement(id, tag);
  return REGISTRY[id];
}

const document = {
  getElementById: function(id) { return REGISTRY[id] || null; },
  querySelectorAll: function(selector) {
    const tag = selector.replace('.', '');
    const matches = Object.values(REGISTRY).filter(function(el) { return el._tag === tag; });
    matches.forEach = Array.prototype.forEach.bind(matches);
    return matches;
  }
};

// Заранее регистрируем нужные элементы (как в реальном index.html)
registerElement('tab-home', 'section');
registerElement('tab-theory', 'section');
registerElement('cbar-live', 'cbar-btn');
registerElement('cbar-macro', 'cbar-btn');

// Зависимости showTab(), которых нет в этом изолированном тесте —
// минимальные заглушки, фиксирующие факт вызова, не полноценная логика
let currentTabId = null;
let activeCluster = 'live';
const CLUSTERS = { live: { tabs: [['home','ОБЗОР']] }, macro: { tabs: [['theory','ТЕОРИЯ']] } };
const TAB_TO_CLUSTER = { home: 'live', theory: 'macro' };
let renderSubnavCalls = [];
function renderSubnav(key, activeId) { renderSubnavCalls.push([key, activeId]); }
function updateCrumb(id) {}
const localStorage = { _store: {}, setItem: function(k, v) { this._store[k] = v; } };
"""


@pytest.mark.skipif(not NODE_AVAILABLE, reason="Node.js не найден в PATH")
class TestShowTabResilience:

    def test_triggerTabData_exception_does_not_leave_currentTabId_out_of_sync(self, show_tab_source):
        """
        Главный кейс находки: triggerTabData() бросает (симулирует гонку с
        ещё не пришедшими данными) — currentTabId и видимый DOM обязаны
        остаться СОГЛАСОВАНЫ на 'theory', не расходиться на 'home'/'theory'.
        """
        js = _DOM_MOCK + """
function triggerTabData(id) {
  if (id === 'theory') { throw new Error('THEORY_TOPICS ещё пуст — гонка с async fetch'); }
}
""" + show_tab_source + """
let threw = false;
try {
  showTab('theory', null);
} catch (e) {
  threw = true;
}
console.log(JSON.stringify({
  threw: threw,
  currentTabId: currentTabId,
  themeTabActive: document.getElementById('tab-theory').classList.contains('active'),
  homeTabActive: document.getElementById('tab-home').classList.contains('active'),
  localStorageSaved: localStorage._store['bi_active_tab']
}));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        import json
        out = json.loads(result.stdout)

        # Исключение НЕ должно вылетать из showTab() наружу
        assert out["threw"] is False, "showTab() должна поглощать исключение triggerTabData(), не пробрасывать его"
        # currentTabId обязан совпадать с реально показанной (активной) вкладкой
        assert out["currentTabId"] == "theory"
        assert out["themeTabActive"] is True
        assert out["homeTabActive"] is False
        # localStorage всё равно должен сохранить намерение пользователя —
        # данные не загрузились, но сам факт "я на вкладке theory" — сохранён
        assert out["localStorageSaved"] == "theory"

    def test_no_exception_path_unaffected(self, show_tab_source):
        """Обычный путь (triggerTabData не падает) — поведение не изменилось."""
        js = _DOM_MOCK + """
let triggerCalledWith = null;
function triggerTabData(id) { triggerCalledWith = id; }
""" + show_tab_source + """
showTab('theory', null);
console.log(JSON.stringify({
  currentTabId: currentTabId,
  triggerCalledWith: triggerCalledWith,
  themeTabActive: document.getElementById('tab-theory').classList.contains('active')
}));
"""
        result = run_node_js(js)
        assert result.returncode == 0, f"Node failed:\n{result.stderr}"
        import json
        out = json.loads(result.stdout)
        assert out["currentTabId"] == "theory"
        assert out["triggerCalledWith"] == "theory"
        assert out["themeTabActive"] is True
