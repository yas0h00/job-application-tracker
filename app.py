from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from models import db, User, Application
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
import os
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key')
db_url = os.environ.get('DATABASE_URL', 'sqlite:///job_tracker.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user, remember=request.form.get('remember')=='on')
            return redirect(request.args.get('next') or url_for('home'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        if request.form.get('password') != request.form.get('confirmPassword'):
            flash('Passwords do not match', 'error')
            return render_template('signup.html')
        if User.query.filter_by(email=request.form.get('email')).first():
            flash('Email exists', 'error')
            return render_template('signup.html')
        user = User(first_name=request.form.get('firstName'), last_name=request.form.get('lastName'), email=request.form.get('email'))
        user.set_password(request.form.get('password'))
        db.session.add(user)
        db.session.commit()
        flash('Account created!', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/api/applications', methods=['GET'])
@login_required
def get_applications():
    return jsonify([a.to_dict() for a in Application.query.filter_by(user_id=current_user.id).all()])

@app.route('/api/applications', methods=['POST'])
@login_required
def create_application():
    d = request.get_json()
    a = Application(user_id=current_user.id, company=d['company'], position=d['position'],
                   date_applied=datetime.strptime(d['dateApplied'], '%Y-%m-%d').date(),
                   status=d['status'], location=d.get('location',''), salary=d.get('salary',''), notes=d.get('notes',''))
    db.session.add(a)
    db.session.commit()
    return jsonify(a.to_dict()), 201

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
@login_required
def delete_application(app_id):
    a = Application.query.filter_by(id=app_id, user_id=current_user.id).first_or_404()
    db.session.delete(a)
    db.session.commit()
    return '', 204

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and app.config['MAIL_USERNAME']:
            s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
            token = s.dumps(user.email, salt='pass-reset')
            url = url_for('reset_password', token=token, _external=True)
            try:
                msg = Message('Password Reset', recipients=[user.email], html=f'<a href="{url}">Reset</a>')
                mail.send(msg)
                flash('Reset link sent!', 'success')
            except:
                flash('Email error', 'error')
        else:
            flash('If account exists, link sent', 'success')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    try:
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = s.loads(token, salt='pass-reset', max_age=3600)
    except:
        flash('Invalid link', 'error')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        if request.form.get('password') != request.form.get('confirmPassword'):
            flash('Passwords do not match', 'error')
            return render_template('reset_password.html', token=token)
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(request.form.get('password'))
            db.session.commit()
            flash('Password reset!', 'success')
            return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

if __name__ == '__main__':
    app.run(debug=True)
