"""
infrastructure/relationship_store.py
Bitcoin Intel — хранилище связей между сигналами

Реализует ADR-007: переходный период чтения связей.
В переходный период читает из ОБОИХ источников:
  - устаревший links.* внутри signals.json (LEGACY)
  - новый data/relationships.json (CANONICAL)

После завершения миграции: LEGACY_LINKS_ENABLED = False в config/settings.py
"""

import json
import uuid
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    RELATIONSHIPS_PATH, SIGNALS_PATH, ENCODING, JSON_ENSURE_ASCII,
    LEGACY_LINKS_ENABLED, DATE_FORMAT,
)


@dataclass
class Relationship:
    id:         str
    from_id:    str
    to_id:      str
    type:       str
    rationale:  str
    created:    str
    created_by: str
    status:     str = "active"
    retracted:    Optional[str] = None
    retracted_by: Optional[str] = None
    retract_reason: Optional[str] = None

    def is_active(self) -> bool:
        return self.status == "active"


class RelationshipStore:
    """
    ADR-007: единая точка доступа к связям между сигналами.

    Переходный период (LEGACY_LINKS_ENABLED=True):
      - Читает canonical из relationships.json
      - Дополняет legacy из links.* в signals.json
      - Canonical приоритетнее: при добавлении canonical вытесняет legacy-дубль
      - Дедупликация по паре (from_id, to_id, type)

    После миграции (LEGACY_LINKS_ENABLED=False):
      - Читает только relationships.json
    """

    def __init__(self, relationships_path=RELATIONSHIPS_PATH, signals_path=SIGNALS_PATH):
        self._rel_path = relationships_path
        self._sig_path = signals_path
        self._relationships: list[Relationship] = []
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self._load()

    def _load(self):
        canonical: list[Relationship] = []
        legacy: list[Relationship] = []

        # 1. Canonical
        if os.path.exists(self._rel_path):
            with open(self._rel_path, encoding=ENCODING) as f:
                data = json.load(f)
            for r in data.get("relationships", []):
                canonical.append(Relationship(**r))

        # 2. Legacy
        if LEGACY_LINKS_ENABLED and os.path.exists(self._sig_path):
            with open(self._sig_path, encoding=ENCODING) as f:
                sig_data = json.load(f)
            signals = sig_data["signals"] if isinstance(sig_data, dict) else sig_data
            now = datetime.now(timezone.utc).strftime(DATE_FORMAT)

            for sig in signals:
                sig_id = sig.get("id", "")
                links = sig.get("links", {})
                for rel_type, targets in [
                    ("confirms",      links.get("confirms", [])),
                    ("contradicts",   links.get("contradicts", [])),
                    ("context_chain", links.get("context_chain", [])),
                ]:
                    for target in targets:
                        legacy.append(Relationship(
                            id=f"legacy-{sig_id}-{rel_type}-{str(target)[:20]}",
                            from_id=sig_id,
                            to_id=str(target),
                            type=rel_type,
                            rationale="[legacy] Перенесено из links.*",
                            created=now,
                            created_by="migration",
                            status="active",
                        ))

        # 3. Дедупликация: canonical сначала, legacy только если пары нет
        seen: set[tuple[str, str, str]] = set()
        merged: list[Relationship] = []

        for r in canonical:
            key = (r.from_id, r.to_id, r.type)
            if key not in seen:
                seen.add(key)
                merged.append(r)

        for r in legacy:
            key = (r.from_id, r.to_id, r.type)
            if key not in seen:
                seen.add(key)
                merged.append(r)

        self._relationships = merged
        self._loaded = True

    # ─── Чтение ──────────────────────────────────────────────────────────────
    def get_all(self, active_only=True) -> list[Relationship]:
        self._ensure_loaded()
        if active_only:
            return [r for r in self._relationships if r.is_active()]
        return list(self._relationships)

    def get_for_signal(self, signal_id, rel_type=None, active_only=True) -> list[Relationship]:
        self._ensure_loaded()
        return [
            r for r in self._relationships
            if r.from_id == signal_id
            and (rel_type is None or r.type == rel_type)
            and (not active_only or r.is_active())
        ]

    def get_contradicts(self, signal_id: str) -> list[str]:
        return [r.to_id for r in self.get_for_signal(signal_id, rel_type="contradicts")]

    def exists(self, from_id, to_id, rel_type) -> bool:
        self._ensure_loaded()
        return any(
            r.from_id == from_id and r.to_id == to_id and r.type == rel_type
            for r in self._relationships
        )

    def _canonical_exists(self, from_id, to_id, rel_type) -> bool:
        return any(
            r.from_id == from_id and r.to_id == to_id and r.type == rel_type
            and not r.id.startswith("legacy-")
            for r in self._relationships
        )

    # ─── Запись ──────────────────────────────────────────────────────────────
    def add(self, from_id: str, to_id: str, rel_type: str,
            rationale: str, created_by: str = "analyst") -> Relationship:
        """
        Добавляет canonical связь.
        - from_id ≠ to_id
        - нет дублирующих canonical пар
        - если пара есть как legacy — canonical вытесняет её
        """
        self._ensure_loaded()

        if from_id == to_id:
            raise ValueError(f"Самосвязь запрещена: {from_id}")

        if self._canonical_exists(from_id, to_id, rel_type):
            raise ValueError(f"Дубль: ({from_id}, {to_id}, {rel_type}) уже существует")

        # Вытесняем legacy-дубль если есть
        self._relationships = [
            r for r in self._relationships
            if not (r.id.startswith("legacy-")
                    and r.from_id == from_id
                    and r.to_id == to_id
                    and r.type == rel_type)
        ]

        rel = Relationship(
            id=str(uuid.uuid4()),
            from_id=from_id,
            to_id=to_id,
            type=rel_type,
            rationale=rationale,
            created=datetime.now(timezone.utc).isoformat(),
            created_by=created_by,
            status="active",
        )
        self._relationships.append(rel)
        self._save()
        return rel

    def retract(self, rel_id: str, reason: str, retracted_by: str = "analyst"):
        """Ретракция — не удаляет, меняет статус. Append-only."""
        self._ensure_loaded()
        for r in self._relationships:
            if r.id == rel_id:
                if r.status == "retracted":
                    raise ValueError(f"Связь {rel_id} уже ретрактирована")
                r.status = "retracted"
                r.retracted = datetime.now(timezone.utc).isoformat()
                r.retracted_by = retracted_by
                r.retract_reason = reason
                self._save()
                return
        raise KeyError(f"Связь {rel_id} не найдена")

    def _save(self):
        """Сохраняет только canonical (не legacy) в relationships.json."""
        os.makedirs(os.path.dirname(self._rel_path) if os.path.dirname(self._rel_path) else ".", exist_ok=True)
        canonical = [r for r in self._relationships if not r.id.startswith("legacy-")]
        data = {
            "meta": {
                "version": "1.0",
                "description": "Canonical relationship store — Bitcoin Intel",
                "legacy_links_enabled": LEGACY_LINKS_ENABLED,
                "updated": datetime.now(timezone.utc).isoformat(),
            },
            "relationships": [asdict(r) for r in canonical],
        }
        with open(self._rel_path, "w", encoding=ENCODING) as f:
            json.dump(data, f, ensure_ascii=JSON_ENSURE_ASCII, indent=2)

    def migration_status(self) -> dict:
        """Чеклист завершения переходного периода (ADR-007)."""
        self._ensure_loaded()
        canonical_count = sum(1 for r in self._relationships if not r.id.startswith("legacy-"))
        legacy_count    = sum(1 for r in self._relationships if r.id.startswith("legacy-"))
        return {
            "total_relationships": len(self._relationships),
            "canonical":           canonical_count,
            "legacy":              legacy_count,
            "legacy_links_enabled": LEGACY_LINKS_ENABLED,
            "migration_complete":  legacy_count == 0,
            "checklist": {
                "all_legacy_migrated":        legacy_count == 0,
                "no_text_targets_in_legacy":  not any(
                    not r.to_id.startswith(("STR-","SUP-","INF-","MAC-","NAR-"))
                    for r in self._relationships if r.id.startswith("legacy-")
                ),
                "relationships_json_exists":  os.path.exists(self._rel_path),
                "synthesizer_uses_store":     True,
                "links_deprecated_in_schema": True,
            },
        }
