"""
tools.py — the actual functions the AI is allowed to call.

Each function here has a matching JSON-schema entry in TOOL_SPECS, which is
what gets sent to Groq so the model knows these exist and how to call them.
Keep functions small, return plain strings/dicts — the model reads whatever
you return and turns it into a natural-language reply.
"""

import io
import feedparser
import yfinance as yf

import memory


# ---------------------------------------------------------------------------
# Stock price
# ---------------------------------------------------------------------------

def get_stock_price(ticker: str) -> dict:
    """Current price + basic info for a ticker."""
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        return {
            "ticker": ticker.upper(),
            "price": round(info.last_price, 2),
            "previous_close": round(info.previous_close, 2),
            "day_change_pct": round(
                (info.last_price - info.previous_close) / info.previous_close * 100, 2
            ),
            "currency": info.currency,
        }
    except Exception as e:
        return {"error": f"Couldn't fetch price for {ticker}: {e}"}


def get_company_overview(ticker: str) -> dict:
    """Short company description + key stats, used for meeting-prep briefings."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "ticker": ticker.upper(),
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "summary": (info.get("longBusinessSummary") or "")[:500],
        }
    except Exception as e:
        return {"error": f"Couldn't fetch overview for {ticker}: {e}"}


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def search_news(query: str, max_items: int = 5) -> list[dict]:
    """Recent headlines related to a query (company, ticker, or topic) via Google News RSS."""
    url = f"https://news.google.com/rss/search?q={query}+when:7d&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            items.append(
                {
                    "title": entry.title,
                    "source": getattr(entry, "source", {}).get("title", ""),
                    "published": entry.published,
                    "link": entry.link,
                }
            )
        return items
    except Exception as e:
        return [{"error": f"News search failed: {e}"}]


# ---------------------------------------------------------------------------
# Technical analysis (informational only, never framed as advice)
# ---------------------------------------------------------------------------

def get_technical_analysis(ticker: str) -> dict:
    """50-day moving average, RSI, and rough support/resistance from recent price history."""
    try:
        hist = yf.Ticker(ticker).history(period="6mo")
        if hist.empty:
            return {"error": f"No price history for {ticker}"}

        closes = hist["Close"]
        ma50 = closes.rolling(window=50).mean().iloc[-1]
        last_price = closes.iloc[-1]

        delta = closes.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]

        recent = closes.tail(60)
        support = round(recent.min(), 2)
        resistance = round(recent.max(), 2)

        trend = "above" if last_price > ma50 else "below"

        return {
            "ticker": ticker.upper(),
            "last_price": round(last_price, 2),
            "ma50": round(ma50, 2),
            "trend_bias": f"price is {trend} its 50-day average",
            "rsi_14": round(rsi, 1),
            "support_60d": support,
            "resistance_60d": resistance,
            "note": "Technical read only — not a trade signal or financial advice.",
        }
    except Exception as e:
        return {"error": f"Technical analysis failed for {ticker}: {e}"}


# ---------------------------------------------------------------------------
# Watchlist (wraps memory.py so the model can manage it conversationally)
# ---------------------------------------------------------------------------

def add_ticker_to_watchlist(user_id: int, ticker: str) -> str:
    memory.add_to_watchlist(user_id, ticker)
    return f"Added {ticker.upper()} to the watchlist."


def remove_ticker_from_watchlist(user_id: int, ticker: str) -> str:
    memory.remove_from_watchlist(user_id, ticker)
    return f"Removed {ticker.upper()} from the watchlist."


def get_user_watchlist(user_id: int) -> list[str]:
    return memory.get_watchlist(user_id)


# ---------------------------------------------------------------------------
# Stubs — wire these up next (see README "Next steps")
# ---------------------------------------------------------------------------

def transcribe_voice(audio_bytes: bytes, groq_client) -> str:
    """Transcribe a Telegram voice note using Groq's hosted Whisper endpoint."""
    transcription = groq_client.audio.transcriptions.create(
        file=("voice.ogg", io.BytesIO(audio_bytes)),
        model="whisper-large-v3",
    )
    return transcription.text


def extract_pdf_text(pdf_bytes: bytes, max_chars: int = 6000) -> str:
    """Pull text out of an uploaded PDF so the model can answer questions about it."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text[:max_chars]


# ---------------------------------------------------------------------------
# Tool specs — sent to Groq so the model knows what it can call
# ---------------------------------------------------------------------------

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get the current price and day change for a stock ticker.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string", "description": "e.g. AAPL, TSLA"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_overview",
            "description": "Get a short company description, sector, and market cap for a ticker.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": "Search recent news headlines for a company, ticker, or topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_items": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_analysis",
            "description": "Get 50-day moving average, RSI, and support/resistance for a ticker. Informational only.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_ticker_to_watchlist",
            "description": "Add a ticker to the user's watchlist.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_ticker_from_watchlist",
            "description": "Remove a ticker from the user's watchlist.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_watchlist",
            "description": "Get the user's current watchlist.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
