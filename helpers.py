import datetime
import os
import urllib.parse
from functools import wraps

import requests
from flask import redirect, render_template, session


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        # Ensure the correct URL format for IEX Cloud
        url = f"https://api.iex.cloud/v1/data/core/quote/{urllib.parse.quote_plus(symbol)}?token={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()[0]

        # Use .get() for safer dictionary access, providing 0.0 or None as a default.
        # This prevents the "UndefinedError: 'dict object' has no attribute 'change'" error.
        return {
            "name": quote.get("companyName"),
            "price": float(quote.get("latestPrice") or 0.0),
            "symbol": quote.get("symbol"),
            "avgTotalVolume": quote.get("avgTotalVolume", 0),
            "calculationPrice": quote.get("calculationPrice"),
            "change": float(quote.get("change") or 0.0), # Safe access, default to 0.0
            "changePercent": float(quote.get("changePercent") or 0.0), # Safe access, default to 0.0
            "close": quote.get("close"),
            "closeTime": quote.get("closeTime"),
            "currency": quote.get("currency"),
            "delayedPrice": quote.get("delayedPrice"),
            "delayedPriceTime": quote.get("delayedPriceTime"),
            "extendedChange": quote.get("extendedChange"),
            "extendedChangePercent": quote.get("extendedChangePercent"),
            "extendedPrice": quote.get("extendedPrice"),
            "extendedPriceTime": quote.get("extendedPriceTime"),
            "high": quote.get("high"),
            "highSource": quote.get("highSource"),
            "highTime": quote.get("highTime"),
            "iexAskPrice": quote.get("iexAskPrice"),
            "iexAskSize": quote.get("iexAskSize"),
            "iexBidPrice": quote.get("iexBidPrice"),
            "iexBidSize": quote.get("iexBidSize"),
            "iexClose": quote.get("iexClose"),
            "iexCloseTime": quote.get("iexCloseTime"),
            "iexLastUpdated": quote.get("iexLastUpdated"),
            "iexMarketPercent": quote.get("iexMarketPercent"),
            "iexOpen": quote.get("iexOpen"),
            "iexOpenTime": quote.get("iexOpenTime"),
            "iexRealtimePrice": quote.get("iexRealtimePrice"),
            "iexRealtimeSize": quote.get("iexRealtimeSize"),
            "iexVolume": quote.get("iexVolume"),
            "lastTradeTime": quote.get("lastTradeTime"),
            "latestPrice": quote.get("latestPrice"),
            "latestSource": quote.get("latestSource"),
            "latestTime": quote.get("latestTime"),
            "latestUpdate": quote.get("latestUpdate"),
            "latestVolume": quote.get("latestVolume"),
            "low": quote.get("low"),
            "lowSource": quote.get("lowSource"),
            "lowTime": quote.get("lowTime"),
            "marketCap": quote.get("marketCap"),
            "oddLotDelayedPrice": quote.get("oddLotDelayedPrice"),
            "oddLotDelayedPriceTime": quote.get("oddLotDelayedPriceTime"),
            "open": quote.get("open"),
            "openTime": quote.get("openTime"),
            "openSource": quote.get("openSource"),
            "peRatio": quote.get("peRatio"),
            "previousClose": quote.get("previousClose"),
            "previousVolume": quote.get("previousVolume"),
            "primaryExchange": quote.get("primaryExchange"),
            "volume": quote.get("volume"),
            "week52High": quote.get("week52High"),
            "week52Low": quote.get("week52Low"),
            "ytdChange": quote.get("ytdChange"),
            "isUSMarketOpen": quote.get("isUSMarketOpen", False),
        }
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def get_time():
    """Get current time"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_time(time):
    """Format time"""
    # Assuming 'time' here is a Unix epoch timestamp in milliseconds (standard for IEX's latestUpdate)
    try:
        timestamp = time
        dt = datetime.datetime.fromtimestamp(timestamp / 1000)
        # prints the time in 12-hour format with AM/PM and the time zone abbreviation
        return dt.strftime("%I:%M %p %Z").lstrip("0")
    except (TypeError, ValueError):
        return "N/A" # Return N/A if timestamp is invalid


def format_money(value):
    if value is None:
        return "N/A"
    try:
        value = float(value)
        if value >= 1000000000:
            return f"{value / 1000000000:.2f}B"
        if value >= 1000000:
            return f"{value / 1000000:.2f}M"
        return value
    except (TypeError, ValueError):
        return "N/A"
