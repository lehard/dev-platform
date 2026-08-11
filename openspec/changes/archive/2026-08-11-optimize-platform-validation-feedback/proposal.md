# Optimize platform validation feedback

## Why

Платформенная задача с небольшой целевой правкой потребовала около 34 минут end-to-end. Последняя полная локальная проверка сама по себе заняла 457 секунд для 323 тестов, тогда как required CI test phase заняла около 48 секунд. Нельзя интерпретировать это как разрешение ослабить CI: разница включает локальную конкуренцию и вывод, а предыдущий compatibility regression был найден именно полной регрессией.

Нужна измеримая, безопасная двухскоростная модель: быстрый локальный feedback по доказанно затронутым проверкам и неизменный полный authoritative gate перед merge protected-main PR. До изменения поведения должны появиться тайминги и диагностика; возможное распараллеливание допустимо только после аудита изоляции тестовых ресурсов.

## What Changes

- Добавить измерение длительности и quiet-by-default вывод проверок с полным полезным контекстом при ошибке.
- Формализовать отдельные режимы выбора `local affected` и `protected full`.
- Сохранить fail-closed fallback: неизвестные и высокорисковые изменения требуют полного набора.
- Исследовать и при подтверждённой изоляции внедрить partitioning с устойчивым aggregate required check, ориентируясь на проверенные паттерны Jara_Fin.
- Добавить benchmark и контрактные тесты, подтверждающие, что оптимизация не ослабляет безопасность публикации.

## Impact

- Affected specs: `platform-lifecycle`.
- Likely implementation: check selector, finish/check runner, CI workflow, tests and engineering guidance.
- No change to protected-main authority: successful local subset never authorizes publication alone.
