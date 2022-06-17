import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
uri = os.getenv("DATABASE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://")
db = SQL(uri)

pgloader --no-ssl-cert-verification finance.db postgres://slalhnicgowxcm:1cfecc5f529ad6bc67a8cfc8b4d98ee6b8b58590cce25253d8d194689d0298b5@ec2-23-23-182-238.compute-1.amazonaws.com:5432/dcql85mfngv3m0?sslmode=require

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
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    stocks = db.execute("SELECT symbol, name, SUM(shares) as total_shares, price FROM transactions where user_id = ? GROUP BY symbol", user_id)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
    total = cash
    for stock in stocks:
        total += stock["total_shares"] * stock["price"]
    return render_template("index.html", stocks = stocks, cash = cash, total = total, usd = usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    user_id = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        n = request.form.get("shares")
        item = lookup(symbol)
        if not symbol:
            return apology("must provide a symbol")
        elif not item:
            return apology("symbol not found!")
        elif not n or not n.isdigit():
            return apology("must provide a positive integer")
        money = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        n = int(n)
        total_price = n * item["price"]
        if total_price > money:
            return apology("not enough cash to buy shares!")
        else:
            db.execute("UPDATE users SET cash = ? WHERE id = ?", money - total_price, user_id)
            db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES (?, ?, ?, ?, ?, ?)", user_id, item["name"], n, item["price"], "buy", symbol)
        return redirect('/')
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    stocks = db.execute("SELECT symbol, shares, price, type, time FROM transactions WHERE user_id = ?", user_id)
    return render_template("history.html", stocks = stocks, usd = usd)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("invalid symbol")
        stock = lookup(symbol)
        if stock:
            return render_template("quoted.html", stock = stock, usd = usd)
        else:
            return apology("symbol not found!")
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        # Ensure username was submitted
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if not username:
            return apology("must provide username")
        # Ensure password was submitted
        elif not password:
            return apology("must provide password")
        elif not confirmation:
            return apology("must type the password again")
        elif password != confirmation:
            return apology("wrong password retyped")
        # Ensure the username doesn't already exist
        elif len(rows) > 0:
            return apology("such username already exists")
        # Generate hash password
        hashed_password = generate_password_hash(password)
        # Insert into database
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashed_password)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    stocks = db.execute("SELECT symbol FROM transactions where user_id = ? GROUP BY symbol", user_id)
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("Must choose a symbol")
        num = db.execute("SELECT shares FROM transactions WHERE symbol = ? AND user_id = ? GROUP BY symbol", symbol, user_id)
        shares = int(shares)
        if shares > num[0]["shares"]:
            return apology("You don't have that many shares")
        item = lookup(symbol)
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]
        db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES (?, ?, ?, ?, ?, ?)", user_id, item["name"], -shares, item["price"], "sell", symbol)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + shares * item["price"], user_id)
        return redirect('/')
    else:
        return render_template("sell.html", stocks = stocks)
