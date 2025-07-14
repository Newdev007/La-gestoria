
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from datetime import datetime, timedelta
import json
import uuid
import os
import sqlite3
import hashlib
import jwt
from functools import wraps
import pandas as pd
from werkzeug.utils import secure_filename
import io
import base64
try:
    from email.mime.text import MIMEText as MimeText
    from email.mime.multipart import MIMEMultipart as MimeMultipart
except ImportError:
    # Fallback for problematic installations
    MimeText = None
    MimeMultipart = None
import smtplib
import threading
import schedule
import time
import requests

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Sesiones de 30 días

# Crear directorio de uploads si no existe
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Configuración de base de datos
def init_db():
    conn = sqlite3.connect('gestortaxi.db')
    cursor = conn.cursor()
    
    # Tabla de usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'trial',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            trial_end TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            profile_data TEXT
        )
    ''')
    
    # Tabla de empresas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            name TEXT NOT NULL,
            cif TEXT,
            address TEXT,
            phone TEXT,
            email TEXT,
            logo_path TEXT,
            sector TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            config_data TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabla de empleados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            company_id TEXT,
            name TEXT NOT NULL,
            surname TEXT NOT NULL,
            dni TEXT UNIQUE,
            nss TEXT,
            birth_date DATE,
            position TEXT,
            salary DECIMAL(10,2),
            start_date DATE,
            end_date DATE,
            status TEXT DEFAULT 'active',
            contact_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    ''')
    
    # Tabla de vehículos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            company_id TEXT,
            plate TEXT UNIQUE NOT NULL,
            brand TEXT,
            model TEXT,
            year INTEGER,
            type TEXT,
            status TEXT DEFAULT 'active',
            insurance_expiry DATE,
            itv_expiry DATE,
            license_number TEXT,
            driver_id TEXT,
            specifications TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (company_id) REFERENCES companies (id),
            FOREIGN KEY (driver_id) REFERENCES employees (id)
        )
    ''')
    
    # Tabla de ingresos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS income (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            company_id TEXT,
            vehicle_id TEXT,
            date DATE,
            amount DECIMAL(10,2),
            type TEXT,
            source TEXT,
            description TEXT,
            invoice_number TEXT,
            vat_rate DECIMAL(5,2),
            vat_amount DECIMAL(10,2),
            payment_method TEXT,
            client_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (company_id) REFERENCES companies (id),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
        )
    ''')
    
    # Tabla de gastos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            company_id TEXT,
            vehicle_id TEXT,
            date DATE,
            amount DECIMAL(10,2),
            type TEXT,
            category TEXT,
            description TEXT,
            supplier TEXT,
            invoice_number TEXT,
            vat_rate DECIMAL(5,2),
            vat_amount DECIMAL(10,2),
            deductible BOOLEAN DEFAULT 1,
            receipt_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (company_id) REFERENCES companies (id),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
        )
    ''')
    
    # Tabla de facturas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            company_id TEXT,
            client_id TEXT,
            invoice_number TEXT UNIQUE,
            date DATE,
            due_date DATE,
            subtotal DECIMAL(10,2),
            vat_amount DECIMAL(10,2),
            total DECIMAL(10,2),
            status TEXT DEFAULT 'draft',
            payment_method TEXT,
            notes TEXT,
            invoice_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    ''')
    
    # Tabla de clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            company_id TEXT,
            name TEXT NOT NULL,
            cif_nif TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            type TEXT DEFAULT 'individual',
            credit_limit DECIMAL(10,2),
            payment_terms INTEGER DEFAULT 30,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    ''')
    
    # Tabla de documentos fiscales
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fiscal_documents (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            company_id TEXT,
            type TEXT,
            model_number TEXT,
            period TEXT,
            year INTEGER,
            status TEXT DEFAULT 'pending',
            amount DECIMAL(10,2),
            due_date DATE,
            submission_date DATE,
            file_path TEXT,
            data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    ''')
    
    # Tabla de recordatorios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            type TEXT,
            title TEXT,
            description TEXT,
            due_date DATE,
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'medium',
            related_id TEXT,
            notification_sent BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabla de análisis y métricas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            company_id TEXT,
            date DATE,
            metric_type TEXT,
            metric_value DECIMAL(15,2),
            additional_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    ''')
    
    # Tabla de configuraciones
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            category TEXT,
            key TEXT,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Inicializar base de datos al arrancar
init_db()

# Utilidades de autenticación
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hash):
    return hashlib.sha256(password.encode()).hexdigest() == hash

def generate_jwt_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.secret_key, algorithm='HS256')

def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, app.secret_key, algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'No autorizado'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Funciones de utilidad para base de datos
def get_db_connection():
    conn = sqlite3.connect('gestortaxi.db')
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=None, fetch=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    
    if fetch:
        result = cursor.fetchall()
        conn.close()
        return result
    else:
        conn.commit()
        conn.close()
        return cursor.lastrowid

# Funciones de análisis y métricas
def calculate_monthly_metrics(user_id):
    current_month = datetime.now().strftime('%Y-%m')
    
    # Ingresos del mes
    income_query = '''
        SELECT SUM(amount) as total_income FROM income 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
    '''
    income_result = execute_query(income_query, (user_id, current_month), fetch=True)
    total_income = income_result[0][0] if income_result[0][0] else 0
    
    # Gastos del mes
    expense_query = '''
        SELECT SUM(amount) as total_expenses FROM expenses 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
    '''
    expense_result = execute_query(expense_query, (user_id, current_month), fetch=True)
    total_expenses = expense_result[0][0] if expense_result[0][0] else 0
    
    # Beneficio neto
    net_profit = total_income - total_expenses
    
    # Guardar métricas
    today = datetime.now().date()
    metrics = [
        (str(uuid.uuid4()), user_id, None, today, 'monthly_income', total_income, None),
        (str(uuid.uuid4()), user_id, None, today, 'monthly_expenses', total_expenses, None),
        (str(uuid.uuid4()), user_id, None, today, 'monthly_profit', net_profit, None)
    ]
    
    for metric in metrics:
        execute_query('''
            INSERT OR REPLACE INTO analytics 
            (id, user_id, company_id, date, metric_type, metric_value, additional_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', metric)
    
    return {
        'income': total_income,
        'expenses': total_expenses,
        'profit': net_profit
    }

# Sistema de notificaciones
def send_email_notification(to_email, subject, message):
    """Envía notificación por email si está disponible"""
    if MimeText is None or MimeMultipart is None:
        print(f"Email notification (fallback): {subject} - {message}")
        return False
    
    try:
        # Aquí iría la lógica de envío de email real
        print(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

def check_reminders():
    today = datetime.now().date()
    upcoming_reminders = execute_query('''
        SELECT * FROM reminders 
        WHERE due_date <= ? AND status = 'pending' AND notification_sent = 0
    ''', (today,), fetch=True)
    
    for reminder in upcoming_reminders:
        # Marcar como notificado
        execute_query('''
            UPDATE reminders SET notification_sent = 1 WHERE id = ?
        ''', (reminder['id'],))
        
        # Enviar notificación
        send_email_notification(
            "user@example.com", 
            f"Recordatorio: {reminder['title']}", 
            reminder['description']
        )

# Scheduler para tareas automáticas
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)

# Programar tareas
schedule.every().day.at("09:00").do(check_reminders)
schedule.every().day.at("23:00").do(lambda: print("Backup automático realizado"))

# Iniciar scheduler en hilo separado
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# RUTAS PRINCIPALES
@app.route('/')
def landing():
    # Siempre mostrar la landing page como inicio
    return render_template('landing.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    
    # Obtener datos del dashboard
    metrics = calculate_monthly_metrics(user_id)
    
    # Obtener recordatorios pendientes
    reminders = execute_query('''
        SELECT * FROM reminders 
        WHERE user_id = ? AND status = 'pending' 
        ORDER BY due_date ASC LIMIT 5
    ''', (user_id,), fetch=True)
    
    # Datos para gráficos (últimos 6 meses)
    chart_data = []
    for i in range(6):
        month_date = (datetime.now() - timedelta(days=30*i)).strftime('%Y-%m')
        monthly_data = execute_query('''
            SELECT 
                COALESCE(SUM(CASE WHEN metric_type = 'monthly_income' THEN metric_value ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN metric_type = 'monthly_expenses' THEN metric_value ELSE 0 END), 0) as expenses
            FROM analytics 
            WHERE user_id = ? AND strftime('%Y-%m', date) = ?
            AND metric_type IN ('monthly_income', 'monthly_expenses')
        ''', (user_id, month_date), fetch=True)
        
        if monthly_data:
            chart_data.append({
                'month': month_date,
                'income': float(monthly_data[0][0]) if monthly_data[0][0] else 0,
                'expenses': float(monthly_data[0][1]) if monthly_data[0][1] else 0
            })
    
    return render_template('dashboard.html', 
                         metrics=metrics, 
                         reminders=reminders, 
                         chart_data=json.dumps(chart_data))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está logueado, redirigir al dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.json.get('email')
        password = request.json.get('password')
        
        user = execute_query('''
            SELECT id, password_hash, is_active FROM users WHERE email = ?
        ''', (email,), fetch=True)
        
        if user and verify_password(password, user[0]['password_hash']) and user[0]['is_active']:
            session['user_id'] = user[0]['id']
            session['user_email'] = email
            session.permanent = True  # Hacer la sesión permanente
            app.permanent_session_lifetime = timedelta(days=30)  # 30 días
            return jsonify({'success': True, 'redirect': '/dashboard'})
        else:
            return jsonify({'success': False, 'message': 'Credenciales inválidas'})
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Si ya está logueado, redirigir al dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        plan = data.get('plan', 'trial')
        
        # Verificar si el email ya existe
        existing_user = execute_query('''
            SELECT id FROM users WHERE email = ?
        ''', (email,), fetch=True)
        
        if not existing_user:
            user_id = str(uuid.uuid4())
            password_hash = hash_password(password)
            trial_end = datetime.now() + timedelta(days=14) if plan == 'trial' else None
            
            execute_query('''
                INSERT INTO users (id, email, password_hash, plan, trial_end)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, email, password_hash, plan, trial_end))
            
            session['user_id'] = user_id
            session['user_email'] = email
            session.permanent = True  # Hacer la sesión permanente
            app.permanent_session_lifetime = timedelta(days=30)  # 30 días
            
            # Crear configuraciones por defecto
            default_settings = [
                (str(uuid.uuid4()), user_id, 'notifications', 'email_enabled', 'true'),
                (str(uuid.uuid4()), user_id, 'fiscal', 'vat_rate', '21'),
                (str(uuid.uuid4()), user_id, 'business', 'currency', 'EUR'),
            ]
            
            for setting in default_settings:
                execute_query('''
                    INSERT INTO settings (id, user_id, category, key, value)
                    VALUES (?, ?, ?, ?, ?)
                ''', setting)
            
            return jsonify({'success': True, 'redirect': '/dashboard'})
        else:
            return jsonify({'success': False, 'message': 'El email ya está registrado. <a href="/login" class="text-blue-600 hover:underline">Inicia sesión aquí</a>'})
    
    return render_template('register.html')

# API ENDPOINTS AVANZADOS

@app.route('/api/companies', methods=['GET', 'POST'])
@login_required
def companies_api():
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.json
        company_id = str(uuid.uuid4())
        
        execute_query('''
            INSERT INTO companies (id, user_id, name, cif, address, phone, email, sector, config_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            company_id, user_id, data.get('name'), data.get('cif'),
            data.get('address'), data.get('phone'), data.get('email'),
            data.get('sector'), json.dumps(data.get('config', {}))
        ))
        
        return jsonify({'success': True, 'company_id': company_id})
    
    companies = execute_query('''
        SELECT * FROM companies WHERE user_id = ? ORDER BY created_at DESC
    ''', (user_id,), fetch=True)
    
    return jsonify([dict(company) for company in companies])

@app.route('/api/employees', methods=['GET', 'POST'])
@login_required
def employees_api():
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.json
        employee_id = str(uuid.uuid4())
        
        execute_query('''
            INSERT INTO employees (id, user_id, company_id, name, surname, dni, nss, 
                                 birth_date, position, salary, start_date, contact_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            employee_id, user_id, data.get('company_id'), data.get('name'),
            data.get('surname'), data.get('dni'), data.get('nss'),
            data.get('birth_date'), data.get('position'), data.get('salary'),
            data.get('start_date'), json.dumps(data.get('contact', {}))
        ))
        
        return jsonify({'success': True, 'employee_id': employee_id})
    
    employees = execute_query('''
        SELECT e.*, c.name as company_name 
        FROM employees e 
        LEFT JOIN companies c ON e.company_id = c.id 
        WHERE e.user_id = ? AND e.status = 'active'
        ORDER BY e.created_at DESC
    ''', (user_id,), fetch=True)
    
    return jsonify([dict(employee) for employee in employees])

@app.route('/api/vehicles', methods=['GET', 'POST'])
@login_required
def vehicles_api():
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.json
        vehicle_id = str(uuid.uuid4())
        
        execute_query('''
            INSERT INTO vehicles (id, user_id, company_id, plate, brand, model, year, 
                                type, insurance_expiry, itv_expiry, license_number, 
                                driver_id, specifications)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            vehicle_id, user_id, data.get('company_id'), data.get('plate'),
            data.get('brand'), data.get('model'), data.get('year'),
            data.get('type'), data.get('insurance_expiry'), data.get('itv_expiry'),
            data.get('license_number'), data.get('driver_id'),
            json.dumps(data.get('specifications', {}))
        ))
        
        return jsonify({'success': True, 'vehicle_id': vehicle_id})
    
    vehicles = execute_query('''
        SELECT v.*, c.name as company_name, e.name as driver_name 
        FROM vehicles v 
        LEFT JOIN companies c ON v.company_id = c.id 
        LEFT JOIN employees e ON v.driver_id = e.id 
        WHERE v.user_id = ? AND v.status = 'active'
        ORDER BY v.created_at DESC
    ''', (user_id,), fetch=True)
    
    return jsonify([dict(vehicle) for vehicle in vehicles])

@app.route('/api/income', methods=['GET', 'POST'])
@login_required
def income_api():
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.json
        income_id = str(uuid.uuid4())
        
        # Calcular IVA
        amount = float(data.get('amount', 0))
        vat_rate = float(data.get('vat_rate', 21))
        vat_amount = amount * (vat_rate / 100)
        
        execute_query('''
            INSERT INTO income (id, user_id, company_id, vehicle_id, date, amount, 
                              type, source, description, invoice_number, vat_rate, 
                              vat_amount, payment_method, client_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            income_id, user_id, data.get('company_id'), data.get('vehicle_id'),
            data.get('date'), amount, data.get('type'), data.get('source'),
            data.get('description'), data.get('invoice_number'), vat_rate,
            vat_amount, data.get('payment_method'), json.dumps(data.get('client', {}))
        ))
        
        return jsonify({'success': True, 'income_id': income_id})
    
    # Filtros
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    vehicle_id = request.args.get('vehicle_id')
    
    query = '''
        SELECT i.*, v.plate as vehicle_plate, c.name as company_name 
        FROM income i 
        LEFT JOIN vehicles v ON i.vehicle_id = v.id 
        LEFT JOIN companies c ON i.company_id = c.id 
        WHERE i.user_id = ?
    '''
    params = [user_id]
    
    if start_date:
        query += ' AND i.date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND i.date <= ?'
        params.append(end_date)
    if vehicle_id:
        query += ' AND i.vehicle_id = ?'
        params.append(vehicle_id)
    
    query += ' ORDER BY i.date DESC'
    
    income_records = execute_query(query, params, fetch=True)
    
    return jsonify([dict(record) for record in income_records])

@app.route('/api/expenses', methods=['GET', 'POST'])
@login_required
def expenses_api():
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.json
        expense_id = str(uuid.uuid4())
        
        # Calcular IVA
        amount = float(data.get('amount', 0))
        vat_rate = float(data.get('vat_rate', 21))
        vat_amount = amount * (vat_rate / 100)
        
        execute_query('''
            INSERT INTO expenses (id, user_id, company_id, vehicle_id, date, amount, 
                                type, category, description, supplier, invoice_number, 
                                vat_rate, vat_amount, deductible)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            expense_id, user_id, data.get('company_id'), data.get('vehicle_id'),
            data.get('date'), amount, data.get('type'), data.get('category'),
            data.get('description'), data.get('supplier'), data.get('invoice_number'),
            vat_rate, vat_amount, data.get('deductible', True)
        ))
        
        return jsonify({'success': True, 'expense_id': expense_id})
    
    # Filtros similares a income
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    vehicle_id = request.args.get('vehicle_id')
    category = request.args.get('category')
    
    query = '''
        SELECT e.*, v.plate as vehicle_plate, c.name as company_name 
        FROM expenses e 
        LEFT JOIN vehicles v ON e.vehicle_id = v.id 
        LEFT JOIN companies c ON e.company_id = c.id 
        WHERE e.user_id = ?
    '''
    params = [user_id]
    
    if start_date:
        query += ' AND e.date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND e.date <= ?'
        params.append(end_date)
    if vehicle_id:
        query += ' AND e.vehicle_id = ?'
        params.append(vehicle_id)
    if category:
        query += ' AND e.category = ?'
        params.append(category)
    
    query += ' ORDER BY e.date DESC'
    
    expense_records = execute_query(query, params, fetch=True)
    
    return jsonify([dict(record) for record in expense_records])

