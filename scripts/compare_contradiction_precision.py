"""
scripts/compare_contradiction_precision.py
Bitcoin Intel — сравнение precision semantic_inverse_score() «до/после» на
фиксированном срезе Golden Dataset (методология из сессии по contradiction
detector, 2026-07-31 — см. docs/PLAN-contradiction-precision-roadmap.md).

ПРОБЛЕМА, КОТОРУЮ РЕШАЕТ: при прототипировании правок detector'а precision
на extended-датасете не всегда падает или растёт из-за самой правки — он
может измениться из-за роста самого датасета между двумя моментами времени
(см. PLAN, §3: extended сам усложняется через периодические батчи). Мерить
"headline precision сейчас vs headline precision вчера" — методологически
неверно. Правильная мера — эффект ОДНОЙ конкретной правки на ОДНОМ и том же
срезе датасета, "до" и "после" неё же, а не тренд во времени. Именно так
сравнивались все три реальные попытки в сессии 2026-07-31 (два отклонённых,
одна принятая) — вручную, разовыми Python-сниппетами. Этот скрипт делает
то же самое воспроизводимо, не полагаясь на память о том, как это делалось.

МЕХАНИЗМ: загружает ДВЕ версии scripts/contradiction_detector.py как отдельные
модули в памяти (git-ref "до" + рабочая копия "после" — или два явных файла),
прогоняет semantic_inverse_score() каждой версии на одном и том же наборе
пар, сравнивает построчно. НЕ трогает файлы на диске, НЕ требует commit
черновика перед оценкой.

Использование (стандартный случай — сравнить черновик в рабочей копии с
последним закоммиченным состоянием):
    python3 scripts/compare_contradiction_precision.py

С явным "до" (сравнить с конкретным коммитом/веткой):
    python3 scripts/compare_contradiction_precision.py --before-ref main~3

Только один датасет (быстрее при итерации):
    python3 scripts/compare_contradiction_precision.py --dataset blocking

Exit code: 1, если ЕСТЬ регресс на blocking-датасете (жёсткое правило —
ноль регресса на 73 обязателен, см. ADR-009/012). Регресс на extended —
предупреждение, не блокирует (extended не enforced, см. ADR-012 заметка
2026-07-31) — но засчитывается в счётчик "N=3 отклонённых попытки" из
PLAN, если это НЕ расширение уже принятого механизма (см. ADR-009,
заметка про "уязвимость" 2026-07-31 — не каждая правка, ухудшающая extended
локально, "попытка" в смысле счётчика).
"""
import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DETECTOR_REL_PATH = "scripts/contradiction_detector.py"

DATASETS = {
    "blocking": REPO_ROOT / "tests" / "golden" / "fixtures" / "contradiction_pairs.json",
    "extended": REPO_ROOT / "tests" / "golden" / "fixtures" / "contradiction_pairs_extended.json",
}


def _load_module_from_source(source: str, module_name: str):
    """
    Компилирует и исполняет source как отдельный модуль в памяти, под
    module_name (не 'scripts.contradiction_detector' — иначе конфликт с уже
    импортированной версией). __file__ выставлен на реальный путь
    contradiction_detector.py — модуль сам вычисляет REPO_ROOT через
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))) и добавляет
    его в sys.path для `from config.settings import ...`; без __file__ это
    упадёт с NameError.
    """
    fake_path = REPO_ROOT / DETECTOR_REL_PATH
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(fake_path)
    sys.modules[module_name] = module
    exec(compile(source, str(fake_path), "exec"), module.__dict__)
    return module


