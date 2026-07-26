"""ChangeDetection (core domain, PRD §10.9).

Сравнивает новый консенсус с предыдущим прогоном и выделяет значимые
изменения — кандидатов на уведомление (принцип P3: триггер — переход
через порог, влияющий на решение, а не любая дельта).
"""

from fourcaster.modules.changedetection.detect import Change, detect_changes

__all__ = ["Change", "detect_changes"]
