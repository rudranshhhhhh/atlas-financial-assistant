"""
ai_engine.py — owns the system prompt and the tool-calling loop.

Every inbound message, regardless of intent, comes through `handle_turn()`.
There is no command router. The model decides whether to answer directly or
call one of the functions in tools.py, and the loop below just keeps feeding
tool results back to the model until it produces a final text reply.
"""

import json
import os

from groq import Groq

import memory
import tools

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """You are Atlas, a financial assistant that talks like a sharp,
approachable analyst texting a client — not a bot reading from a menu.

Rules:
- Never mention "commands". The user should never need to know a command exists.
- Use tools whenever a question needs live data (price, news, technicals). Don't
  guess numbers from memory.
- When you present technical analysis, always frame it as an informational read,
  never as a trade signal or financial advice. You are not a licensed advisor.
- Keep replies conversational and concise — this is a chat app, not a report.
  Use short paragraphs, not headers or bullet walls, unless the user asks for
  a structured breakdown.
- If the user mentions an upcoming meeting or call with a company, proactively
  offer to pull together a quick briefing (price + overview + recent news)
  rather than waiting to be asked.
- If you don't have enough info to help (e.g. an ambiguous ticker), ask a
  short clarifying question instead of guessing.
"""

# Maps tool names to the actual Python functions in tools.py
TOOL_FUNCTIONS = {
    "get_stock_price": lambda args, user_id: tools.get_stock_price(args["ticker"]),
    "get_company_overview": lambda args, user_id: tools.get_company_overview(args["ticker"]),
    "search_news": lambda args, user_id: tools.search_news(
        args["query"], args.get("max_items", 5)
    ),
    "get_technical_analysis": lambda args, user_id: tools.get_technical_analysis(args["ticker"]),
    "add_ticker_to_watchlist": lambda args, user_id: tools.add_ticker_to_watchlist(
        user_id, args["ticker"]
    ),
    "remove_ticker_from_watchlist": lambda args, user_id: tools.remove_ticker_from_watchlist(
        user_id, args["ticker"]
    ),
    "get_user_watchlist": lambda args, user_id: tools.get_user_watchlist(user_id),
}


def handle_turn(user_id: int, user_message: str, max_tool_hops: int = 4) -> str:
    """
    Runs one full turn: adds the user's message to history, calls the model,
    executes any tool calls it requests, and loops until it returns plain text.
    Returns the assistant's final reply (also persisted to history).
    """
    memory.add_message(user_id, "user", user_message)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += memory.get_recent_messages(user_id, limit=20)

    for _ in range(max_tool_hops):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools.TOOL_SPECS,
            tool_choice="auto",
        )
        choice = response.choices[0].message

        if not choice.tool_calls:
            reply = choice.content or "Sorry, I didn't catch that — could you rephrase?"
            memory.add_message(user_id, "assistant", reply)
            return reply

        # Model wants to call one or more tools — execute each, feed results back
        messages.append(
            {
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [tc.model_dump() for tc in choice.tool_calls],
            }
        )

        for tc in choice.tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            fn = TOOL_FUNCTIONS.get(fn_name)
            result = fn(args, user_id) if fn else {"error": f"Unknown tool: {fn_name}"}

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                }
            )

    # Hit the hop limit without a final answer — fail gracefully
    fallback = "I ran into trouble pulling that together — mind trying again?"
    memory.add_message(user_id, "assistant", fallback)
    return fallback