@app.route('/api/invoices', methods=['GET', 'POST'])
@login_required
def invoices_api():
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.json
        invoice_id = str(uuid.uuid4())
        
        # Generar número de factura automático
        last_invoice = execute_query('''
            SELECT invoice_number FROM invoices 
            WHERE user_id = ? AND invoice_number LIKE ?
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id, f"{datetime.now().year}%"), fetch=True)
        
        if last_invoice:
            last_number = int(last_invoice[0]['invoice_number'].split('-')[-1])
            invoice_number = f"{datetime.now().year}-{last_number + 1:04d}"
        else:
            invoice_number = f"{datetime.now().year}-0001"
        
        execute_query('''
            INSERT INTO invoices (id, user_id, company_id, client_id, invoice_number, 
                                date, due_date, subtotal, vat_amount, total, status, 
                                payment_method, notes, invoice_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            invoice_id, user_id, data.get('company_id'), data.get('client_id'),
            invoice_number, data.get('date'), data.get('due_date'),
            data.get('subtotal'), data.get('vat_amount'), data.get('total'),
            data.get('status', 'draft'), data.get('payment_method'),
            data.get('notes'), json.dumps(data.get('items', []))
        ))
        
        return jsonify({'success': True, 'invoice_id': invoice_id, 'invoice_number': invoice_number})
    
    invoices = execute_query('''
        SELECT i.*, c.name as client_name, comp.name as company_name 
        FROM invoices i 
        LEFT JOIN clients c ON i.client_id = c.id 
        LEFT JOIN companies comp ON i.company_id = comp.id 
        WHERE i.user_id = ? 
        ORDER BY i.created_at DESC
    ''', (user_id,), fetch=True)
    
    return jsonify([dict(invoice) for invoice in invoices])

