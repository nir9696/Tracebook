from datetime import datetime, timedelta
from flask import flash, Flask, request, render_template, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
import requests


app = Flask(__name__)
app.secret_key = "hello"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///books_lending.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SQLALCHEMY_ECHO"] = True
app.permanent_session_lifetime = timedelta(minutes=30)

db = SQLAlchemy(app)

class users (db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

    books_own = db.relationship('books', backref='owner', lazy=True)
    books_borrow = db.relationship('borrows', backref='borrower', lazy=True)

    def __repr__(self):
        return f'User: |{self.id}|{self.name}|{self.password}|'


class books (db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(100), nullable=False)
    num_of_pages = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self):
        return f'Book: |{self.id}|{self.owner_id}|{self.title}|{self.num_of_pages}|'


class borrows (db.Model):
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), primary_key=True)
    borrower_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    lending_date = db.Column(db.DATETIME, nullable=False, default=datetime.utcnow)
    return_until_date = db.Column(db.DATE)

    def __repr__(self):
        return f'Borrow: |{self.book_id}|{self.borrower_id}|{self.lending_date}|{self.return_until_date}|'


def get_user(user_name, password):
    found_user = users.query.filter_by(name=user_name).first()
    if found_user:
        if found_user.password != password:
            flash("Wrong password!")
            return False
        elif "user_name" in session:
            flash("Already Logged in!")
        else:
            flash("Login Succesfull!")
        return True
    usr = users(name=user_name, password=password)
    db.session.add(usr)
    db.session.commit()
    return True


def get_login_user_name():
    if "user_name" in session:
        return f'Hello {session["user_name"]}!'
    return "Hello guest!"


def get_notifications():
    results = []
    if "user_name" in session:
        user_name = session["user_name"]
        borrower = users.query.filter_by(name=user_name).first()
        curr_date = datetime.now().date()
        results = db.session.query(books.title, users.name, borrows.lending_date, borrows.return_until_date).select_from(borrows).join(books).join(users, users.id == books.owner_id). \
            filter(borrows.borrower_id == borrower.id).filter(borrows.return_until_date < curr_date).all()
    return results


def is_logout():
    return not "user_name" in session


@app.route('/')
def home():
    notifications = get_notifications()
    return render_template("index.html", logout_flag=is_logout(), notfications_query=notifications, login_user=get_login_user_name())


@app.route('/login/', methods=["POST", "GET"])
def login():
    if request.method == "POST":
        session.permanent = True
        user_name = request.form["nm"]
        password = request.form["pwd"]
        login_attemp = get_user(user_name, password)
        if login_attemp:
            session["user_name"] = user_name
            session["password"] = password
        return redirect(url_for("home"))
    else:
        if "user_name" in session:
            flash("Already Logged in!")
            return redirect(url_for("home"))
        return render_template("login.html", login_user=get_login_user_name())


@app.route('/update/', methods=["POST", "GET"])
def update():
    password = None
    if "user_name" in session:
        user_name = session["user_name"]
        if request.method == 'POST':
            password = request.form["pwd"]
            session["password"] = password
            found_user = users.query.filter_by(name=user_name).first()
            found_user.password = password
            db.session.commit()
            flash('Password Saved!')
        return render_template("update.html", login_user=get_login_user_name())
    else:
        flash("You are not logged in!")
        return redirect(url_for("home"))


@app.route('/add_book/', methods=["POST", "GET"])
def add_book():
    if "user_name" in session:
        if request.method == "POST":
            book_name = request.form["book_name"].strip().lower()
            number_of_pages = request.form["number_of_pages"]
            exist_book = db.session.query(books.title, users.name).select_from(users).join(books, users.id == books.owner_id).\
                filter(books.title == book_name and users.name == session["user_name"]).all()
            if exist_book:
                flash("There is already such book in the system!", "info")
                return render_template("add_book.html", login_user=get_login_user_name())
            owner = users.query.filter_by(name=session["user_name"]).first()
            new_book = books(title=book_name, num_of_pages=number_of_pages, owner=owner)
            db.session.add(new_book)
            db.session.commit()
            return redirect(url_for("my_books"))
        else:
            return render_template("add_book.html", login_user=get_login_user_name())
    else:
        flash("You are not logged in!")
        return redirect(url_for("login"))


