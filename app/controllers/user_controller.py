from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from services.user_service import UserService

user_service = UserService()

user_controller = Blueprint('user', __name__)


# Route to render the authentication page
@user_controller.route('/auth', methods=['GET'])
def auth_page():
    return render_template('auth.html')


# Route for handling registration
@user_controller.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    user = user_service.register(username, email, password)
    if user:
        flash("Registration successful! Please log in.")
        return redirect(url_for('user.auth_page'))
    else:
        flash("User or email already exists.")
        return redirect(url_for('user.auth_page'))


# Route for handling login
@user_controller.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user = user_service.login(username, password)
    if user:
        session['user_id'] = user.id
        return redirect(url_for('todo.list_todos'))
    else:
        flash("Invalid username or password.")
        return redirect(url_for('user.auth_page'))


# Route for logging out
@user_controller.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return redirect(url_for('user.auth_page'))