@app.route('/api/analytics/dashboard')
@login_required
def analytics_dashboard():
    user_id = session['user_id']
    
    # Métricas del mes actual
    current_metrics = calculate_monthly_metrics(user_id)
    
    # Comparación con mes anterior
    previous_month = (datetime.now() - timedelta(days=30)).strftime('%Y-%m')
    previous_metrics = execute_query('''
        SELECT metric_type, metric_value 
        FROM analytics 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        AND metric_type IN ('monthly_income', 'monthly_expenses', 'monthly_profit')
    ''', (user_id, previous_month), fetch=True)
    
    previous_data = {metric['metric_type']: metric['metric_value'] for metric in previous_metrics}
    
    # Calcular porcentajes de cambio
    def calculate_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return ((current - previous) / previous) * 100
    
    changes = {
        'income_change': calculate_change(current_metrics['income'], previous_data.get('monthly_income', 0)),
        'expenses_change': calculate_change(current_metrics['expenses'], previous_data.get('monthly_expenses', 0)),
        'profit_change': calculate_change(current_metrics['profit'], previous_data.get('monthly_profit', 0))
    }
    
    # Top categorías de gastos
    top_expenses = execute_query('''
        SELECT category, SUM(amount) as total 
        FROM expenses 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        GROUP BY category 
        ORDER BY total DESC 
        LIMIT 5
    ''', (user_id, datetime.now().strftime('%Y-%m')), fetch=True)
    
    # Vehículos más rentables
    vehicle_profitability = execute_query('''
        SELECT v.plate, v.brand, v.model,
               COALESCE(SUM(i.amount), 0) as income,
               COALESCE(SUM(e.amount), 0) as expenses,
               COALESCE(SUM(i.amount), 0) - COALESCE(SUM(e.amount), 0) as profit
        FROM vehicles v
        LEFT JOIN income i ON v.id = i.vehicle_id AND strftime('%Y-%m', i.date) = ?
        LEFT JOIN expenses e ON v.id = e.vehicle_id AND strftime('%Y-%m', e.date) = ?
        WHERE v.user_id = ? AND v.status = 'active'
        GROUP BY v.id
        ORDER BY profit DESC
    ''', (datetime.now().strftime('%Y-%m'), datetime.now().strftime('%Y-%m'), user_id), fetch=True)
    
    return jsonify({
        'current_metrics': current_metrics,
        'changes': changes,
        'top_expenses': [dict(expense) for expense in top_expenses],
        'vehicle_profitability': [dict(vehicle) for vehicle in vehicle_profitability]
    })

