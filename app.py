
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Application
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
import os
import csv
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from flask_migrate import Migrate

app = Flask(__name__)  # ✅ Create app first

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///job_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)  # ✅ Now initialize migrate after app exists
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
@login_required
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        first_name = request.form.get('firstName')
        last_name = request.form.get('lastName')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirmPassword')
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('signup.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('signup.html')
        
        # Create new user
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# API Routes for Applications
@app.route('/api/applications', methods=['GET'])
@login_required
def get_applications():
    applications = Application.query.filter_by(user_id=current_user.id).all()
    return jsonify([app.to_dict() for app in applications])

@app.route('/api/applications', methods=['POST'])
@login_required
def create_application():
    data = request.get_json()
    
    application = Application(
        user_id=current_user.id,
        company=data['company'],
        position=data['position'],
        date_applied=datetime.strptime(data['dateApplied'], '%Y-%m-%d').date(),
        status=data['status'],
        location=data.get('location', ''),
        salary=data.get('salary', ''),
        notes=data.get('notes', '')
    )
    
    db.session.add(application)
    db.session.commit()
    
    return jsonify(application.to_dict()), 201

@app.route('/api/applications/<int:app_id>', methods=['PUT'])
@login_required
def update_application(app_id):
    application = Application.query.filter_by(id=app_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    
    application.company = data['company']
    application.position = data['position']
    application.date_applied = datetime.strptime(data['dateApplied'], '%Y-%m-%d').date()
    application.status = data['status']
    application.location = data.get('location', '')
    application.salary = data.get('salary', '')
    application.notes = data.get('notes', '')
    
    db.session.commit()
    
    return jsonify(application.to_dict())

@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
@login_required
def delete_application(app_id):
    application = Application.query.filter_by(id=app_id, user_id=current_user.id).first_or_404()
    
    db.session.delete(application)
    db.session.commit()
    
    return '', 204

# Export Routes
@app.route('/export/csv')
@login_required
def export_csv():
    """Export user's applications to CSV"""
    applications = Application.query.filter_by(user_id=current_user.id).all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Company', 'Position', 'Date Applied', 'Status', 'Location', 'Salary', 'Notes', 'Created At'])
    
    # Write data
    for app in applications:
        writer.writerow([
            app.company,
            app.position,
            app.date_applied.strftime('%Y-%m-%d'),
            app.status,
            app.location or '',
            app.salary or '',
            app.notes or '',
            app.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=job_applications_{datetime.now().strftime("%Y%m%d")}.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response

@app.route('/export/pdf')
@login_required
def export_pdf():
    """Export user's applications to PDF"""
    applications = Application.query.filter_by(user_id=current_user.id).all()
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#4f46e5'),
        spaceAfter=30,
    )
    
    # Title
    title = Paragraph(f"Job Applications Report - {current_user.full_name}", title_style)
    elements.append(title)
    
    # Date
    date_text = Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal'])
    elements.append(date_text)
    elements.append(Spacer(1, 0.5*inch))
    
    # Summary statistics
    total = len(applications)
    interviews = len([a for a in applications if a.status in ['Phone Screen', 'Interview Scheduled', 'Interviewed']])
    offers = len([a for a in applications if a.status == 'Offer'])
    
    summary = Paragraph(f"<b>Summary:</b> {total} Total Applications | {interviews} Interviews | {offers} Offers", styles['Normal'])
    elements.append(summary)
    elements.append(Spacer(1, 0.3*inch))
    
    # Applications table
    if applications:
        data = [['Company', 'Position', 'Date Applied', 'Status']]
        
        for app in applications:
            data.append([
                app.company,
                app.position,
                app.date_applied.strftime('%Y-%m-%d'),
                app.status
            ])
        
        table = Table(data, colWidths=[2*inch, 2.5*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        elements.append(table)
    else:
        elements.append(Paragraph("No applications found.", styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'job_applications_{datetime.now().strftime("%Y%m%d")}.pdf',
        mimetype='application/pdf'
    )
def get_serializer():
    return URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Password Reset Routes
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate reset token
            serializer = get_serializer()
            token = serializer.dumps(user.email, salt='password-reset-salt')
            
            # In production, send email here
            # For now, we'll just show the reset link
            reset_url = url_for('reset_password', token=token, _external=True)
            
            # For development: flash the link
            flash(f'Password reset link (in production this would be emailed): {reset_url}', 'info')
            
            # For production: Send email with reset_url
            # send_password_reset_email(user.email, reset_url)
            
            flash('If an account exists with that email, a password reset link has been sent.', 'success')
        else:
            # Don't reveal if email exists or not (security best practice)
            flash('If an account exists with that email, a password reset link has been sent.', 'success')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    try:
        serializer = get_serializer()
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # 1 hour expiry
    except:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirmPassword')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('reset_password.html', token=token)
        
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(password)
            db.session.commit()
            flash('Your password has been reset successfully. Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('User not found.', 'error')
            return redirect(url_for('forgot_password'))
    
    return render_template('reset_password.html', token=token)

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password for logged-in user"""
    if request.method == 'POST':
        current_password = request.form.get('currentPassword')
        new_password = request.form.get('newPassword')
        confirm_password = request.form.get('confirmPassword')
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'error')
            return render_template('change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return render_template('change_password.html')
        
        current_user.set_password(new_password)
        db.session.commit()
        flash('Your password has been changed successfully', 'success')
        return redirect(url_for('home'))
    
    return render_template('change_password.html')

if __name__ == '__main__':
    app.run(debug=True)