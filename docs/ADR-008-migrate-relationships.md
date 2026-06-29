# ADR-008: Миграция links.* → relationships.json

**Статус:** Принято  
**Дата:** 2026-06-29  
**Авторы:** Команда Bitcoin Intel

## Контекст

Исторически связи между сигналами хранились inline в `signals.json`
в поле `links: {confirms, contradicts, context_chain}`.
По мере роста базы (44+ сигналов) это создаёт проблемы:
- связи нельзя ретрактовать без изменения сигнала
- нет audit trail для изменения связей
- cross-signal querying требует полного скана

## Решение

Вынести связи в отдельный файл `data/relationships.json`
(append-only, каждая связь — отдельный объект с `id`, `status`, `rationale`).

## Переходный период (Фазы)

| Фаза | Условие | Поведение системы |
|------|---------|-------------------|
| A (текущая) | `LEGACY_LINKS_ENABLED = True` | Читать из `signals[*].links` |
| B | `relationships.json` создан | Читать из обоих, приоритет `relationships.json` |
| C | После `migrate_relationships.py --apply` | Читать только из `relationships.json` |

## Rollback

При любой фазе: установить `LEGACY_LINKS_ENABLED = True` в `config/settings.py`
→ система вернётся к чтению из `signals[*].links`.

## Последствия

- `scripts/migrate_relationships.py` — реализован, dry-run безопасен
- `scripts/validate_relationships.py` — проверяет целостность после миграции
- Старые `links.*` поля остаются в `signals.json` до Фазы C
