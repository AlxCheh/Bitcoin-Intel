"""
Performance baseline для synthesizer.py (IRP v1 Wave 4 / REM-M09).

DoD §28.2 требует: synthesize(42 signals) < 100ms. Не автоматизировано
до этого файла (docs/IRR_REPORT_v1.md).

Важное уточнение по факту: "42 signals" в §28.2 — это было общее число
сигналов в signals.json на момент написания DoD, использованное как
масштаб для порога, а не инвариант, который нужно поддерживать вручную.
База сигналов растёт (на момент написания этого теста — 49 сигналов,
проверьте `len(signals.json['signals'])` для актуального числа) — тест
меряет РЕАЛЬНЫЕ данные на момент запуска, а не фиксированную синтетическую
выборку из 42 записей. Это точнее отражает продакшн-нагрузку и не ломается
каждый раз при добавлении нового сигнала (что произошло бы с захардкоженным
числом — ровно тот тип document-vs-reality дрейфа, который IRP исправляет
по всему проекту).

Не в основной CI — маркер `perf` зарегистрирован в pyproject.toml.
Запуск: `pytest -m perf` или еженедельный scheduled workflow
(.github/workflows/performance.yml).
"""
import json
import time
from collections import defaultdict
from pathlib import Path

import pytest

from domain.exceptions import EmptyClusterError
from scripts.synthesizer import synthesize_cluster

PERF_THRESHOLD_SECONDS = 0.100  # 100ms, DoD §28.2

# tests/conftest.py::isolated_environment — autouse-фикстура, которая делает
# monkeypatch.chdir(tmp_path) для КАЖДОГО теста и подкладывает фейковый
# signals.json ("[]") в песочницу. Этому тесту нужны РЕАЛЬНЫЕ данные проекта
# (иначе нечего мерить), поэтому путь резолвится от Path(__file__), а не от
# cwd-relative config.settings.SIGNALS_PATH — см. предупреждение в самом
# conftest.py и эталонный пример в tests/golden/test_golden.py.
REAL_SIGNALS_PATH = Path(__file__).resolve().parents[2] / "signals.json"


def _load_signals_by_cluster() -> dict[str, list[dict]]:
    with open(REAL_SIGNALS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for s in data["signals"]:
        by_cluster[s["cluster"]].append(s)
    return dict(by_cluster)


@pytest.mark.perf
def test_synthesize_cluster_under_100ms_per_cluster():
    """
    synthesize_cluster() на каждом реальном кластере из signals.json
    укладывается в 100ms по отдельности (DoD §28.2).
    """
    by_cluster = _load_signals_by_cluster()
    assert by_cluster, "signals.json пуст или сигналы без поля cluster"

    timings: dict[str, float] = {}
    for cluster_key, signals in by_cluster.items():
        start = time.perf_counter()
        try:
            synthesize_cluster(cluster_key, signals)
        except EmptyClusterError:
            # Все сигналы кластера старше WINDOW_DAYS_DEFAULT (90 дней) —
            # ожидаемое поведение для старых кластеров, не ошибка
            # производительности. Пропускаем замер для этого кластера.
            continue
        timings[cluster_key] = time.perf_counter() - start

    assert timings, (
        "Ни один кластер не дал результат synthesize_cluster() — "
        "либо все сигналы старше WINDOW_DAYS_DEFAULT, либо тест сломан"
    )

    failures = [
        f"{k}: {v*1000:.1f}ms на {len(by_cluster[k])} сигналах"
        for k, v in timings.items()
        if v >= PERF_THRESHOLD_SECONDS
    ]
    assert not failures, (
        f"Кластеры превысили порог {PERF_THRESHOLD_SECONDS*1000:.0f}ms (DoD §28.2): "
        + "; ".join(failures)
    )


@pytest.mark.perf
def test_synthesize_all_clusters_total_under_threshold():
    """
    Суммарное время synthesize_cluster() по ВСЕМ кластерам сразу —
    прокси для вычислительной части полного прогона synthesizer.py::main()
    (без файловых I/O операций записи в synthesis_store/synthesis_cache).

    Один и тот же порог 100ms применяется к сумме, а не только к каждому
    кластеру по отдельности: main() в реальности вызывает
    synthesize_cluster() последовательно для каждого кластера, поэтому
    суммарное время — то, что реально влияет на длительность CI/cron джобы,
    которая строит synthesis_cache.json.
    """
    by_cluster = _load_signals_by_cluster()

    ran_any = False
    start = time.perf_counter()
    for cluster_key, signals in by_cluster.items():
        try:
            synthesize_cluster(cluster_key, signals)
            ran_any = True
        except EmptyClusterError:
            continue
    elapsed = time.perf_counter() - start

    assert ran_any, "Ни один кластер не дал результат — нечего измерять"
    assert elapsed < PERF_THRESHOLD_SECONDS, (
        f"Суммарный synthesize_cluster() по {len(by_cluster)} кластерам занял "
        f"{elapsed*1000:.1f}ms — порог {PERF_THRESHOLD_SECONDS*1000:.0f}ms (DoD §28.2)"
    )
