"""
config.py — Edit this file before running the agent.
All sensitive values can also be set as environment variables (recommended).
"""

import os

CONFIG = {
    # ── Anthropic ─────────────────────────────────────────────────────────────
    # Get your key at https://console.anthropic.com/
    "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", "sk-ant-YOUR_KEY_HERE"),

    # ── Job search settings ───────────────────────────────────────────────────
    "keywords": [
        "real estate website design",
        "IDX broker integration",
        "Showcase IDX",
        "IDX integration",
        "MLS integration",
        "real estate website",
        "ihomefinder",
        "idxbroker"
    ],

    # Platforms to monitor: "upwork", "fiverr", "freelancer"
    # Note: Fiverr has no public RSS — the agent logs a note for it.
    "platforms": ["upwork", "fiverr"],

    # How often to check (minutes)
    "interval_minutes": 120,

    # Minimum AI relevance score (0-10) to trigger a notification
    # 5 = moderate match, 7 = strict, 8+ = only very close matches
    "min_score": 6,

    # ── Email (Gmail example) ─────────────────────────────────────────────────
    "email": {
        "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", "465")),
        # For Gmail: enable 2FA then create an App Password at
        # https://myaccount.google.com/apppasswords
        "username": os.getenv("EMAIL_USERNAME", "your_gmail@gmail.com"),
        "password": os.getenv("EMAIL_PASSWORD", "your_app_password_here"),
        "sender":   os.getenv("EMAIL_SENDER",   "your_gmail@gmail.com"),
        "recipient": os.getenv("EMAIL_RECIPIENT", "your_gmail@gmail.com"),
    },

    # ── Telegram ──────────────────────────────────────────────────────────────
    # 1. Message @BotFather on Telegram → /newbot → copy the token
    # 2. Message @userinfobot to get your chat_id (or use @getidsbot)
    "telegram": {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "8639789332:AAHcu7BaLmIKMuXYnPF4X6HXdtluOX9cCbA"),
        "chat_id":   os.getenv("TELEGRAM_CHAT_ID",   "7468181176"),
    },
}
