"""
scripts/validate_integrity.py
Bitcoin Intel — проверка целостности всех критических файлов.

Проверяет:
  1. signals.json — валидный JSON, уникальные ID, обязательные поля
  2. ENTITIES.json — валидный JSON
  3. synthesis_cache.json — валидный JSON, все кластеры имеют tension
  4. SHA-256 checksums — сравнение с manifest.json если существует (DA05)

Exit codes:
  0 — всё в порядке
  1 — найдены ошибки
"""

import json
import sys
import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    """SHA-256 контрольная сумма файла."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate() -> bool:
    errors   = []
    warnings = []

    # ── signals.json ─────────────────────────────────────────────────────────
    signals_path = Path("signals.json")
    signal_ids: set = set()  # используется ниже в M6 (referential integrity)
    try:
        raw     = json.loads(signals_path.read_text(encoding="utf-8"))
        signals = raw.get("signals", raw) if isinstance(raw, dict) else raw

        if not isinstance(signals, list):
            errors.append("signals.json: root must be array or {signals: []}")
        else:
            ids = [s.get("id") for s in signals if s.get("id")]
            signal_ids = set(ids)
            dupes = [i for i in ids if ids.count(i) > 1]
            if dupes:
                errors.append(f"signals.json: duplicate IDs: {set(dupes)}")

            required = ["id", "date", "signal", "cluster", "narrative_role",
                        "tension", "macro_implication"]
            for s in signals:
                for field in required:
                    if not s.get(field):
                        warnings.append(
                            f"signals.json: signal {s.get('id','?')} "
                            f"missing '{field}'"
                        )

            chk = sha256_file(signals_path)
            print(f"✓ signals.json: {len(signals)} signals | "
                  f"{len(set(ids))} unique IDs | sha256: {chk[:16]}…")

    except Exception as e:
        errors.append(f"signals.json: {e}")

    # ── ENTITIES.json ─────────────────────────────────────────────────────────
    entities_path = Path("ENTITIES.json")
    entity_signal_refs: list[tuple[str, str]] = []  # (entity_id, signal_ref) для M6
    try:
        entities_raw = json.loads(entities_path.read_text(encoding="utf-8"))
        # ENTITIES.json — {meta, entities: [...]} (DOC: docs/API.md)
        entities = entities_raw.get("entities", entities_raw) if isinstance(entities_raw, dict) else entities_raw
        chk = sha256_file(entities_path)
        print(f"✓ ENTITIES.json: {len(entities)} entities | sha256: {chk[:16]}…")

        for e in entities:
            for ref in e.get("signal_refs", []) or []:
                entity_signal_refs.append((e.get("id", "?"), ref))

    except Exception as e:
        errors.append(f"ENTITIES.json: {e}")
        entities = []

    # ── M6 (ARR v3): Referential Integrity ENTITIES.json.signal_refs ─────────
    # Раньше проверялась только целостность relationships.json (orphan from_id/
    # to_id, см. validate_relationships.py) — signal_refs внутри ENTITIES.json
    # не проверялись вообще. Если сигнал удалён или его id переименован, а
    # signal_refs не обновлён — ENTITIES.json молча ссылается в никуда, и это
    # не заметно ни в одном существующем чеке.
    if signal_ids and entity_signal_refs:
        orphan_refs = [
            (entity_id, ref) for entity_id, ref in entity_signal_refs
            if ref not in signal_ids
        ]
        if orphan_refs:
            errors.append(
                "ENTITIES.json: orphan signal_refs (ссылка на несуществующий "
                "signal id): " + ", ".join(f"{e}→{r}" for e, r in orphan_refs)
            )
        else:
            print(
                f"✓ ENTITIES.json.signal_refs: {len(entity_signal_refs)} ссылок, "
                f"все валидны"
            )

    # ── synthesis_cache.json ──────────────────────────────────────────────────
    cache_path = Path("data/synthesis_cache.json")
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            no_tension = [k for k, v in cache.items() if not v.get("tension")]
            if no_tension:
                warnings.append(
                    f"synthesis_cache.json: clusters without tension: {no_tension}"
                )
            chk = sha256_file(cache_path)
            print(f"✓ synthesis_cache.json: {len(cache)} clusters | "
                  f"sha256: {chk[:16]}…")
        except Exception as e:
            errors.append(f"synthesis_cache.json: {e}")
    else:
        warnings.append("synthesis_cache.json: не существует — запустить synthesizer.py")

    # ── Manifest checksum verification (DA05) ────────────────────────────────
    manifest_path = Path("data/integrity_manifest.json")
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            print("\nПроверка manifest checksums:")
            for file_path, expected_sha in manifest.items():
                p = Path(file_path)
                if not p.exists():
                    warnings.append(f"Manifest: {file_path} не существует")
                    continue
                actual = sha256_file(p)
                if actual == expected_sha:
                    print(f"  ✓ {file_path}")
                else:
                    errors.append(
                        f"Manifest checksum MISMATCH: {file_path}\n"
                        f"  expected: {expected_sha[:16]}…\n"
                        f"  actual:   {actual[:16]}…"
                    )
        except Exception as e:
            warnings.append(f"Manifest: {e}")

    # ── Результат ────────────────────────────────────────────────────────────
    if warnings:
        print(f"\n⚠  {len(warnings)} предупреждений:")
        for w in warnings:
            print(f"   - {w}")

    if errors:
        print(f"\n⛔ {len(errors)} ошибок:")
        for e in errors:
            print(f"   - {e}")
        return False

    print("\n✓ Все проверки целостности пройдены")
    return True


def update_manifest() -> None:
    """Обновить manifest checksums для критических файлов."""
    files_to_track = [
        "signals.json",
        "ENTITIES.json",
    ]
    manifest = {}
    for f in files_to_track:
        p = Path(f)
        if p.exists():
            manifest[f] = sha256_file(p)

    Path("data").mkdir(exist_ok=True)
    Path("data/integrity_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print("✓ integrity_manifest.json обновлён")
    for f, chk in manifest.items():
        print(f"  {f}: {chk[:16]}…")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--update-manifest":
        update_manifest()
    else:
        ok = validate()
        sys.exit(0 if ok else 1)