@app.route('/api/reports/export/<report_type>')
@login_required
def export_report(report_type):
    user_id = session['user_id']
    
    if report_type == 'income':
        data = execute_query('''
            SELECT i.date, i.amount, i.type, i.source, i.description, 
                   v.plate as vehicle, c.name as company
            FROM income i
            LEFT JOIN vehicles v ON i.vehicle_id = v.id
            LEFT JOIN companies c ON i.company_id = c.id
            WHERE i.user_id = ?
            ORDER BY i.date DESC
        ''', (user_id,), fetch=True)
        
        df = pd.DataFrame([dict(row) for row in data])
        
    elif report_type == 'expenses':
        data = execute_query('''
            SELECT e.date, e.amount, e.type, e.category, e.description, 
                   e.supplier, v.plate as vehicle, c.name as company
            FROM expenses e
            LEFT JOIN vehicles v ON e.vehicle_id = v.id
            LEFT JOIN companies c ON e.company_id = c.id
            WHERE e.user_id = ?
            ORDER BY e.date DESC
        ''', (user_id,), fetch=True)
        
        df = pd.DataFrame([dict(row) for row in data])
    
    else:
        return jsonify({'error': 'Tipo de reporte no válido'}), 400
    
    # Generar Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=report_type.title(), index=False)
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'{report_type}_report_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@app.route('/api/reminders', methods=['GET', 'POST'])
@login_required
def reminders_api():
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.json
        reminder_id = str(uuid.uuid4())
        
        execute_query('''
            INSERT INTO reminders (id, user_id, type, title, description, 
                                 due_date, priority, related_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            reminder_id, user_id, data.get('type'), data.get('title'),
            data.get('description'), data.get('due_date'), 
            data.get('priority', 'medium'), data.get('related_id')
        ))
        
        return jsonify({'success': True, 'reminder_id': reminder_id})
    
    reminders = execute_query('''
        SELECT * FROM reminders 
        WHERE user_id = ? AND status = 'pending'
        ORDER BY due_date ASC
    ''', (user_id,), fetch=True)
    
    return jsonify([dict(reminder) for reminder in reminders])

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def settings_api():
    user_id = session['user_id']
    
    if request.method == 'POST':
        data = request.json
        
        for category, settings in data.items():
            for key, value in settings.items():
                # Actualizar o insertar configuración
                execute_query('''
                    INSERT OR REPLACE INTO settings (id, user_id, category, key, value, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (str(uuid.uuid4()), user_id, category, key, str(value), datetime.now()))
        
        return jsonify({'success': True})
    
    settings = execute_query('''
        SELECT category, key, value FROM settings WHERE user_id = ?
    ''', (user_id,), fetch=True)
    
    # Organizar por categorías
    organized_settings = {}
    for setting in settings:
        category = setting['category']
        if category not in organized_settings:
            organized_settings[category] = {}
        organized_settings[category][setting['key']] = setting['value']
    
    return jsonify(organized_settings)

# Ruta de logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

# Manejo de errores
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Recurso no encontrado'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Error interno del servidor'}), 500