@app.route('/lend_form/', methods=["POST", "GET"])
def lend_form():
    if "user_name" in session:
        if request.method == "POST":
            book_name = request.form["book_name"]
            lend_to = request.form["lend_to"]
            return_until_date = datetime.strptime(request.form["r_date"], '%Y-%m-%d')

            usr = users.query.filter_by(name=lend_to).first()
            if not usr:
                flash("There is not such user!", "info")
                return render_template("lend_form.html", login_user=get_login_user_name())
            book = books.query.filter_by(title=book_name).first()
            new_borrower = borrows(return_until_date=return_until_date, borrower=usr, book_id=book.id)
            db.session.add(new_borrower)
            db.session.commit()
            return redirect(url_for("my_lent_books"))
        else:
            all_users = users.query.filter(users.name != session["user_name"]).all()
            user_books = db.session.query(books.title, users.name).select_from(users).join(books, users.id == books.owner_id).\
                outerjoin(borrows, books.id == borrows.book_id).filter(users.name == session["user_name"]).filter(borrows.book_id == None).all()
            return render_template("lend_form.html", users_query=all_users, books_query=user_books, login_user=get_login_user_name())
    else:
        flash("You are not logged in!")
        return redirect(url_for("home"))


@app.route('/return_form/', methods=["POST", "GET"])
def return_form():
    if "user_name" in session:
        if request.method == "POST":
            book_name = request.form["book_name"]
            return_to = request.form["return_to"]

            owner = users.query.filter_by(name=return_to).first()
            book = books.query.filter_by(title=book_name, owner=owner).first()
            borrower = users.query.filter_by(name=session["user_name"]).first()
            if not owner or not book or not borrower:
                flash("Nothing to return.", "info")
                return render_template("return_form.html", login_user=get_login_user_name())
            borrow_entry = borrows.query.filter_by(borrower=borrower, book_id=book.id).delete()
            db.session.commit()
            if not borrow_entry:
                flash("Nothing to return.", "info")
                return render_template("return_form.html", login_user=get_login_user_name())
            return redirect(url_for("my_borrowed_books"))
        else:
            all_users = users.query.filter(users.name != session["user_name"]).all()
            user_books = db.session.query(books.title, users.name).select_from(borrows).join(books,
                                                                                           borrows.book_id == books.id). \
                join(users, users.id == borrows.borrower_id).filter(users.name == session["user_name"]).all()
            return render_template("return_form.html", books_query=user_books, users_query=all_users, login_user=get_login_user_name())
    else:
        flash("You are not logged in!")
        return redirect(url_for("home"))


@app.route('/my_books/', methods=["POST", "GET"])
def my_books():
    if "user_name" in session:
        user_name = session["user_name"]
        user_books = db.session.query(books.title, books.num_of_pages).select_from(users).join(books, users.id == books.owner_id). \
            filter(users.name == user_name).all()
        return render_template("my_books.html", books_query=user_books)
    else:
        flash("You are not logged in!")
        return redirect(url_for("home"))


@app.route('/my_borrowed_books/', methods=["POST", "GET"])
def my_borrowed_books():
    if "user_name" in session:
        user_name = session["user_name"]
        borrower = users.query.filter_by(name=user_name).first()
        results = db.session.query(books.title, users.name, borrows.lending_date, borrows.return_until_date).select_from(borrows).join(books).join(users, users.id == books.owner_id). \
            filter(borrows.borrower_id == borrower.id).all()
        return render_template("my_borrowed_books.html", borrowed_query=results)
    else:
        flash("You are not logged in!")
        return redirect(url_for("home"))


@app.route('/my_lent_books/', methods=["POST", "GET"])
def my_lent_books():
    if "user_name" in session:
        user_name = session["user_name"]
        lender = users.query.filter_by(name=user_name).first()
        results = db.session.query(books.title, users.name, borrows.lending_date, borrows.return_until_date).select_from(borrows).join(books).join(users, users.id == borrows.borrower_id). \
            filter(books.owner_id == lender.id).all()
        return render_template("my_lent_books.html", lent_query=results)
    else:
        flash("You are not logged in!")
        return redirect(url_for("home"))


@app.route('/logout/')
def logout():
    flash("You have been logged out!", "info")
    session.pop("user_name", None)
    session.pop("password", None)
    return redirect(url_for("home"))


if __name__ == "__main__":
    db.create_all()
    app.run(debug=True, port=5000)