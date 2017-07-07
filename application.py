import os
import psycopg2
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from datetime import datetime

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL(os.environ.get("DATABASE_URL") or "sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    # call databases
    stocks = db.execute("SELECT * FROM stocks where \"user\" = :user", user = session["user_id"])
    users = db.execute("SELECT * FROM users where id = :id", id = session["user_id"])
    
    # calculate total price
    total = float(users[0]["cash"])
    i = 0
    for i in range(len(stocks)):
        total += stocks[i]["total"]
        i += 1
    cash = float(users[0]["cash"])
    
    # display home page
    return render_template("index.html", stocks = stocks, cash = cash, total = total)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    
    # if user reached route via POST (as by submitting a form via POST)    
    if request.method=="POST":
        
        # checks if shares provided is a num
        try:
            share = float(request.form.get("shares"))
        except:
            return apology("shares is not a number")
        if (share<=0):
            return apology("did not provide positive num")
            
        # confirm symbol exists
        sym = lookup(request.form.get("symbol"))
        if not sym:
            return apology("invalid symbol")
        
        # call database    
        stocks = db.execute("SELECT * FROM stocks WHERE symbol = :symbol AND \"user\" = :user", symbol=sym["symbol"], user=session["user_id"])
        users = db.execute("SELECT * FROM users where id = :id", id = session["user_id"])
        
        # checks if user has enough money
        if share*sym["price"] > float(users[0]["cash"]):
            return apology("not enough money")
            
        # else pays cash
        else:
            db.execute("UPDATE users SET cash = :cash WHERE id = :id",
            cash = float(users[0]["cash"])-float(request.form.get("shares"))*sym["price"],
            id = session["user_id"]
            )
        
        # checks if symbol exists in database, and adds it if it doesn't
        if len(stocks) == 0:
            
            db.execute("INSERT INTO  \"stocks \" (user, symbol, shares, name, price, total) VALUES (:user, :symbol, :shares, :name, :price, :total)", 
                symbol = sym["symbol"], 
                shares = request.form.get("shares"), 
                user = session["user_id"],
                name = sym["name"],
                price = sym["price"],
                total = float(request.form.get("shares"))*sym["price"]
            )
        
        # else updates existing symbol with new amount of shares    
        else:
            shares = stocks[0]["shares"] + float(request.form.get("shares"))
            db.execute("UPDATE stocks SET shares = :shares, total = :total WHERE id = :id",
            shares = shares,
            total = shares*stocks[0]["price"],
            id = stocks[0]["id"]
        )
        
        # update history
        db.execute("INSERT INTO  \"history \" (user, symbol, shares, price) VALUES(:user, :symbol, :shares, :price)",
        user = session["user_id"],
        symbol = sym["symbol"],
        shares = request.form.get("shares"),
        price = sym["price"]*float(request.form.get("shares"))
        )
        
        # redirect to home page
        return redirect(url_for("index"))
        
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    
    # order history for user by descending date
    history = db.execute("SELECT * FROM history WHERE \"user\" = :user ORDER BY date DESC",
    user=session["user_id"]
    )
    
    # display history page
    return render_template("history.html", history=history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method=="POST":
        # get symbol info through lookup
        company = lookup(request.form.get("symbol"))
        
        if company != None:
            # go to quoted page to display info
            return render_template("quoted.html", company = company)
        
        else:
            # apologizes if symbol is invalid
            return apology("invalid symbol")
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        # go to quote page to input symbol
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
            
        # ensure password was retyped    
        elif not request.form.get("password2"):
            return apology("must retype password")
        
        # ensure passwords match
        if request.form.get("password") != request.form.get("password2"):
            return apology("passwords don't match")

        # confirms username not taken
        if len(db.execute("SELECT username FROM users WHERE username = :username", username=request.form.get("username"))) != 0:
            return apology("username already taken")
            
        # add username and password to database
        hash = pwd_context.hash(request.form.get("password"))
        id = db.execute("INSERT INTO \"users\" (username, hash) VALUES (:username, :password)", username = request.form.get("username"), password=hash)
        
        # remember which user has registered
        session["user_id"]=id
        
        # redirect user to home page
        return redirect(url_for("index"))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:    
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    
    # if user reached route via POST (as by submitting a form via POST)    
    if request.method=="POST":
        
        # checks if shares provided is a num
        try:
            share = float(request.form.get("shares"))
        except:
            return apology("shares is not a number")
        if (share<=0):
            return apology("did not provide positive num")
        
        # confirm symbol exists
        sym = lookup(request.form.get("symbol"))
        if not sym:
            return apology("invalid symbol")
            
        # call databases
        stocks = db.execute("SELECT * FROM stocks WHERE symbol = :symbol AND \"user\" = :user", symbol=sym["symbol"], user=session["user_id"])
        users = db.execute("SELECT * FROM users where id = :id", id = session["user_id"])
        
        # checks if symbol exists in database
        if len(stocks) == 0: 
            return apology("symbol not in database")
            
        # else updates existing symbol with new amount of shares    
        else:
            shares = stocks[0]["shares"]-float(request.form.get("shares"))
            if shares < 0:
                return apology("too many shares")
            if stocks[0]["shares"]==float(request.form.get("shares")):
                db.execute("DELETE FROM stocks WHERE id = :id", id = stocks[0]["id"])
            db.execute("UPDATE stocks SET shares = :shares, total = :total WHERE id = :id",
            shares = shares,
            total = shares*stocks[0]["price"],
            id = stocks[0]["id"]
            )
        
        # user recieves cash
        db.execute("UPDATE users SET cash = :cash WHERE id = :id",
        id = session["user_id"],
        cash = float(users[0]["cash"])+float(request.form.get("shares"))*sym["price"]
        )
        
        # update history
        db.execute("INSERT INTO  \"history \" (user, symbol, shares, price) VALUES(:user, :symbol, :shares, :price)",
        user = session["user_id"],
        symbol = sym["symbol"],
        shares = float("-" + request.form.get("shares")),
        price = sym["price"]*float(request.form.get("shares"))
        )
        
        # redirect to home page
        return redirect(url_for("index"))
        
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("sell.html")
        
@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit cash into account."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method=="POST":
    
        # checks if deposit provided is a num
        try:
            float(request.form.get("deposit"))
        except:
            return apology("deposit is not a number")
        
        # call database
        user = db.execute("SELECT * FROM users where id = :id", id = session["user_id"])
        
        # add cash
        db.execute("UPDATE users SET cash = :cash WHERE id = :id",
        cash = float(request.form.get("deposit"))+user[0]["cash"],
        id = session["user_id"]
        )
        
        # update history
        db.execute("INSERT INTO  \"history \" (user, symbol, shares, price) VALUES(:user, :symbol, :shares, :price)",
        user = session["user_id"],
        symbol = "DEPOSIT",
        shares = 0,
        price = float(request.form.get("deposit"))
        )
        
        # redirect to home page
        return redirect(url_for("index"))
    
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("deposit.html")
        
@app.route("/changepwd", methods=["GET", "POST"])
@login_required
def changepwd():
    """Change password."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        
        # call database
        user = db.execute("SELECT * FROM users WHERE id = :id", id = session["user_id"])
        
        # ensure original password was submitted
        if not request.form.get("originalpass"):
            return apology("must provide original password")

        # ensure password was submitted
        if not request.form.get("newpass"):
            return apology("must provide new password")
            
        # ensure password was retyped    
        if not request.form.get("newpass2"):
            return apology("must retype new password")
        
        # ensure new passwords match
        if request.form.get("newpass") != request.form.get("newpass2"):
            return apology("new passwords don't match")
            
        # ensure original passwords match
        if not pwd_context.verify(request.form.get("originalpass"), user[0]["hash"]):
            return apology("original passwords don't match")
            
        # ensure original and new passowrd don't match
        if request.form.get("originalpass") == request.form.get("newpass"):
            return apology("original and new password are the same")
            
        # update password in database
        db.execute("UPDATE users SET hash = :hash WHERE id = :id",
        hash = pwd_context.hash(request.form.get("newpass")),
        id = session["user_id"]
        )
        
        # return to login page
        return redirect(url_for("logout"))
        
    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("changepwd.html")
        
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)