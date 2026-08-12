# Infinite — Giveaway Voting Bot

A multi-hoster Telegram giveaway voting bot built with Pyrogram + MongoDB.

## Features

- Any user can become a **hoster** and run their own giveaway (1 active at a time)
- Force-subscribe required to participate AND to vote
- 1 user = 1 vote total per giveaway (self-voting allowed), **toggle-able** — click again to un-vote
- Switching your vote directly to another participant is blocked — you must remove it first
- Auto-generated participation posts with a **square-cropped profile photo**, caption (with example prompt)
- Review & confirm step before a giveaway is actually created
- Giveaway auto-ends at the set time (IST) and posts a Top 10 result automatically
- **1-hour-left reminder** posted in the channel before a giveaway ends
- If a voter **leaves the channel**, their vote is automatically removed and a bold announcement is posted
- If the bot is **removed as admin** from a hoster's channel, that giveaway is deleted instantly
- **Auto-cleanup**: 4 days after a giveaway ends, its heavy participant/vote data is deleted (a summary stays forever)
- Hoster gets a **DM with a download button** for the full report before that data is cleaned up
- Hoster can **cancel** a giveaway before anyone has joined
- `/mystats` shows a hoster's giveaway history
- Silent owner super-admin access via `/access` / `/exit`, plus `/current` to see all active giveaways and a
  "View Participants" button after `/access`
- Bot-wide **Admin role** (separate from hosters) with `/stats`, `/ban`, `/unban`, `/startpic`, `/broadcast`
- DM messages use a small-caps stylized look; channel posts use bold headers with normal readable body text

## Commands

| Command | Who | Description |
|---|---|---|
| `/start` | Everyone | Welcome message (with optional custom banner image) |
| `/help` | Everyone | Command list |
| `/host` | Everyone | Start hosting a new giveaway |
| `/incr <participant_id> <count>` | Hoster | Manually boost a participant's votes |
| `/end` | Hoster | End your giveaway early |
| `/cancel` | Hoster | Cancel your giveaway (only before anyone has joined) |
| `/mystats` | Hoster | View your hosting history |
| `/access <giveaway_id>` | Owner only | Silently take hoster control of any giveaway |
| `/exit` | Owner only | Leave the access session |
| `/current` | Owner only | List all currently active giveaways |
| `/addadmin <user_id>` | Owner only | Grant a user admin rights |
| `/removeadmin <user_id>` | Owner only | Revoke admin rights |
| `/stats` | Owner + Admin | Bot-wide usage stats |
| `/ban <user_id>` / `/unban <user_id>` | Owner + Admin | Block/unblock a user from using the bot |
| `/startpic` | Owner + Admin | Set/change the image shown on `/start` |
| `/broadcast` | Owner + Admin | Send a message to every bot user (slow, rate-limit-safe) |

## Setup

1. Copy `.env.example` to `.env` (or set these as environment variables on Render)
2. Fill in:
   - `API_ID` / `API_HASH` — from https://my.telegram.org
   - `BOT_TOKEN` — from @BotFather
   - `BOT_USERNAME` — your bot's username (no @)
   - `MONGO_URI` — MongoDB Atlas connection string
   - `OWNER_ID` — your personal Telegram user ID (get it from @userinfobot)
3. Deploy to Render as a Docker web service (Dockerfile included)
4. Set up an uptime pinger (e.g. cron-job.org) hitting your Render URL `/` every few minutes to keep it alive

## Project Structure

```
infinite-bot/
├── main.py                    # Entry point - starts bot + 3 background loops
├── config.py                  # Environment variables
├── database.py                # MongoDB collections & queries
├── helpers.py                 # Force-sub check, IST time utils, small-caps styling, pfp cropping
├── scheduler.py                # Auto-end, 1-hour reminder, auto-cleanup (4 days) loops
├── web.py                      # Health-check server for Render
├── plugins/
│   ├── start.py                # /start, /help
│   ├── router.py                # Routes free-text/photo messages to the right conversation flow
│   ├── host.py                  # /host flow (channel add, timing, review & confirm)
│   ├── participate.py          # Participation flow + post generation (square pfp, caption example)
│   ├── vote.py                  # Voting logic (toggle vote, switch-block)
│   ├── hoster_commands.py      # /incr, /end, /cancel, /mystats
│   ├── owner.py                 # /access, /exit, /current
│   ├── reports.py               # Download-data button + View Participants button
│   ├── admin.py                 # /addadmin, /removeadmin, /stats, /ban, /unban, /startpic, /broadcast
│   └── chat_member_events.py   # Leave-detection + bot-removed-from-channel detection
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Notes

- Conversation state (host setup steps, participate caption step, admin flows) is kept in-memory.
  This is fine for a single bot instance; if you ever scale to multiple instances,
  move this state into MongoDB too.
- Participant IDs are generated with an atomic MongoDB counter, so concurrent
  participation (many people joining at the exact same moment) can never produce duplicate IDs.
- Square profile-photo cropping requires the `Pillow` package (in requirements.txt). If cropping
  fails for any reason, the bot falls back to sending the original photo instead of crashing.
