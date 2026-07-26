"""Управление Telegram webhook (PRD FR-TG-1, ADR-0012).

Использование (после деплоя на Vercel):
    python scripts/telegram_webhook.py set https://<app>.vercel.app/api/telegram
    python scripts/telegram_webhook.py info
    python scripts/telegram_webhook.py delete

Токен и секрет берутся из окружения/.env; в лог не выводятся.
"""

from __future__ import annotations

import sys

import httpx

sys.path.insert(0, "src")

from fourcaster.platform.config import telegram_token, telegram_webhook_secret  # noqa: E402

API = "https://api.telegram.org/bot{token}/{method}"


def _call(method: str, **params) -> dict:
    url = API.format(token=telegram_token(), method=method)
    resp = httpx.post(url, json=params, timeout=30)
    return resp.json()


def cmd_set(webhook_url: str) -> dict:
    params: dict = {
        "url": webhook_url,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True,
    }
    secret = telegram_webhook_secret()
    if secret:
        params["secret_token"] = secret
    return _call("setWebhook", **params)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "set":
        if len(argv) < 2:
            print("Укажите URL: set https://.../api/telegram")
            return 2
        print(cmd_set(argv[1]))
    elif cmd == "info":
        print(_call("getWebhookInfo"))
    elif cmd == "delete":
        print(_call("deleteWebhook", drop_pending_updates=True))
    else:
        print(f"Неизвестная команда: {cmd}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
