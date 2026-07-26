"""Notification (delivery, PRD §11.3).

В serverless-раскладке (ADR-0013) роль worker-notify выполняет финальный
шаг cron-джоба: после расчёта он рассылает алерты подписчикам.
"""

from fourcaster.modules.notification.alerts import format_alert, send_alerts

__all__ = ["format_alert", "send_alerts"]
