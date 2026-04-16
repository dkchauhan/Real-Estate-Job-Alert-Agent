"""
Real Estate Job Alert Agent
Monitors Upwork, Fiverr, and Freelancer for real estate / IDX jobs.
Filters with Claude AI, notifies via Email and Telegram.
"""

import os
import json
import time
import hashlib
import logging
import smtplib
import sqlite3
import schedule
import requests
import feedparser
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai  # Add this
from config import CONFIG

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler("agent.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Gemini client ──────────────────────────────────────────────────────────
genai.configure(api_key=CONFIG["gemini_api_key"])
model = genai.GenerativeModel('gemini-1.5-flash')

# ── Database (tracks already-seen jobs so we never double-notify) ─────────────
DB_PATH = "seen_jobs.db"


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS seen_jobs (
               job_id   TEXT PRIMARY KEY,
               title    TEXT,
               platform TEXT,
               seen_at  TEXT
           )"""
    )
    con.commit()
    con.close()


def is_seen(job_id: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT 1 FROM seen_jobs WHERE job_id=?", (job_id,)).fetchone()
    con.close()
    return row is not None


def mark_seen(job_id: str, title: str, platform: str):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT OR IGNORE INTO seen_jobs VALUES (?,?,?,?)",
        (job_id, title, platform, datetime.utcnow().isoformat()),
    )
    con.commit()
    con.close()


# ── Feed helpers ──────────────────────────────────────────────────────────────

def _job_id(platform: str, url: str, title: str) -> str:
    """Stable unique ID for a job posting."""
    raw = f"{platform}|{url or title}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def fetch_upwork(keywords: list[str]) -> list[dict]:
    """Upwork public RSS – one feed per keyword query."""
    jobs = []
    for kw in keywords:
        url = f"https://www.upwork.com/ab/feed/jobs/rss?q={requests.utils.quote(kw)}&sort=recency"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                jobs.append(
                    {
                        "platform": "Upwork",
                        "title": entry.get("title", ""),
                        "description": entry.get("summary", ""),
                        "url": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "id": _job_id("upwork", entry.get("link", ""), entry.get("title", "")),
                    }
                )
            log.info("Upwork '%s' → %d results", kw, len(feed.entries))
        except Exception as exc:
            log.warning("Upwork fetch failed for '%s': %s", kw, exc)
    return jobs


def fetch_freelancer(keywords: list[str]) -> list[dict]:
    """Freelancer public RSS search feed."""
    jobs = []
    for kw in keywords:
        url = f"https://www.freelancer.com/rss/search.php?query={requests.utils.quote(kw)}"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                jobs.append(
                    {
                        "platform": "Freelancer",
                        "title": entry.get("title", ""),
                        "description": entry.get("summary", ""),
                        "url": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "id": _job_id("freelancer", entry.get("link", ""), entry.get("title", "")),
                    }
                )
            log.info("Freelancer '%s' → %d results", kw, len(feed.entries))
        except Exception as exc:
            log.warning("Freelancer fetch failed for '%s': %s", kw, exc)
    return jobs


def fetch_fiverr(keywords: list[str]) -> list[dict]:
    """
    Fiverr does not expose a public jobs/buyer-requests RSS feed.
    We simulate by returning an empty list and logging a helpful note.
    To monitor Fiverr buyer requests you need to log in manually or
    use their Partner API (requires approval).
    """
    log.info(
        "Fiverr: no public RSS feed available for buyer requests. "
        "Consider checking https://www.fiverr.com/buyer_requests manually "
        "or applying for Fiverr Partner API access."
    )
    return []


# ── Claude AI relevance filter ────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a job relevance classifier for a freelance developer 
who specialises in real estate websites, IDX broker integration, Showcase IDX, 
MLS integration, WordPress real estate themes, and property search portals.

Given a job posting (title + description), respond ONLY with valid JSON:
{
  "relevant": true | false,
  "score": 0-10,
  "reason": "one short sentence"
}

Mark relevant=true only when the job clearly involves:
- Real estate website design or development
- IDX (Internet Data Exchange) integration of any kind
- MLS (Multiple Listing Service) integration
- Showcase IDX, IDX Broker, iHomefinder, or similar IDX plugins
- WordPress real estate themes (AgentPress, Easy Agent Pro, etc.)
- Property listing portals or search tools

Score 8-10 = perfect match, 5-7 = likely match, 1-4 = tangential, 0 = unrelated."""

def ai_filter(job):
    """Uses Gemini 1.5 Flash to score job relevance."""
    prompt = f"""
    You are a job filter. Score this job from 0-10 based on relevance to these keywords: {', '.join(CONFIG['keywords'])}.
    Respond ONLY in JSON format: {{"score": 8, "reason": "short explanation"}}
    
    Job Title: {job['title']}
    Description: {job['description'][:500]}
    """
    try:
        response = model.generate_content(prompt)
        # Clean the response text to ensure it's valid JSON
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(res_text)
        
        if data.get('score', 0) >= CONFIG['min_score']:
            job['ai_score'] = data.get('score', 0)
            job['ai_reason'] = data.get('reason', "No reason provided")
            return job
    except Exception as e:
        log.warning(f"Gemini error: {e}")
    return None


# ── Notifications ─────────────────────────────────────────────────────────────

def send_email(jobs: list[dict]):
    """Send a batch email for all new matching jobs."""
    if not jobs:
        return
    cfg = CONFIG["email"]

    subject = f"[Job Alert] {len(jobs)} new real estate job(s) found – {datetime.now().strftime('%d %b %Y %H:%M')}"

    # Build HTML body
    rows = ""
    for j in jobs:
        score_color = "#2d7a2d" if j["ai_score"] >= 8 else "#8a6000"
        rows += f"""
        <tr>
          <td style="padding:14px 0;border-bottom:1px solid #eee;">
            <a href="{j['url']}" style="font-size:15px;font-weight:600;color:#1a1a1a;text-decoration:none;">
              {j['title']}
            </a><br>
            <span style="font-size:12px;color:#666;">
              {j['platform']} &nbsp;·&nbsp; {j.get('published','')[:25]}
            </span><br>
            <span style="font-size:12px;color:{score_color};font-weight:600;">
              AI Score: {j['ai_score']}/10 — {j['ai_reason']}
            </span><br>
            <span style="font-size:13px;color:#444;margin-top:4px;display:block;">
              {j['description'][:300].strip()}...
            </span><br>
            <a href="{j['url']}" style="display:inline-block;margin-top:8px;padding:6px 16px;
               background:#0066cc;color:#fff;border-radius:5px;font-size:13px;
               text-decoration:none;">View & Apply →</a>
          </td>
        </tr>"""

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#1a1a1a;">
      <div style="background:#0066cc;padding:20px 24px;border-radius:8px 8px 0 0;">
        <h1 style="color:#fff;font-size:18px;margin:0;">Real Estate Job Alert</h1>
        <p style="color:#cce0ff;font-size:13px;margin:6px 0 0;">{len(jobs)} new matching job(s) found</p>
      </div>
      <div style="padding:0 24px;background:#fafafa;border:1px solid #eee;border-top:none;border-radius:0 0 8px 8px;">
        <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        <p style="font-size:11px;color:#999;margin-top:16px;padding-bottom:16px;">
          Sent by your Job Alert Agent · Checking every {CONFIG['interval_minutes']} minutes
        </p>
      </div>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["sender"]
    msg["To"] = cfg["recipient"]
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"]) as server:
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["sender"], cfg["recipient"], msg.as_string())
        log.info("Email sent: %d jobs to %s", len(jobs), cfg["recipient"])
    except Exception as exc:
        log.error("Email failed: %s", exc)


