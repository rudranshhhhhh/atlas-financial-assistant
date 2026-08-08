# Atlas — Telegram AI Financial Assistant

A conversational financial assistant on Telegram. No slash commands, no buttons —
just natural language, like texting an analyst who remembers you.

## Why it's built this way

Every message goes to the AI. The AI decides what to do (look up a stock,
search news, answer from memory, ask a clarifying question) using tools.
There is no `/price` or `/news` command anywhere. This is "tool calling" /
"function calling": you give the LLM a list of Python functions it's allowed
to call, describe what each does, and it decides when to call them based on
the conversation.

## Project structure

```
atlas-bot/
├── bot.py            # Telegram entrypoint — routes text/voice/document messages
├── ai_engine.py       # Talks to Groq, owns the system prompt + tool-calling loop
├── tools.py           # The actual functions the AI can call (stock price, news, etc.)
├── memory.py          # SQLite: user profiles, conversation history, watchlists
├── scheduler.py        # Daily proactive briefing (stub, not wired in yet)
├── requirements.txt
├── .env.example        # Copy to .env and fill in your keys
└── finance_assistant.db  # Created automatically on first run
```

## Setup (do this first)

1. Get a Telegram bot token from **@BotFather** on Telegram (`/newbot`)
2. Get a free Groq API key at https://console.groq.com
3. `cp .env.example .env` and paste both keys in
4. `pip install -r requirements.txt`
5. `python bot.py`

Message your bot on Telegram. It should respond conversationally right away.

## What's implemented

- ✅ Text message handling, routed entirely through the AI (no commands)
- ✅ Tool calling: stock price + company overview (yfinance), news search (Google News RSS)
- ✅ Technical analysis: 50-day MA, RSI, support/resistance — always framed as informational
- ✅ Watchlist management (add/remove/list) through natural conversation
- ✅ SQLite memory: user profile, full conversation history, watchlist
- 🔲 Conversational onboarding — stub in `bot.py::handle_text`, not wired up yet
- 🔲 Voice message transcription (Groq Whisper) — `tools.transcribe_voice` exists, `bot.py` handler is a stub
- 🔲 PDF upload + Q&A — `tools.extract_pdf_text` exists, `bot.py` handler is a stub
- 🔲 Daily scheduled briefing — `scheduler.py` exists but isn't started from `bot.py` yet

## Next steps

1. Wire up onboarding in `bot.py::handle_text`.
2. Wire up voice notes (`handle_voice` → `tools.transcribe_voice` → `ai_engine.handle_turn`).
3. Wire up PDF Q&A (`handle_document` → `tools.extract_pdf_text` → feed as context).
4. Start `scheduler.run_daily_briefings` from `bot.py::main()` on a cron trigger.
5. Personalization: periodically extract durable facts from conversations via `memory.save_fact()`.

Don't build all of these before testing anything — get text chat solid first,
talk to your bot for real, then layer on.

## Deploying it

Once it works locally, you have a few easy options to keep it running 24/7:

- **Railway / Render / Fly.io** — push this repo, set `TELEGRAM_BOT_TOKEN` and
  `GROQ_API_KEY` as environment variables, set the start command to `python bot.py`.
  All three have free tiers.
- **A cheap VPS** (DigitalOcean, Hetzner) — clone the repo, install deps, then
  run it under `systemd` or `screen`/`tmux` so it survives disconnects.
- **Docker** — wrap it in a container if you want the same setup to run
  anywhere; a `Dockerfile` isn't included yet but it's a small addition
  (`python:3.11-slim` base, `pip install -r requirements.txt`, `CMD ["python", "bot.py"]`).

Whichever you pick, the bot uses long-polling (`app.run_polling()`), so no
public URL or webhook is required — it just needs outbound internet access.
