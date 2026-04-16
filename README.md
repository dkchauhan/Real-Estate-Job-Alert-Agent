# Real Estate Job Alert Agent

Monitors Upwork, Freelancer (and notes Fiverr limitations) for real estate / IDX jobs every 60 minutes. Filters results with Claude AI, then sends alerts via Email and Telegram.

---

## Files

```
job_alert_agent/
├── agent.py          ← main script (run this)
├── config.py         ← all your settings (edit this first)
├── requirements.txt  ← Python dependencies
├── agent.log         ← created automatically on first run
└── seen_jobs.db      ← SQLite DB, created automatically (prevents duplicate alerts)
```

---

## Quick Setup (5 steps)

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Get your Anthropic API key

- Go to https://console.anthropic.com/
- Create an account → API Keys → Create Key
- Copy the key (starts with `sk-ant-…`)

### 3. Set up Gmail App Password (for email alerts)

1. Enable 2-Factor Authentication on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Create a new App Password → copy the 16-character password

### 4. Set up Telegram Bot (for Telegram alerts)

1. Open Telegram → search for **@BotFather**
2. Send `/newbot` → follow prompts → copy your **bot token**
3. Search for **@userinfobot** or **@getidsbot** → start it → copy your **chat ID**
4. Start your bot once by searching its name and pressing Start

### 5. Edit config.py

Fill in your actual values:

```python
"anthropic_api_key": "sk-ant-...",

"email": {
    "username":  "you@gmail.com",
    "password":  "xxxx xxxx xxxx xxxx",   # 16-char App Password
    "sender":    "you@gmail.com",
    "recipient": "you@gmail.com",
},

"telegram": {
    "bot_token": "123456789:ABCdef...",
    "chat_id":   "987654321",
},
```

---

## Run the agent

```bash
python agent.py
```

It will:
1. Scan immediately on startup
2. Re-scan every 60 minutes automatically
3. Log everything to `agent.log` and your terminal

---

## Run 24/7 (free options)

### Option A — Always-on PC / VPS (recommended)

```bash
# Keep running in background with nohup
nohup python agent.py > agent.log 2>&1 &
```

### Option B — Railway.app (free tier)

1. Create account at https://railway.app
2. New Project → Deploy from GitHub repo
3. Add environment variables in Railway dashboard:
   - `ANTHROPIC_API_KEY`
   - `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_RECIPIENT`
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
4. Done — runs 24/7 for free

### Option C — Linux systemd service

Create `/etc/systemd/system/job-alert.service`:

```ini
[Unit]
Description=Real Estate Job Alert Agent
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/agent.py
WorkingDirectory=/path/to/job_alert_agent
Restart=always
Environment=ANTHROPIC_API_KEY=sk-ant-...
Environment=EMAIL_USERNAME=you@gmail.com
Environment=EMAIL_PASSWORD=your_app_password
Environment=EMAIL_RECIPIENT=you@gmail.com
Environment=TELEGRAM_BOT_TOKEN=your_token
Environment=TELEGRAM_CHAT_ID=your_id

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable job-alert
sudo systemctl start job-alert
sudo systemctl status job-alert
```

---

## Tuning the AI filter

In `config.py`, adjust `"min_score"`:

| Value | Effect |
|-------|--------|
| `5`   | Moderate — catches most real estate jobs |
| `6`   | Balanced (default) |
| `7`   | Strict — only strong matches |
| `8`   | Very strict — near-perfect matches only |

---

## About Fiverr

Fiverr does **not** have a public RSS feed for buyer requests. The agent logs this on each run. Options:
- Check https://www.fiverr.com/buyer_requests manually while logged in
- Apply for the Fiverr Partner API at https://www.fiverr.com/partnerships

---

## Sample Telegram message

```
🏠 New Real Estate Job (Upwork)

Real Estate Website with IDX Integration

Score: ★★★★★★★★☆☆ 8/10
Needs IDX broker integration for a real estate site

Need a developer to build a WordPress real estate 
website with full IDX Broker integration, property 
search, and MLS listings...

[View & Apply →]
```

---

## Troubleshooting

**No jobs found**: Upwork RSS can sometimes be rate-limited. Try running again in a few minutes.

**Email not sending**: Make sure you're using an App Password (not your regular Gmail password) and that 2FA is enabled.

**Telegram not working**: Make sure you've sent at least one message to your bot (press Start) before running the agent.

**All jobs filtered out**: Lower `min_score` in config.py to 5.