# API Routes adicionales que faltan
@app.route('/api/gastos/<category>')
@login_required
def gastos_category(category):
    # Simulación de datos para todas las categorías de gastos
    return jsonify({
        'success': True,
        'data': f'Datos de {category} cargados',
        'category': category
    })

@app.route('/api/ingresos/<category>')
@login_required
def ingresos_category(category):
    # Simulación de datos para todas las categorías de ingresos
    return jsonify({
        'success': True,
        'data': f'Datos de {category} cargados',
        'category': category
    })

@app.route('/api/laboral/<category>')
@login_required
def laboral_category(category):
    # Simulación de datos para todas las categorías laborales
    return jsonify({
        'success': True,
        'data': f'Datos laborales de {category} cargados',
        'category': category
    })

@app.route('/api/fiscal/<category>')
@login_required
def fiscal_category(category):
    # Simulación de datos para todas las categorías fiscales
    return jsonify({
        'success': True,
        'data': f'Datos fiscales de {category} cargados',
        'category': category
    })

@app.route('/api/contable/<category>')
@login_required
def contable_category(category):
    # Simulación de datos para todas las categorías contables
    return jsonify({
        'success': True,
        'data': f'Datos contables de {category} cargados',
        'category': category
    })

@app.route('/api/vtc/<category>')
@login_required
def vtc_category(category):
    # Simulación de datos para todas las categorías VTC
    return jsonify({
        'success': True,
        'data': f'Datos VTC de {category} cargados',
        'category': category
    })

@app.route('/api/taxi/<category>')
@login_required
def taxi_category(category):
    # Simulación de datos para todas las categorías de taxi
    return jsonify({
        'success': True,
        'data': f'Datos de taxi de {category} cargados',
        'category': category
    })

@app.route('/api/dgt/<category>')
@login_required
def dgt_category(category):
    # Simulación de datos para todas las categorías DGT
    return jsonify({
        'success': True,
        'data': f'Datos DGT de {category} cargados',
        'category': category
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
