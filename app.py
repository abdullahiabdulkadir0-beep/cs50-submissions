import os

from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from helpers import (
    apology,
    format_money,
    format_time,
    get_time,
    login_required,
    lookup,
    usd,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import HTTPException, InternalServerError

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["format_time"] = format_time
app.jinja_env.filters["format_money"] = format_money

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]

    # Get user cash balance
    balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
    totalBalance = balance

    # Get user portfolio (sum of shares for each symbol)
    # NOTE: Changed SUM(quantity) to SUM(shares) AS total_shares and u_id to user_id
    portfolio = db.execute(
        "SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id=? GROUP BY symbol HAVING total_shares > 0",
        user_id,
    )
    prices = []

    # Calculate total portfolio value and fetch current prices
    for owned in portfolio:
        # Lookup the current price
        stock_info = lookup(owned["symbol"])
        if stock_info is None:
             return apology("Could not lookup current stock price", 500)

        current_price = stock_info["price"]
        prices.append(current_price)

        # Calculate asset value and add to total balance
        asset_value = owned["total_shares"] * current_price
        totalBalance += asset_value

        # Add the current price and total value to the asset dictionary for template rendering
        owned["current_price"] = current_price
        owned["total_value"] = asset_value

    return render_template(
        "index.html",
        port=portfolio,
        prices=[p["current_price"] for p in portfolio], # Pass the prices list needed for the template
        balance=balance,
        total_bal=totalBalance,
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        symbol_input = request.form.get("symbol")
        shares_input = request.form.get("shares")
        user_id = session["user_id"]

        if not symbol_input:
            return apology("symbol cannot be blank", 400)

        # Check if shares is a positive integer
        if not shares_input or not shares_input.isdigit() or int(shares_input) <= 0:
             return apology("shares must be a positive whole number", 400)

        shares = int(shares_input)
        symbol = lookup(symbol_input)

        if not symbol:
            return apology("symbol not found", 400)

        price = symbol["price"]
        total_cost = price * shares

        balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

        new_balance = balance - total_cost

        if new_balance < 0:
            return apology("not enough cash to complete transaction", 400)

        # 1. Update user cash balance
        db.execute(
            "UPDATE users SET cash = ? WHERE id = ?",
            new_balance,
            user_id,
        )
        # 2. Insert transaction record
        # NOTE: Changed quantity to shares and u_id to user_id
        db.execute(
            "INSERT INTO transactions (symbol, shares, price, user_id) VALUES(?, ?, ?, ?)",
            symbol["symbol"], # Use the standardized symbol from lookup
            shares,
            price,
            user_id,
        )
        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    # NOTE: Changed quantity to shares and u_id to user_id
    portfolio = db.execute(
        "SELECT t_id, symbol, shares, price, user_id, timestamp FROM transactions WHERE user_id=? ORDER BY t_id DESC",
        session["user_id"],
    )

    return render_template("history.html", port=portfolio)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    submitted = False
    if request.method == "POST":
        submitted = True
        symbol_input = request.form.get("symbol")
        if not symbol_input:
            return apology("symbol cannot be blank")

        result = lookup(symbol_input)
        if not result:
            return apology("symbol not found")
        time = get_time()

        return render_template(
            "quote.html", results=result, currTime=time, submitted=submitted
        )
    return render_template("quote.html", results=None)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password was submitted again
        elif not request.form.get("confirmation"):
            return apology("must re-enter password", 400)

        # Ensure that the passwords match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match")

        # Check if the username is available
        check = db.execute(
            "SELECT * FROM users WHERE username=?", request.form.get("username")
        )
        if len(check) != 0:
            return apology("username not available")

        db.execute(
            "INSERT INTO users (username, hash, cash) VALUES(?, ?, ?)",
            request.form.get("username"),
            generate_password_hash(request.form.get("confirmation")),
            10000.0,
        )

        # Redirect user to home page
        return redirect("/")
    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = session["user_id"]

    # NOTE: Changed SUM(quantity) to SUM(shares) AS total_shares and u_id to user_id
    # Fetch current holdings with positive shares
    portfolio = db.execute(
        "SELECT symbol, SUM(shares) AS total_shares FROM transactions WHERE user_id=? GROUP BY symbol HAVING total_shares > 0",
        user_id,
    )

    if request.method == "POST":
        symbol_to_sell = request.form.get("symbol")
        shares_input = request.form.get("shares")

        if not symbol_to_sell:
            return apology("please select what to sell", 403)

        # Validate shares input
        if not shares_input or not shares_input.isdigit() or int(shares_input) <= 0:
            return apology("shares must be a positive whole number", 403)

        shares_to_sell = int(shares_input)

        # Find the stock in the user's current portfolio
        current_holding = next((item for item in portfolio if item["symbol"] == symbol_to_sell), None)

        if not current_holding:
            return apology("you do not own that stock", 403)

        owned_shares = current_holding["total_shares"]

        # Check if they own enough shares
        if shares_to_sell > owned_shares:
            return apology(f"you only own {owned_shares} shares of {symbol_to_sell}", 403)

        # Lookup price
        lookup_result = lookup(symbol_to_sell)
        if lookup_result is None:
            return apology("could not get current price for stock", 500)

        price = lookup_result["price"]
        sale_value = shares_to_sell * price

        # 1. Update user cash (cash increases)
        db.execute(
            "UPDATE users SET cash = cash + ? WHERE id = ?",
            sale_value,
            user_id,
        )

        # 2. Record transaction (shares are negative for a sale)
        # NOTE: Changed quantity to shares and u_id to user_id
        db.execute(
            "INSERT INTO transactions (symbol, shares, price, user_id) VALUES(?, ?, ?, ?)",
            symbol_to_sell,
            -shares_to_sell,
            price,
            user_id,
        )

        return redirect("/")

    # Pass the portfolio to sell.html
    return render_template("sell.html", port=portfolio)


@app.route("/delete")
@login_required
def delete():
    i = session["user_id"]
    session.clear()
    db.execute("DELETE FROM users WHERE id=?", i)

    return redirect("/login")


@app.errorhandler(HTTPException)
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)
