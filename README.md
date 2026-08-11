# Infinite — Giveaway Voting Bot

A multi-hoster Telegram giveaway voting bot built with Pyrogram + MongoDB.

## Features

- Any user can become a **hoster** and run their own giveaway (1 active at a time)
- Force-subscribe required to participate AND to vote
- 1 user = 1 vote total per giveaway (self-voting allowed)
- Auto-generated participation posts in the channel with live vote counts
- Hoster can manually boost votes with `/incr`
- Giveaway auto-ends at the set time (IST) and posts a Top 10 result automatically
- Silent owner super-admin access via `/access` and `/exit`

## Commands

| Command | Who | Description |
|---|---|---|
| `/start` | Everyone | Welcome message |
| `/help` | Everyone | Command list |
| `/host` | Everyone | Start hosting a new giveaway |
| `/incr <participant_id> <count>` | Hoster | Manually boost a participant's votes |
| `/end` | Hoster | End your giveaway early |
| `/access <giveaway_id>` | Owner only | Silently take hoster control of any giveaway |
| `/exit` | Owner only | Leave the access session |

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
├── main.py              # Entry point
├── config.py             # Environment variables
├── database.py            # MongoDB collections & queries
├── helpers.py             # Force-sub check, IST time utils
├── scheduler.py           # Auto-end giveaways + result announcement
├── web.py                 # Health-check server for Render
├── plugins/
│   ├── start.py           # /start, /help
│   ├── router.py          # Routes free-text to the right conversation flow
│   ├── host.py             # /host flow (channel add, timing setup)
│   ├── participate.py     # Participation flow + post generation
│   ├── vote.py             # Voting logic
│   ├── hoster_commands.py # /incr, /end
│   └── owner.py            # /access, /exit (silent super-admin)
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Notes

- Vote counts are stored per-participant; the `votes` collection enforces the
  "1 user = 1 vote per giveaway" rule via a unique lookup on `(giveaway_id, voter_id)`.
- Conversation state (host setup steps, participate caption step) is kept in-memory.
  This is fine for a single bot instance; if you ever scale to multiple instances,
  move this state into MongoDB too.
- If a participant's Telegram profile photo is private, the post is sent as a
  text-only message (no photo) instead of failing.
