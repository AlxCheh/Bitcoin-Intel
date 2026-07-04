"""
domain/events.py
Bitcoin Intel — доменные события (Domain Events)

Реализует audit trail: каждое значимое действие в системе
испускает событие которое записывается в data/events.jsonl.

Принцип: append-only. События не изменяются и не удаляются.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import EVENTS_LOG_PATH, ENCODING, JSON_ENSURE_ASCII, DATE_FORMAT


# ─── Базовый класс события ────────────────────────────────────────────────────
@dataclass
class DomainEvent:
    """Базовый класс для всех доменных событий."""
    event_type:  str
    occurred_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Версия схемы — для будущей миграции событий
    schema_version: str = "1.0"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_jsonl(self) -> str:
        """Одна строка JSONL (без переноса строки внутри)."""
        return json.dumps(self.to_dict(), ensure_ascii=JSON_ENSURE_ASCII)


# ─── Пять типов событий ───────────────────────────────────────────────────────

@dataclass
class SignalAdded(DomainEvent):
    """
    Сигнал добавлен в signals.json.
    Испускается в: scripts/add_signal.py
    """
    event_type:  str = "SignalAdded"
    signal_id:   str = ""
    cluster:     str = ""
    theme:       str = ""
    dir:         str = ""
    narrative_role: str = ""
    source:      str = ""
    added_by:    str = "analyst"


@dataclass
class SynthesisApproved(DomainEvent):
    """
    Аналитик одобрил синтез кластера.
    Испускается в: scripts/approve_synthesis.py

    `rationale` добавлен 2026-06-30 (C3 ARR v3): scripts/approve_synthesis.py
    всегда передавал rationale в конструктор, но поле отсутствовало в
    dataclass — это бросало TypeError при КАЖДОМ вызове approve(), сразу
    после успешного прохождения state machine (см. CHANGELOG / коммит фикса).
    Без теста на approve_synthesis.py это не было обнаружено.
    """
    event_type:      str = "SynthesisApproved"
    synthesis_id:    str = ""
    cluster:         str = ""
    tension:         str = ""
    strength:        str = ""
    confidence:      float = 0.0
    rationale:       str = ""
    approved_by:     str = "analyst"
    previous_synthesis_id: Optional[str] = None


@dataclass
class RelationshipRetracted(DomainEvent):
    """
    Связь между сигналами ретрактирована.
    Ранее: «Испускается в infrastructure/relationship_store.py» — этот файл удалён
    (ADR-016, нигде не использовался). Событие пока нигде не эмиттируется в реальном
    пайплайне (см. domain/lifecycle.py::on_relationship_retracted — вызывающих нет);
    остаётся как корректно специфицированная, но не подключённая возможность.
    """
    event_type:    str = "RelationshipRetracted"
    relationship_id: str = ""
    from_id:       str = ""
    to_id:         str = ""
    rel_type:      str = ""
    reason:        str = ""
    retracted_by:  str = "analyst"


@dataclass
class ClusterScoreChanged(DomainEvent):
    """
    Score кластера изменился значительно (delta >= порога).
    Испускается в: scripts/synthesizer.py после пересчёта.
    """
    event_type:    str = "ClusterScoreChanged"
    cluster:       str = ""
    score_before:  int = 0
    score_after:   int = 0
    delta:         int = 0
    phase_before:  str = ""
    phase_after:   str = ""
    trigger_signal_id: str = ""   # сигнал который вызвал изменение

    @property
    def is_significant(self) -> bool:
        """Изменение >= 5 баллов считается значимым."""
        return abs(self.delta) >= 5


@dataclass
class SynthesisExpired(DomainEvent):
    """
    Синтез устарел: все сигналы кластера вышли за WINDOW_DAYS.
    Испускается в: scripts/synthesizer.py при обнаружении пустого кластера.
    """
    event_type:   str = "SynthesisExpired"
    cluster:      str = ""
    synthesis_id: str = ""
    last_signal_date: str = ""
    expired_after_days: int = 0


@dataclass
class SynthesisStoreCleaned(DomainEvent):
    """
    Файл синтеза удалён из synthesis_store/ по retention policy (M1 ARR v3).
    Испускается в: scripts/cleanup_synthesis_store.py, ДО физического
    удаления файла — Audit Trail не должен лгать о состоянии файловой
    системы, поэтому событие пишется первым (fail loud, если запись не
    удалась — файл остаётся на диске).
    """
    event_type:      str = "SynthesisStoreCleaned"
    synthesis_id:    str = ""
    cluster:         str = ""
    status:          str = ""
    age_days:        int = 0
    retention_days:  int = 0


# ─── EventLog ────────────────────────────────────────────────────────────────
class EventLog:
    """
    Append-only лог доменных событий в формате JSONL.

    Каждая строка = одно событие в JSON.
    Файл никогда не перезаписывается — только дополняется.

    Использование:
        log = EventLog()
        log.emit(SignalAdded(signal_id="STR-2026-0628-001", cluster="strategy_model_stress", ...))
    """

    def __init__(self, path: str = EVENTS_LOG_PATH):
        self._path = path

    def emit(self, event: DomainEvent) -> None:
        """
        Записывает событие в JSONL файл.
        Атомарность обеспечивается file_lock (infrastructure/file_lock.py).
        При отсутствии директории — создаёт её.
        """
        os.makedirs(os.path.dirname(self._path) if os.path.dirname(self._path) else ".", exist_ok=True)
        with open(self._path, "a", encoding=ENCODING) as f:
            f.write(event.to_jsonl() + "\n")

    def read_all(self) -> list[dict]:
        """Читает все события из JSONL файла."""
        if not os.path.exists(self._path):
            return []
        events = []
        with open(self._path, encoding=ENCODING) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass  # повреждённая строка — пропускаем, не падаем
        return events

    def read_by_type(self, event_type: str) -> list[dict]:
        """Фильтрует события по типу."""
        return [e for e in self.read_all() if e.get("event_type") == event_type]

    def read_for_cluster(self, cluster: str) -> list[dict]:
        """Все события связанные с кластером."""
        return [e for e in self.read_all() if e.get("cluster") == cluster]

    def tail(self, n: int = 20) -> list[dict]:
        """Последние N событий."""
        return self.read_all()[-n:]

    def stats(self) -> dict:
        """Статистика по типам событий."""
        events = self.read_all()
        counts: dict[str, int] = {}
        for e in events:
            t = e.get("event_type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return {
            "total": len(events),
            "by_type": counts,
            "log_path": self._path,
            "exists": os.path.exists(self._path),
        }
