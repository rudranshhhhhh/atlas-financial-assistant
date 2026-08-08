"""
scheduler.py — proactive daily briefing (NOT wired up yet).

Idea: once a day, for each user with a non-empty watchlist, check whether
anything is actually worth surfacing (a big price move, fresh news) before
sending anything. Silence is the default; only interrupt when it's earned.

To wire this in:
  1. In bot.py::main(), after building `app`, create an AsyncIOScheduler,
     add_job(run_daily_briefings, args=[app.bot], trigger="cron", hour=8),
     and .start() it before app.run_polling().
  2. Fill in `is_worth_surfacing()` with real thresholds (e.g. >3% move,
     or a fresh headline since the last briefing).
"""

import asyncio

import memory
import tools


def is_worth_surfacing(ticker: str) -> tuple[bool, str]:
    """Decide if a ticker has moved enough / has fresh news to justify a ping."""
    price = tools.get_stock_price(ticker)
    if "error" in price:
        return False, ""

    if abs(price.get("day_change_pct", 0)) >= 3:
        direction = "up" if price["day_change_pct"] > 0 else "down"
        return True, f"{ticker} is {direction} {abs(price['day_change_pct'])}% today."

    return False, ""


async def run_daily_briefings(bot):
    for user_id in memory.get_all_user_ids():
        watchlist = memory.get_watchlist(user_id)
        if not watchlist:
            continue

        highlights = []
        for ticker in watchlist:
            worth_it, note = is_worth_surfacing(ticker)
            if worth_it:
                highlights.append(note)

        if not highlights:
            continue  # nothing worth interrupting the user for today

        message = "Morning briefing:\n" + "\n".join(highlights)
        try:
            await bot.send_message(chat_id=user_id, text=message)
        except Exception:
            pass  # user may have blocked the bot, etc.


if __name__ == "__main__":
    # Quick manual test without Telegram — just prints what it would send
    async def _demo():
        for uid in memory.get_all_user_ids():
            for ticker in memory.get_watchlist(uid):
                print(is_worth_surfacing(ticker))

    asyncio.run(_demo())
