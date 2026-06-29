"""
domain/validator.py
Bitcoin Intel — валидация сигналов и синтезов.

Функции:
  validate_signal(signal)                      — валидация сигнала (FAIL LOUD)
  check_possible_duplicate(signal, existing)   — предупреждение о дубликате
  validate_rationale_quality(rationale, synth) — качество rationale (AI09)
"""

import re
from datetime import datetime

from domain.exceptions import (
    ValidationError,
    InvalidSignalIdError,
    MissingRequiredFieldError,
)
from infrastructure.logger import get_logger

logger = get_logger("validator")

# ─── Константы ───────────────────────────────────────────────────────────────
REQUIRED_FIELDS = [
    "id", "date", "cat", "catLabel", "dir", "horizon",
    "theme", "weight", "actor", "flow", "signal",
    "narrative_role", "cluster", "tension", "macro_implication",
]

VALID_DIR     = {"pos", "neg", "neu"}
VALID_HORIZON = {"short", "mid", "long"}
VALID_WEIGHT  = {"onchain", "primary", "market", "media"}
VALID_ROLE    = {"trigger", "complication", "resolution", "background"}
VALID_CAT     = {"onchain", "ta", "macro", "mining", "narrative", "layer2", "ownership"}
VALID_ACTOR   = {"etf", "corporate", "government", "defi", "retail", "miner"}
VALID_FLOW    = {"inflow", "outflow", "internal", "neutral"}

TENSION_MARKERS  = ["vs", "несмотря на", "при условии", "вопреки", " — "]
DATE_FORMAT      = "%Y-%m-%d"
ID_PATTERN       = re.compile(r"^[A-Z]{2,5}-\d{4}-\d{4}-\d{3}$")
MACRO_MIN_LEN    = 50
DUPLICATE_FIELDS = ["date", "actor", "cluster"]


# ─── Валидация сигнала ───────────────────────────────────────────────────────

def validate_signal(signal: dict) -> None:
    """
    Валидирует сигнал. FAIL LOUD — бросает исключения при нарушении инварианта.

    Raises:
        MissingRequiredFieldError — отсутствует обязательное поле
        InvalidSignalIdError      — неверный формат ID
        ValidationError           — прочие нарушения
    """
    sid = signal.get("id", "")

    # Обязательные поля
    for field in REQUIRED_FIELDS:
        if not signal.get(field):
            raise MissingRequiredFieldError(field, sid)

    # Формат ID
    if not ID_PATTERN.match(sid):
        raise InvalidSignalIdError(sid)

    # Enum значения
    for field, value, valid_set in [
        ("dir",            signal.get("dir"),            VALID_DIR),
        ("horizon",        signal.get("horizon"),        VALID_HORIZON),
        ("weight",         signal.get("weight"),         VALID_WEIGHT),
        ("narrative_role", signal.get("narrative_role"), VALID_ROLE),
        ("cat",            signal.get("cat"),            VALID_CAT),
        ("actor",          signal.get("actor"),          VALID_ACTOR),
        ("flow",           signal.get("flow"),           VALID_FLOW),
    ]:
        if value and value not in valid_set:
            raise ValidationError(field, value, f"must be one of {sorted(valid_set)}")

    # Формат даты
    try:
        datetime.strptime(signal.get("date", ""), DATE_FORMAT)
    except ValueError:
        raise ValidationError("date", signal.get("date"), "must be YYYY-MM-DD")

    # Tension — заглавная буква
    tension = signal.get("tension", "")
    if tension and not tension[0].isupper():
        raise ValidationError("tension", tension[:40],
                               "must start with capital letter (CLAUDE.md rule)")

    # macro_implication — минимальная длина
    macro = signal.get("macro_implication", "")
    if macro and len(macro) < MACRO_MIN_LEN:
        raise ValidationError("macro_implication", macro,
                               f"too short ({len(macro)} chars) — describe structural change, not event")

    logger.debug(f"Signal {sid} passed validation")


def check_possible_duplicate(signal: dict, existing: list) -> str | None:
    """
    Предупреждение о похожем сигнале. Не блокирует добавление.
    Возвращает warning string или None.
    """
    for s in existing:
        if all(signal.get(f) == s.get(f) for f in DUPLICATE_FIELDS):
            return (
                f"Possible duplicate of {s['id']}: "
                f"same {', '.join(DUPLICATE_FIELDS)}. "
                f"Intentional? Ensure different source."
            )
    return None


# ─── Валидация качества rationale (AI09) ─────────────────────────────────────

def validate_rationale_quality(rationale: str, synthesis: dict) -> list[str]:
    """
    Проверяет качество rationale синтеза (AI09).
    Возвращает список предупреждений — не блокирует утверждение.

    Критерии:
      1. Не пустой если synthesis approved
      2. Длина > 50 символов (слишком короткий = бессодержательный)
      3. Упоминает хотя бы один signal ID из signals_used
      4. Не идентичен tension (разные поля — разные смыслы)
      5. Содержит обоснование выбора anchor-сигнала
    """
    warnings = []

    if not rationale or not rationale.strip():
        if synthesis.get("status") == "approved":
            warnings.append(
                "Rationale is empty for approved synthesis — "
                "explain why this tension/anchor was chosen"
            )
        return warnings

    # Критерий 2: длина
    if len(rationale) < 50:
        warnings.append(
            f"Rationale too short ({len(rationale)} chars) — "
            f"add context about anchor selection and confidence"
        )

    # Критерий 3: упоминает signal ID
    signals_used = synthesis.get("signals_used", [])
    if signals_used:
        mentions_signal = any(sid in rationale for sid in signals_used)
        if not mentions_signal:
            warnings.append(
                "Rationale doesn't reference any signal ID — "
                "mention specific signals to justify the choice "
                f"(used: {signals_used[:3]}{'...' if len(signals_used)>3 else ''})"
            )

    # Критерий 4: не идентичен tension
    tension = synthesis.get("tension", "")
    if tension and rationale.strip() == tension.strip():
        warnings.append(
            "Rationale is identical to tension — "
            "rationale should explain WHY this tension was chosen, not repeat it"
        )

    # Критерий 5: содержит обоснование выбора
    justification_keywords = [
        "anchor", "contradicts", "weight", "confidence",
        "потому что", "because", "выбран", "score"
    ]
    has_justification = any(kw in rationale.lower() for kw in justification_keywords)
    if not has_justification:
        warnings.append(
            "Rationale lacks justification keywords (anchor, contradicts, weight, score) — "
            "explain what drove the synthesis decision"
        )

    return warnings
