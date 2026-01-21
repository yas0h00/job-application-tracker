from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from models import db, User, Application
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
import os
import csv
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
database_url = os.environ.get('DATABASE_URL', 'sqlite:///job_tracker.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_USERNAME'))

db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def send_password_reset_email(user_email, reset_url):
    if not app.config['MAIL_USERNAME']:
        return False
    try:
        msg = Message('Password Reset - Job Tracker', recipients=[user_email],
                     html=f'<p>Reset your password: <a href="{reset_url}">Click here</a></p><p>Link expires in 1 hour.</p>')
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

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
        flash('Invalid email or password', 'error')
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
            flash('Email already registered', 'error')
            return render_template('signup.html')
        user = User(first_name=request.form.get('firstName'), last_name=request.form.get('lastName'), email=request.form.get('email'))
        user.set_password(request.form.get('password'))
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
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
    return jsonify([app.to_dict() for app in Application.query.filter_by(user_id=current_user.id).all()])

@app.route('/api/applications', methods=['POST'])
@login_required
def create_application():
    data = request.get_json()
    app = Application(user_id=current_user.id, company=data['company'], position=data['position'],
                     date_applied=datetime.strptime(data['dateApplied'], '%Y-%m-%d').date(),
                     status=data['status'], location=data.get('location',''), salary=data.get('salary',''), notes=data.get('notes',''))
    db.session.add(app)
    db.session.commit()
    return jsonify(app.to_dict()), 201

@app.route('/api/applications/<int:app_id>', methods=['PUT'])
@login_required
def update_application(app_id):
    app = Application.query.filter_by(id=app_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    app.company = data['company']
    app.position = data['position']
    app.date_applied = datetime.strptime(data['dateApplied'], '%Y-%m-%d').date()
    app.status = data['status']
    app.location = data.get('location','')
    app.salary = data.get('salary','')
    app.notes = data.get('notes','')
    db.session.commit()
    return jsonify(app.to_dict())

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
@login_required
def delete_application(app_id):
    app = Application.query.filter_by(id=app_id, user_id=current_user.id).first_or_404()
    db.session.delete(app)
    db.session.commit()
    return '', 204

@app.route('/export/csv')
@login_required
def export_csv():
    apps = Application.query.filter_by(user_id=current_user.id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Company','Position','Date','Status','Location','Salary','Notes'])
    for a in apps:
        writer.writerow([a.company,a.position,a.date_applied.strftime('%Y-%m-%d'),a.status,a.location or '',a.salary or '',a.notes or ''])
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=applications_{datetime.now().strftime("%Y%m%d")}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

@app.route('/export/pdf')
@login_required
def export_pdf():
    apps = Application.query.filter_by(user_id=current_user.id).all()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    data = [['Company','Position','Date','Status']]
    for a in apps:
        data.append([a.company, a.position, a.date_applied.strftime('%Y-%m-%d'), a.status])
    table = Table(data)
    table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
    doc.build([table])
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'applications.pdf', mimetype='application/pdf')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user:
            from itsdangerous import URLSafeTimedSerializer
            s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
            token = s.dumps(user.email, salt='password-reset-salt')
            reset_url = url_for('reset_password', token=token, _external=True)
            if send_password_reset_email(user.email, reset_url):
                flash('If account exists, reset link sent.', 'success')
            else:
                flash('Error sending email.', 'error')
        else:
            flash('If account exists, reset link sent.', 'success')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    try:
        from itsdangerous import URLSafeTimedSerializer
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('Invalid or expired link.', 'error')
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        if request.form.get('password') != request.form.get('confirmPassword'):
            flash('Passwords do not match', 'error')
            return render_template('reset_password.html', token=token)
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(request.form.get('password'))
            db.session.commit()
            flash('Password reset! Please log in.', 'success')
            return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

if __name__ == '__main__':
    app.run(debug=True)