def send_telegram(jobs: list[dict]):
    """Send one Telegram message per job (keeps messages short and actionable)."""
    cfg = CONFIG["telegram"]
    if not cfg.get("bot_token") or not cfg.get("chat_id"):
        return

    for j in jobs:
        stars = "★" * j["ai_score"] + "☆" * (10 - j["ai_score"])
        text = (
            f"🏠 *New Real Estate Job* ({j['platform']})\n\n"
            f"*{j['title']}*\n\n"
            f"Score: {stars} {j['ai_score']}/10\n"
            f"_{j['ai_reason']}_\n\n"
            f"{j['description'][:250].strip()}...\n\n"
            f"[View & Apply →]({j['url']})"
        )
        payload = {
            "chat_id": cfg["chat_id"],
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage",
                json=payload,
                timeout=10,
            )
            r.raise_for_status()
            log.info("Telegram sent for: %s", j["title"])
        except Exception as exc:
            log.error("Telegram failed: %s", exc)
        time.sleep(0.5)  # avoid Telegram rate limit


# ── Core run loop ─────────────────────────────────────────────────────────────

def run_once():
    log.info("=" * 60)
    log.info("Starting job scan at %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    keywords = CONFIG["keywords"]
    all_jobs: list[dict] = []

    if "upwork" in CONFIG["platforms"]:
        all_jobs.extend(fetch_upwork(keywords))
    if "fiverr" in CONFIG["platforms"]:
        all_jobs.extend(fetch_fiverr(keywords))
    if "freelancer" in CONFIG["platforms"]:
        all_jobs.extend(fetch_freelancer(keywords))

    log.info("Total raw jobs fetched: %d", len(all_jobs))

    # Deduplicate within this batch
    seen_ids: set[str] = set()
    unique_jobs = []
    for j in all_jobs:
        if j["id"] not in seen_ids:
            seen_ids.add(j["id"])
            unique_jobs.append(j)

    # Filter out jobs we've already notified about
    new_jobs = [j for j in unique_jobs if not is_seen(j["id"])]
    log.info("New (unseen) jobs: %d", len(new_jobs))

    # AI relevance filter
    matched: list[dict] = []
    for j in new_jobs:
        result = ai_filter(j)
        if result:
            matched.append(result)
            log.info("  MATCH  [%d/10] %s — %s", result["ai_score"], result["platform"], result["title"])
        else:
            log.debug("  skip   %s — %s", j["platform"], j["title"])

    # Persist all new jobs as seen (even filtered ones) so we don't recheck them
    for j in new_jobs:
        mark_seen(j["id"], j["title"], j["platform"])

    log.info("Matched jobs to notify: %d", len(matched))

    if matched:
        # Sort best score first
        matched.sort(key=lambda x: x["ai_score"], reverse=True)
        send_email(matched)
        send_telegram(matched)

    log.info("Scan complete. Next scan in %d minutes.", CONFIG["interval_minutes"])


def main():
    log.info("Real Estate Job Alert Agent starting up…")
    init_db()
    run_once()  # run immediately on start
    schedule.every(CONFIG["interval_minutes"]).minutes.do(run_once)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
