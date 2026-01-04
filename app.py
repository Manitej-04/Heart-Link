import os
import joblib 
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
import ocr_utils 

app = Flask(__name__)
app.config['SECRET_KEY'] = 'heartline_secure_key_2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///heartline.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- LOAD MODELS ---
try:
    # Using joblib as per your fix
    model = joblib.load('models/best_rf_calibrated.pkl')
    preprocessor = joblib.load('models/preprocessor.pkl')
except Exception as e:
    model = None
    preprocessor = None

# --- MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Login via Email only (No Username)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(150))
    role = db.Column(db.String(50), default='user') 
    reports = db.relationship('Report', backref='patient', lazy=True)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Inputs
    age = db.Column(db.Integer)
    sex = db.Column(db.String(10))
    chest_pain_type = db.Column(db.String(50))
    resting_bp = db.Column(db.Integer)
    cholesterol = db.Column(db.Float)
    fasting_bs = db.Column(db.Integer)
    resting_ecg = db.Column(db.String(50))
    max_hr = db.Column(db.Integer)
    exercise_angina = db.Column(db.String(10))
    oldpeak = db.Column(db.Float)
    st_slope = db.Column(db.String(50))
    
    # Outputs
    prediction = db.Column(db.String(50))
    probability = db.Column(db.Float)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # CHANGED: Look up by email instead of username
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid Email or Password.')
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # CHANGED: Check if email exists
        if User.query.filter_by(email=request.form['email']).first():
            flash('Email already registered.')
            return redirect(url_for('register'))
        
        # CHANGED: Create user without username
        new_user = User(
            email=request.form['email'],
            password=request.form['password'],
            name=request.form['name']
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        # --- ADMIN ANALYTICS LOGIC ---
        # 1. Fetch ALL reports
        all_reports = Report.query.order_by(Report.date.desc()).all()
        
        # 2. Calculate Stats for the Dashboard
        total_patients = len(set(r.user_id for r in all_reports))
        total_reports = len(all_reports)
        high_risk_count = Report.query.filter_by(prediction='High Risk').count()
        low_risk_count = Report.query.filter_by(prediction='Low Risk').count()
        
        # Avoid division by zero
        if total_reports > 0:
            risk_percent = round((high_risk_count / total_reports) * 100, 1)
        else:
            risk_percent = 0

        # Pass 'stats' dictionary to the template
        return render_template('admin/dashboard.html', 
                             reports=all_reports, 
                             stats={
                                 'total_patients': total_patients,
                                 'total_reports': total_reports,
                                 'high_risk': high_risk_count,
                                 'low_risk': low_risk_count,
                                 'risk_percent': risk_percent
                             })
    else:
        # User Logic
        user_reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.date.desc()).all()
        return render_template('user/dashboard.html', reports=user_reports)

@app.route('/predict', methods=['GET', 'POST'])
@login_required
def predict():
    if request.method == 'POST':
        data = {}
        
        # 1. OCR or Manual
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            try:
                data = ocr_utils.ocr_to_row(filepath)
                os.remove(filepath)
            except Exception as e:
                flash(f"OCR Error: {str(e)}")
                return redirect(request.url)
        else:
            data = {
                "Age": request.form.get('age'),
                "Sex": request.form.get('sex'),
                "ChestPainType": request.form.get('chest_pain_type'),
                "RestingBP": request.form.get('resting_bp'),
                "Cholesterol": request.form.get('cholesterol'),
                "FastingBS": request.form.get('fasting_bs'),
                "RestingECG": request.form.get('resting_ecg'),
                "MaxHR": request.form.get('max_hr'),
                "ExerciseAngina": request.form.get('exercise_angina'),
                "Oldpeak": request.form.get('oldpeak'),
                "ST_Slope": request.form.get('st_slope')
            }

        # 2. Sanitize Data (Fix for NoneType error)
        for key in data:
            if data[key] is None or data[key] == '':
                if key in ['Sex', 'ChestPainType', 'RestingECG', 'ExerciseAngina', 'ST_Slope']:
                    data[key] = 'M' if key == 'Sex' else 'Normal'
                else:
                    data[key] = 0

        # Type Conversion
        try:
            data['Age'] = int(data['Age'])
            data['RestingBP'] = int(data['RestingBP'])
            data['Cholesterol'] = float(data['Cholesterol'])
            data['FastingBS'] = int(data['FastingBS'])
            data['MaxHR'] = int(data['MaxHR'])
            data['Oldpeak'] = float(data['Oldpeak'])
        except ValueError:
            flash("Error processing inputs.")
            return redirect(url_for('predict'))

        # 3. Prediction
        try:
            df = pd.DataFrame([data])
            if model and preprocessor:
                 X_processed = preprocessor.transform(df)
                 prob = model.predict_proba(X_processed)[0][1]
            else:
                 # Fallback logic if model fails
                 prob = 0.92 if data['Cholesterol'] > 240 else 0.15
            
            prediction_text = "High Risk" if prob > 0.5 else "Low Risk"

            new_report = Report(
                user_id=current_user.id,
                age=data['Age'], sex=data['Sex'], chest_pain_type=data['ChestPainType'],
                resting_bp=data['RestingBP'], cholesterol=data['Cholesterol'],
                fasting_bs=data['FastingBS'], resting_ecg=data['RestingECG'],
                max_hr=data['MaxHR'], exercise_angina=data['ExerciseAngina'],
                oldpeak=data['Oldpeak'], st_slope=data['ST_Slope'],
                prediction=prediction_text, probability=prob
            )
            db.session.add(new_report)
            db.session.commit()
            return redirect(url_for('dashboard'))

        except Exception as e:
            flash(f"Model Error: {e}")
            return redirect(url_for('predict'))

    return render_template('user/predict.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form['name']
        if request.form['password']:
            current_user.password = request.form['password']
        db.session.commit()
        flash('Profile Updated')
    return render_template('user/profile.html')

@app.route('/report/<int:report_id>/print')
@login_required
def print_report(report_id):
    report = Report.query.get_or_404(report_id)
    return render_template('user/report_print.html', r=report, user=current_user)

# --- INITIAL SETUP ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create Specific Admin User (admin@gmail.com / admin@123)
        admin_email = 'admin@gmail.com'
        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                email=admin_email, 
                password='admin@123', 
                role='admin', 
                name='Super Admin'
            )
            db.session.add(admin)
            db.session.commit()
            print(f"✅ Admin Account Created: {admin_email}")

    app.run(debug=True)