def load_from_git_ref(ref: str, module_name: str):
    result = subprocess.run(
        ["git", "show", f"{ref}:{DETECTOR_REL_PATH}"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"'git show {ref}:{DETECTOR_REL_PATH}' failed:\n{result.stderr}"
        )
    return _load_module_from_source(result.stdout, module_name)


def load_from_file(path: Path, module_name: str):
    return _load_module_from_source(path.read_text(encoding="utf-8"), module_name)


def load_pairs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("pairs", [])


def score_pairs(module, pairs: list[dict]) -> dict:
    """{index: (score, predicted_bool)} для каждой пары, той же версией модуля."""
    result = {}
    for i, p in enumerate(pairs):
        score = module.semantic_inverse_score(p["a"], p["b"])
        result[i] = (score, score >= 0.5)
    return result


def compare_on_dataset(before_mod, after_mod, path: Path) -> dict:
    pairs = load_pairs(path)
    before = score_pairs(before_mod, pairs)
    after = score_pairs(after_mod, pairs)

    correct_before = sum(1 for i, p in enumerate(pairs) if before[i][1] == p["expected"])
    correct_after = sum(1 for i, p in enumerate(pairs) if after[i][1] == p["expected"])

    changed = []
    for i, p in enumerate(pairs):
        pred_before, pred_after = before[i][1], after[i][1]
        if pred_before != pred_after:
            was_correct = pred_before == p["expected"]
            is_correct = pred_after == p["expected"]
            verdict = "FIXED" if (is_correct and not was_correct) else (
                "BROKE" if (was_correct and not is_correct) else "CHANGED"
            )
            changed.append({
                "signal_a": p.get("signal_a", "?"),
                "signal_b": p.get("signal_b", "?"),
                "expected": p["expected"],
                "before": round(before[i][0], 3),
                "after": round(after[i][0], 3),
                "verdict": verdict,
            })

    n = len(pairs)
    return {
        "n_pairs": n,
        "precision_before": round(correct_before / n, 3) if n else None,
        "precision_after": round(correct_after / n, 3) if n else None,
        "correct_before": correct_before,
        "correct_after": correct_after,
        "changed": changed,
    }


def _print_dataset_result(name: str, result: dict) -> None:
    n = result["n_pairs"]
    pb, pa = result["precision_before"], result["precision_after"]
    delta = pa - pb
    arrow = "→" if delta == 0 else ("↑" if delta > 0 else "↓")
    print(
        f"\n  {name} ({n} пар): {pb:.1%} {arrow} {pa:.1%} "
        f"({result['correct_before']}→{result['correct_after']}/{n}, "
        f"Δ{delta:+.1%})"
    )
    for c in result["changed"]:
        print(
            f"    [{c['verdict']}] {c['signal_a']} vs {c['signal_b']} "
            f"expected={c['expected']} {c['before']}→{c['after']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--before-ref", default="HEAD",
        help="git ref для состояния 'до' (по умолчанию HEAD — последний коммит)",
    )
    parser.add_argument(
        "--after-file", default=str(REPO_ROOT / DETECTOR_REL_PATH),
        help="путь к файлу для состояния 'после' (по умолчанию — рабочая копия)",
    )
    parser.add_argument(
        "--dataset", choices=["blocking", "extended", "both"], default="both",
    )
    args = parser.parse_args()

    before_mod = load_from_git_ref(args.before_ref, "contradiction_detector_before")
    after_mod = load_from_file(Path(args.after_file), "contradiction_detector_after")

    datasets_to_run = DATASETS if args.dataset == "both" else {args.dataset: DATASETS[args.dataset]}

    print(f"Сравнение: {args.before_ref} (до) vs {args.after_file} (после)")

    blocking_regressed = False
    for name, path in datasets_to_run.items():
        if not path.exists():
            print(f"\n  {name}: файл не найден ({path}), пропущено")
            continue
        result = compare_on_dataset(before_mod, after_mod, path)
        _print_dataset_result(name, result)
        if name == "blocking" and result["precision_after"] < result["precision_before"]:
            blocking_regressed = True

    print()
    if blocking_regressed:
        print("✗ РЕГРЕСС на blocking-датасете — жёсткое правило нарушено (ADR-009/012). Не коммитить как есть.")
        return 1

    print("✓ Ноль регресса на blocking. Дальнейшее решение (принять/отклонить) — по числам extended выше.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
