"""Форматирование и доставка алертов об изменении прогноза (US-HIST-3).

Сообщение действенно: «было → стало» для конкретных дат, вывод о том,
ухудшился прогноз или улучшился.
"""

from __future__ import annotations

from datetime import date

import httpx

from fourcaster.modules.changedetection import Change
from fourcaster.modules.hazard.rain import HIL_LEVELS

_API = "https://api.telegram.org/bot{token}/sendMessage"


def _fmt_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day:02d}.{d.month:02d}"


def _side(hil: int, p50: float, pop: float) -> str:
    lv = HIL_LEVELS[hil]
    return f"{lv.icon} {lv.label} {p50:g} мм · {round(pop * 100)}%"


def format_alert(location_name: str, changes: list[Change]) -> str:
    worse = any(c.worse for c in changes)
    head = "⚠️ Прогноз ухудшился" if worse else "🔀 Прогноз изменился"
    lines = [f"{head} · <b>{location_name}</b>", ""]
    for c in changes:
        lines.append(f"<b>{_fmt_date(c.valid_date)}</b>")
        lines.append(f"  было:  {_side(c.was_hil, c.was_p50, c.was_pop)}")
        lines.append(f"  стало: {_side(c.now_hil, c.now_p50, c.now_pop)}")
    lines.append("")
    lines.append("💡 Прогноз на эти даты сдвинулся — стоит пересмотреть план."
                 if worse else "Изменение зафиксировано; критичного ухудшения нет.")
    return "\n".join(lines)


def send_alerts(
    *, token: str, chat_ids: list[int], location_name: str, changes: list[Change]
) -> int:
    """Рассылает алерт списку чатов. Возвращает число успешных отправок."""
    if not chat_ids or not changes:
        return 0
    text = format_alert(location_name, changes)
    sent = 0
    with httpx.Client(timeout=30) as client:
        for chat_id in chat_ids:
            try:
                r = client.post(
                    _API.format(token=token),
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                )
                if r.json().get("ok"):
                    sent += 1
            except Exception:  # noqa: BLE001 — один плохой чат не роняет рассылку
                continue
    return sent
