# app.py - оптимизированная версия системы учета анализов Malvin Vet
import sys
import io

# Устанавливаем кодировку для вывода в консоль
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import os
import csv
import secrets
import re
from io import StringIO, BytesIO
from functools import wraps
import traceback
import io as io_module

# Конфигурация приложения
class Config:
    SECRET_KEY = 'malvin_vet_secret_key_2024'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///malvin_vet.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    DEFAULT_DOCTORS = [
        'Волков И.Р.',
        'Федосов М.А.', 
        'Шашурина Ю.Н.',
        'Олейник А.С.',
        'Синюков С.С.',
        'Соколова А.С.',
        'Гришина А.С.',
        'Соловьев Д.Е.',
        'Соловьева Н.И.',
        'Лочехина Е.А.',
        'Зюков И.И.',
        'Синюкова Е.В.',
        'Макаренко В.А.',
        'Без врача'
    ]
    # Обычные учетные данные
    LOGIN_USERNAME = 'Malvin_42'
    LOGIN_PASSWORD = '585188'
    RESET_PASSWORD = 'FeirlyMoore_42'
    
    # Суперадмин (единственный, с особыми правами)
    SUPER_ADMIN_USERNAME = 'Feirly_Moore'
    SUPER_ADMIN_PASSWORD = '1029384756Ravent_42'

# Инициализация приложения
app = Flask(__name__)
app.config.from_object(Config)

# Создаем необходимые директории
for folder in [app.config['UPLOAD_FOLDER'], 'emergency_logs']:
    os.makedirs(folder, exist_ok=True)

db = SQLAlchemy(app)

# Модели данных
class User(db.Model):
    """Модель пользователя"""
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # super_admin, admin, doctor, user
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

class InviteCode(db.Model):
    """Модель инвайт-кода"""
    __tablename__ = 'invite_code'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    is_used = db.Column(db.Boolean, default=False)
    used_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    used_at = db.Column(db.DateTime)
    
    created_by_user = db.relationship('User', foreign_keys=[created_by])
    used_by_user = db.relationship('User', foreign_keys=[used_by])

class Doctor(db.Model):
    """Модель врача"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Analysis(db.Model):
    """Модель анализа"""
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))  # ID пациента
    client_surname = db.Column(db.String(100), nullable=False)
    pet_name = db.Column(db.String(100), nullable=False)
    analysis_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='actual')  # actual, processed
    is_called = db.Column(db.Boolean, default=False)
    call_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    notes = db.Column(db.Text)
    
    doctor = db.relationship('Doctor', backref='analyses')

# Утилиты
def generate_invite_code(length=10):
    """Генерирует случайный инвайт-код"""
    characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(secrets.choice(characters) for _ in range(length))

def create_admin_users():
    """Создает администраторов по умолчанию если их нет"""
    try:
        # Создаем суперадмина
        super_admin = User.query.filter_by(username=Config.SUPER_ADMIN_USERNAME).first()
        if not super_admin:
            super_admin = User(
                username=Config.SUPER_ADMIN_USERNAME,
                password_hash=generate_password_hash(Config.SUPER_ADMIN_PASSWORD),
                role='super_admin',
                is_active=True
            )
            db.session.add(super_admin)
            print(f"[SUCCESS] Создан суперадмин по умолчанию: {Config.SUPER_ADMIN_USERNAME}")
        else:
            # Обновляем пароль суперадмина, если он существует
            super_admin.password_hash = generate_password_hash(Config.SUPER_ADMIN_PASSWORD)
            super_admin.role = 'super_admin'
            super_admin.is_active = True
            print(f"[SUCCESS] Обновлен суперадмин: {Config.SUPER_ADMIN_USERNAME}")
        
        # Создаем обычного админа
        admin = User.query.filter_by(username=Config.LOGIN_USERNAME).first()
        if not admin:
            admin = User(
                username=Config.LOGIN_USERNAME,
                password_hash=generate_password_hash(Config.LOGIN_PASSWORD),
                role='admin',
                is_active=True
            )
            db.session.add(admin)
            print(f"[SUCCESS] Создан администратор по умолчанию: {Config.LOGIN_USERNAME}")
        else:
            # Обновляем пароль админа, если он существует
            admin.password_hash = generate_password_hash(Config.LOGIN_PASSWORD)
            admin.role = 'admin'
            admin.is_active = True
            print(f"[SUCCESS] Обновлен администратор: {Config.LOGIN_USERNAME}")
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Ошибка при создании администраторов: {str(e)}")
        raise

def log_emergency_call(analysis):
    """Создает лог-файл с информацией о звонке"""
    today = date.today().strftime('%Y-%m-%d')
    filepath = os.path.join('emergency_logs', f'emergency_{today}.txt')
    
    log_entry = f"""
{'='*60}
ВРЕМЯ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
ВЛАДЕЛЕЦ: {analysis.client_surname}
КЛИЧКА: {analysis.pet_name}
АНАЛИЗ: {analysis.analysis_type}
ВРАЧ: {analysis.doctor.name if analysis.doctor else 'Не указан'}
ID ПАЦИЕНТА: {analysis.patient_id or 'Не указан'}
СТАТУС: Обработан
{'='*60}
"""
    
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f'Ошибка при записи лога: {e}')

# Декораторы для проверки прав
def login_required(f):
    """Декоратор для проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Декоратор для проверки прав администратора (admin или super_admin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=session.get('username')).first()
        if not user or user.role not in ['admin', 'super_admin']:
            flash('Доступ запрещен. Требуются права администратора', 'danger')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    """Декоратор для проверки прав суперадмина"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=session.get('username')).first()
        if not user or user.role != 'super_admin':
            flash('Доступ запрещен. Требуются права суперадминистратора', 'danger')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def doctor_or_admin_required(f):
    """Декоратор для проверки прав врача или администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=session.get('username')).first()
        if not user or user.role not in ['doctor', 'admin', 'super_admin']:
            flash('Доступ запрещен. Требуются права врача или администратора', 'danger')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def user_or_doctor_required(f):
    """Декоратор для проверки прав обычного пользователя или врача"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=session.get('username')).first()
        if not user or user.role not in ['user', 'doctor', 'admin', 'super_admin']:
            flash('Доступ запрещен. Требуются права пользователя или врача', 'danger')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def user_required(f):
    """Декоратор для проверки прав любого пользователя"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=session.get('username')).first()
        if not user:
            flash('Доступ запрещен. Пользователь не найден', 'danger')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def initialize_database():
    """Инициализация базы данных с начальными данными"""
    db.create_all()
    
    if Doctor.query.count() == 0:
        for doc_name in Config.DEFAULT_DOCTORS:
            doctor = Doctor(name=doc_name)
            db.session.add(doctor)
        
        db.session.commit()
        print(f"[SUCCESS] Создано {len(Config.DEFAULT_DOCTORS)} врачей по умолчанию")
    
    # Создаем администраторов если их нет
    create_admin_users()

def apply_filters(query, search_term, date_filter):
    """Применяет фильтры поиска и даты к запросу"""
    if search_term:
        search_pattern = f"%{search_term}%"
        query = query.filter(
            db.or_(
                Analysis.client_surname.ilike(search_pattern),
                Analysis.pet_name.ilike(search_pattern),
                Analysis.analysis_type.ilike(search_pattern),
                Analysis.notes.ilike(search_pattern),
                Analysis.patient_id.ilike(search_pattern)
            )
        )
    
    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%d.%m.%Y').date()
            query = query.filter(db.func.date(Analysis.created_at) == date_obj)
        except ValueError:
            flash(f'Неверный формат даты: {date_filter}. Используйте ДД.ММ.ГГГГ', 'warning')
    
    return query

def get_analysis_statistics(actual_analyses, processed_analyses, doctors):
    """Собирает статистику по анализам"""
    doctor_stats = []
    for doctor in doctors:
        doctor_actual = len([a for a in actual_analyses if a.doctor_id == doctor.id])
        doctor_processed = len([a for a in processed_analyses if a.doctor_id == doctor.id])
        doctor_total = doctor_actual + doctor_processed
        
        progress = int((doctor_processed / doctor_total * 100)) if doctor_total > 0 else 0
            
        doctor_stats.append({
            'id': doctor.id,
            'name': doctor.name,
            'actual': doctor_actual,
            'processed': doctor_processed,
            'total': doctor_total,
            'progress': progress
        })
    
    return doctor_stats

def create_redirect_url(endpoint='index', **kwargs):
    """Создает URL для редиректа с сохранением фильтров"""
    params = {}
    for key, value in kwargs.items():
        if value not in ('', None):
            params[key] = value
    return url_for(endpoint, **params) if params else url_for(endpoint)

def parse_custom_datetime(custom_date, custom_time):
    """Парсит пользовательскую дату и время"""
    if not custom_date:
        return datetime.utcnow()
    
    try:
        if custom_time:
            datetime_str = f"{custom_date} {custom_time}"
            return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        else:
            date_obj = datetime.strptime(custom_date, '%Y-%m-%d')
            return datetime.combine(date_obj, datetime.now().time())
    except ValueError:
        raise ValueError('Неверный формат даты или времени')

# Маршруты аутентификации
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password) and user.is_active:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = user.role
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Определяем тип приветствия в зависимости от роли
            role_display = {
                'super_admin': 'Суперадминистратор',
                'admin': 'Администратор',
                'doctor': 'Врач',
                'user': 'Пользователь'
            }.get(user.role, 'Пользователь')
            
            flash(f'Добро пожаловать, {role_display} {username}!', 'success')
            return redirect(url_for('index'))
        
        flash('Неверные учетные данные или учетная запись неактивна.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('logged_in'):
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()
            invite_code = request.form.get('invite_code', '').strip().upper()
            
            # Валидация
            if not all([username, password, confirm_password, invite_code]):
                flash('Заполните все поля', 'danger')
                return render_template('register.html')
            
            if password != confirm_password:
                flash('Пароли не совпадают', 'danger')
                return render_template('register.html')
            
            if len(password) < 6:
                flash('Пароль должен содержать минимум 6 символов', 'danger')
                return render_template('register.html')
            
            if len(username) < 3:
                flash('Логин должен содержать минимум 3 символа', 'danger')
                return render_template('register.html')
            
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                flash('Логин может содержать только латинские буквы, цифры и подчеркивание', 'danger')
                return render_template('register.html')
            
            # Проверка существующего пользователя
            if User.query.filter_by(username=username).first():
                flash('Пользователь с таким логином уже существует', 'danger')
                return render_template('register.html')
            
            # Проверка инвайт-кода
            invite = InviteCode.query.filter_by(code=invite_code, is_used=False).first()
            if not invite:
                flash('Неверный или уже использованный инвайт-код', 'danger')
                return render_template('register.html')
            
            if invite.expires_at and invite.expires_at < datetime.utcnow():
                flash('Срок действия инвайт-кода истек', 'danger')
                return render_template('register.html')
            
            # Создание пользователя (только обычный пользователь)
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                role='user'  # Все новые пользователи - обычные
            )
            db.session.add(user)
            db.session.flush()  # Получаем ID пользователя
            
            # Использование инвайт-кода
            invite.is_used = True
            invite.used_by = user.id
            invite.used_at = datetime.utcnow()
            
            db.session.commit()
            
            flash('Регистрация успешна! Теперь вы можете войти в систему.', 'success')
            return redirect(url_for('login'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при регистрации: {str(e)}', 'danger')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы успешно вышли из системы', 'info')
    return redirect(url_for('login'))

# Управление инвайт-кодами
@app.route('/admin/invite_codes')
@admin_required
def admin_invite_codes():
    """Страница управления инвайт-кодами"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    invite_codes = InviteCode.query.order_by(InviteCode.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin_invite_codes.html', 
                         invite_codes=invite_codes, 
                         now=datetime.utcnow())

@app.route('/admin/generate_invite', methods=['POST'])
@admin_required
def generate_invite():
    """Генерация нового инвайт-кода"""
    try:
        days_valid = request.form.get('days_valid', 7, type=int)
        quantity = request.form.get('quantity', 1, type=int)
        
        if quantity < 1 or quantity > 50:
            flash('Количество кодов должно быть от 1 до 50', 'danger')
            return redirect(url_for('admin_invite_codes'))
        
        admin_user = User.query.filter_by(username=session.get('username')).first()
        
        generated_codes = []
        for _ in range(quantity):
            code = generate_invite_code()
            
            # Проверяем уникальность
            while InviteCode.query.filter_by(code=code).first():
                code = generate_invite_code()
            
            invite = InviteCode(
                code=code,
                created_by=admin_user.id,
                expires_at=datetime.utcnow() + timedelta(days=days_valid) if days_valid > 0 else None
            )
            db.session.add(invite)
            generated_codes.append(code)
        
        db.session.commit()
        
        flash(f'Сгенерировано {quantity} инвайт-кодов', 'success')
        
        # Возвращаем список сгенерированных кодов
        session['generated_codes'] = generated_codes
        return redirect(url_for('admin_invite_codes'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при генерации кодов: {str(e)}', 'danger')
        return redirect(url_for('admin_invite_codes'))

@app.route('/admin/revoke_invite/<int:code_id>', methods=['POST'])
@admin_required
def revoke_invite(code_id):
    """Отзыв инвайт-кода"""
    try:
        invite = InviteCode.query.get_or_404(code_id)
        
        if invite.is_used:
            flash('Невозможно отозвать уже использованный код', 'warning')
        else:
            db.session.delete(invite)
            db.session.commit()
            flash('Инвайт-код успешно отозван', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при отзыве кода: {str(e)}', 'danger')
    
    return redirect(url_for('admin_invite_codes'))

# Управление пользователями
@app.route('/admin/users')
@admin_required
def admin_users():
    """Страница управления пользователями"""
    users = User.query.order_by(
        db.case(
            (User.role == 'super_admin', 1),
            (User.role == 'admin', 2),
            (User.role == 'doctor', 3),
            (User.role == 'user', 4),
            else_=5
        ),
        User.created_at.desc()
    ).all()
    
    return render_template('admin_users.html', users=users, now=datetime.utcnow())

@app.route('/admin/user/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    """Активация/деактивация пользователя"""
    try:
        current_user = User.query.filter_by(username=session.get('username')).first()
        target_user = User.query.get_or_404(user_id)
        
        if target_user.username == session.get('username'):
            flash('Нельзя отключить свою учетную запись', 'danger')
            return redirect(url_for('admin_users'))
        
        # Проверка прав
        if current_user.role == 'admin' and target_user.role in ['super_admin', 'admin']:
            flash('Администратор не может изменять статус других администраторов или суперадмина', 'danger')
            return redirect(url_for('admin_users'))
        
        target_user.is_active = not target_user.is_active
        db.session.commit()
        
        status = "активирована" if target_user.is_active else "деактивирована"
        flash(f'Учетная запись {target_user.username} {status}', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Удаление пользователя"""
    try:
        current_user = User.query.filter_by(username=session.get('username')).first()
        target_user = User.query.get_or_404(user_id)
        
        if target_user.username == session.get('username'):
            flash('Нельзя удалить свою учетную запись', 'danger')
            return redirect(url_for('admin_users'))
        
        # Проверка прав
        if current_user.role == 'admin' and target_user.role in ['super_admin', 'admin']:
            flash('Администратор не может удалять других администраторов или суперадмина', 'danger')
            return redirect(url_for('admin_users'))
        
        username = target_user.username
        db.session.delete(target_user)
        db.session.commit()
        
        flash(f'Пользователь {username} удален', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/promote', methods=['POST'])
@super_admin_required
def promote_to_admin(user_id):
    """Повышение пользователя до администратора (только для суперадмина)"""
    try:
        target_user = User.query.get_or_404(user_id)
        
        if target_user.role == 'super_admin':
            flash('Нельзя изменить роль суперадмина', 'warning')
        elif target_user.role == 'admin':
            flash('Пользователь уже является администратором', 'info')
        else:
            target_user.role = 'admin'
            db.session.commit()
            flash(f'Пользователь {target_user.username} повышен до администратора', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при изменении роли: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/demote', methods=['POST'])
@super_admin_required
def demote_to_user(user_id):
    """Понижение администратора до обычного пользователя (только для суперадмина)"""
    try:
        target_user = User.query.get_or_404(user_id)
        
        if target_user.role == 'super_admin':
            flash('Нельзя понизить суперадмина', 'warning')
        elif target_user.role == 'user':
            flash('Пользователь уже является обычным пользователем', 'info')
        else:
            target_user.role = 'user'
            db.session.commit()
            flash(f'Пользователь {target_user.username} понижен до обычного пользователя', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при изменении роли: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/make_doctor', methods=['POST'])
@super_admin_required
def make_doctor(user_id):
    """Назначение пользователя врачом (только для суперадмина)"""
    try:
        target_user = User.query.get_or_404(user_id)
        
        if target_user.role == 'super_admin':
            flash('Нельзя изменить роль суперадмина', 'warning')
        elif target_user.role == 'doctor':
            flash('Пользователь уже является врачом', 'info')
        else:
            target_user.role = 'doctor'
            db.session.commit()
            flash(f'Пользователь {target_user.username} назначен врачом', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при изменении роли: {str(e)}', 'danger')
    
    return redirect(url_for('admin_users'))

# Главная страница
@app.route('/')
@login_required
def index():
    try:
        # Получаем параметры фильтрации
        doctor_id = request.args.get('doctor_id', type=int)
        search = request.args.get('search', '').strip()
        date_filter = request.args.get('date', '').strip()
        
        # Получаем текущего пользователя
        current_user = User.query.filter_by(username=session.get('username')).first()
        
        # Получаем количество пользователей
        users_count = User.query.count()
        
        # Рассчитываем границу для архивации
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Основные запросы с учетом статусов
        base_query = Analysis.query
        if doctor_id:
            base_query = base_query.filter_by(doctor_id=doctor_id)
        
        # Неархивные анализы
        non_archive_query = base_query.filter(
            db.or_(
                Analysis.status == 'actual',
                db.and_(
                    Analysis.status == 'processed',
                    Analysis.call_date >= week_ago
                )
            )
        )
        
        # Архивные анализы
        archive_query = base_query.filter(
            db.and_(
                Analysis.status == 'processed',
                Analysis.call_date < week_ago
            )
        )
        
        # Применяем текстовый поиск и фильтр по дате
        non_archive_query = apply_filters(non_archive_query, search, date_filter)
        archive_query = apply_filters(archive_query, search, date_filter)
        
        # Получаем данные
        non_archived_analyses = non_archive_query.order_by(Analysis.created_at.desc()).all()
        archived_analyses = archive_query.order_by(Analysis.call_date.desc()).all()
        
        # Разделяем неархивные анализы
        actual_analyses = [a for a in non_archived_analyses if a.status == 'actual']
        actual_analyses.sort(key=lambda x: x.created_at, reverse=True)
        
        processed_analyses = [a for a in non_archived_analyses if a.status == 'processed']
        processed_analyses.sort(key=lambda x: x.call_date or datetime.min, reverse=True)
        
        # Статистика
        doctors = Doctor.query.order_by(Doctor.name).all()
        doctor_stats = get_analysis_statistics(actual_analyses, processed_analyses, doctors)
        
        return render_template('index.html',
                             actual_analyses=actual_analyses,
                             processed_analyses=processed_analyses,
                             archived_analyses=archived_analyses,
                             doctors=doctors,
                             doctor_stats=doctor_stats,
                             total_analyses=len(non_archived_analyses),
                             actual_count=len(actual_analyses),
                             processed_count=len(processed_analyses),
                             archived_count=len(archived_analyses),
                             selected_doctor=doctor_id,
                             search_query=search,
                             date_filter=date_filter,
                             week_ago=week_ago,
                             now=datetime.now(),
                             users_count=users_count,
                             user=current_user)
    
    except Exception as e:
        flash(f'Ошибка при загрузке данных: {str(e)}', 'danger')
        print(f"[ERROR] Ошибка в функции index: {str(e)}")
        traceback.print_exc()
        
        # Возвращаем значения по умолчанию при ошибке
        current_user = User.query.filter_by(username=session.get('username')).first() if session.get('username') else None
        users_count = User.query.count()
        
        return render_template('index.html', 
                              actual_analyses=[], 
                              processed_analyses=[], 
                              archived_analyses=[],
                              doctors=[], 
                              doctor_stats=[],
                              total_analyses=0,
                              actual_count=0,
                              processed_count=0,
                              archived_count=0,
                              selected_doctor=None,
                              search_query='',
                              date_filter='',
                              now=datetime.now(),
                              users_count=users_count,
                              user=current_user)

# Обработка анализов
@app.route('/analysis/<int:analysis_id>/mark_called', methods=['POST'])
@user_or_doctor_required  # Могут врачи и обычные пользователи
def mark_called(analysis_id):
    try:
        analysis = Analysis.query.get_or_404(analysis_id)
        
        if not analysis.is_called:
            analysis.is_called = True
            analysis.status = 'processed'
            analysis.call_date = datetime.utcnow()
            db.session.commit()
            
            log_emergency_call(analysis)
            flash(f'Анализ для {analysis.client_surname} ({analysis.pet_name}) отмечен как обработанный', 'success')
        else:
            flash('Этот анализ уже был обработан ранее', 'info')
    
    except Exception as e:
        flash(f'Ошибка при отметке анализа: {str(e)}', 'danger')
    
    return redirect(create_redirect_url(
        doctor_id=request.form.get('redirect_doctor_id', ''),
        search=request.form.get('redirect_search', ''),
        date=request.form.get('redirect_date', '')
    ))

@app.route('/analysis/add', methods=['GET', 'POST'])
@admin_required  # Только админы и суперадмины
def add_analysis():
    doctors = Doctor.query.order_by(Doctor.name).all()
    
    if request.method == 'POST':
        try:
            patient_id = request.form.get('patient_id', '').strip()
            client_surname = request.form.get('client_surname', '').strip()
            pet_name = request.form.get('pet_name', '').strip()
            analysis_type = request.form.get('analysis_type', '').strip()
            doctor_id = request.form.get('doctor_id', type=int)
            notes = request.form.get('notes', '').strip()
            custom_date = request.form.get('custom_date', '').strip()
            custom_time = request.form.get('custom_time', '').strip()
            
            # Валидация обязательных полей
            if not all([client_surname, pet_name, analysis_type]):
                flash('Заполните обязательные поля: Фамилия, Кличка, Тип анализа', 'danger')
                return render_template('add_analysis.html', doctors=doctors)
            
            doctor = Doctor.query.get(doctor_id)
            if not doctor:
                flash('Выберите врача', 'danger')
                return render_template('add_analysis.html', doctors=doctors)
            
            # Обработка даты
            try:
                created_at = parse_custom_datetime(custom_date, custom_time)
            except ValueError as e:
                flash(str(e), 'danger')
                return render_template('add_analysis.html', doctors=doctors)
            
            # Проверка дубликатов
            check_date = created_at.date()
            existing_analyses = Analysis.query.filter(
                db.and_(
                    Analysis.client_surname == client_surname,
                    Analysis.pet_name == pet_name,
                    Analysis.analysis_type == analysis_type,
                    Analysis.doctor_id == doctor.id,
                    db.func.date(Analysis.created_at) == check_date
                )
            ).all()
            
            # Проверяем точные дубликаты
            for existing in existing_analyses:
                if (existing.patient_id == patient_id and existing.notes == notes):
                    flash('Анализ с такими данными уже существует в системе', 'warning')
                    return render_template('add_analysis.html', doctors=doctors)
            
            # Создание нового анализа
            new_analysis = Analysis(
                patient_id=patient_id if patient_id else None,
                client_surname=client_surname,
                pet_name=pet_name,
                analysis_type=analysis_type,
                doctor_id=doctor_id,
                notes=notes,
                status='actual',
                is_called=False,
                created_at=created_at
            )
            
            db.session.add(new_analysis)
            db.session.commit()
            
            flash(f'Анализ успешно добавлен для {client_surname} ({pet_name})', 'success')
            
            return redirect(create_redirect_url(
                doctor_id=request.form.get('redirect_doctor_id', ''),
                search=request.form.get('redirect_search', ''),
                date=request.form.get('redirect_date', '')
            ))
        
        except Exception as e:
            flash(f'Ошибка при добавлении анализа: {str(e)}', 'danger')
    
    return render_template('add_analysis.html', doctors=doctors)

@app.route('/analysis/<int:analysis_id>/edit', methods=['GET', 'POST'])
@user_or_doctor_required  # Могут врачи и обычные пользователи
def edit_analysis(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)
    doctors = Doctor.query.order_by(Doctor.name).all()
    
    if request.method == 'POST':
        try:
            analysis.patient_id = request.form.get('patient_id', '').strip()
            analysis.client_surname = request.form.get('client_surname', '').strip()
            analysis.pet_name = request.form.get('pet_name', '').strip()
            analysis.analysis_type = request.form.get('analysis_type', '').strip()
            analysis.doctor_id = request.form.get('doctor_id', type=int)
            analysis.notes = request.form.get('notes', '').strip()
            
            db.session.commit()
            flash('Анализ успешно обновлен', 'success')
        
        except Exception as e:
            flash(f'Ошибка при обновлении анализа: {str(e)}', 'danger')
        
        return redirect(create_redirect_url(
            doctor_id=request.form.get('redirect_doctor_id', ''),
            search=request.form.get('redirect_search', ''),
            date=request.form.get('redirect_date', '')
        ))
    
    return render_template('edit_analysis.html', analysis=analysis, doctors=doctors)

@app.route('/analysis/<int:analysis_id>/delete', methods=['POST'])
@admin_required  # Только админы и суперадмины
def delete_analysis(analysis_id):
    try:
        analysis = Analysis.query.get_or_404(analysis_id)
        client_info = f"{analysis.client_surname} ({analysis.pet_name})"
        
        db.session.delete(analysis)
        db.session.commit()
        
        flash(f'Анализ для {client_info} успешно удален', 'success')
    
    except Exception as e:
        flash(f'Ошибка при удалении анализа: {str(e)}', 'danger')
    
    return redirect(create_redirect_url(
        doctor_id=request.form.get('redirect_doctor_id', ''),
        search=request.form.get('redirect_search', ''),
        date=request.form.get('redirect_date', '')
    ))

@app.route('/analysis/<int:analysis_id>/archive', methods=['POST'])
@admin_required  # Только админы и суперадмины
def archive_analysis(analysis_id):
    try:
        analysis = Analysis.query.get_or_404(analysis_id)
        
        if analysis.status == 'processed' and analysis.call_date:
            # Сохраняем оригинальную дату обработки, просто уменьшаем на 8 дней для фильтрации
            analysis.call_date = analysis.call_date - timedelta(days=8)
            db.session.commit()
            flash(f'Анализ для {analysis.client_surname} перемещен в архив', 'success')
        else:
            flash('Только обработанные анализы можно перемещать в архив', 'warning')
    
    except Exception as e:
        flash(f'Ошибка при перемещении в архив: {str(e)}', 'danger')
    
    return redirect(create_redirect_url(
        doctor_id=request.form.get('redirect_doctor_id', ''),
        search=request.form.get('redirect_search', ''),
        date=request.form.get('redirect_date', '')
    ))

@app.route('/archive_old', methods=['POST'])
@admin_required  # Только админы и суперадмины
def archive_old():
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        fresh_analyses = Analysis.query.filter(
            db.and_(
                Analysis.status == 'processed',
                Analysis.call_date >= week_ago
            )
        ).all()
        
        count = 0
        for analysis in fresh_analyses:
            # Сохраняем оригинальную дату обработки, просто уменьшаем на 8 дней для фильтрации
            analysis.call_date = analysis.call_date - timedelta(days=8)
            count += 1
        
        db.session.commit()
        flash(f'В архив перемещено {count} анализов', 'success')
    
    except Exception as e:
        flash(f'Ошибка при архивировании: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

# Загрузка CSV файлов
def validate_csv_file(file):
    """Валидация CSV файла"""
    if not file or file.filename == '':
        raise ValueError('Файл не выбран')
    
    if not file.filename.lower().endswith('.csv'):
        raise ValueError('Пожалуйста, загрузите CSV файл с расширением .csv')
    
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 10 * 1024 * 1024:
        raise ValueError('Файл слишком большой. Максимальный размер: 10MB')
    
    return True

def decode_csv_content(file_content):
    """Декодирование содержимого CSV файла с разными кодировками"""
    encodings = ['utf-8', 'cp1251', 'windows-1251', 'latin-1', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            return file_content.decode(encoding)
        except UnicodeDecodeError:
            continue
    
    raise UnicodeDecodeError('Не удалось прочитать файл. Сохраните файл в кодировке UTF-8')

def parse_creation_time(time_str, current_datetime):
    """Парсит строку времени из CSV"""
    if not time_str:
        return current_datetime
    
    formats = [
        '%d.%m.%Y %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%d/%m/%Y %H:%M',
        '%H:%M %d.%m.%Y',
        '%d.%m.%Y',
        '%Y-%m-%d %H:%M',
        '%d.%m.%Y %H:%M:%S',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    
    return current_datetime

@app.route('/upload', methods=['GET', 'POST'])
@admin_required  # Только админы и суперадмины
def upload_csv():
    if request.method == 'GET':
        return render_template('upload.html')
    
    try:
        if 'csv_file' not in request.files:
            flash('Файл не найден в запросе', 'danger')
            return redirect(url_for('upload_csv'))
        
        file = request.files['csv_file']
        validate_csv_file(file)
        
        file_content = file.read()
        if not file_content:
            flash('Файл пуст', 'danger')
            return redirect(url_for('upload_csv'))
        
        decoded_content = decode_csv_content(file_content)
        csv_data = io_module.StringIO(decoded_content)
        
        # Читаем первую строку для проверки
        first_line = csv_data.readline().strip()
        if not first_line:
            flash('CSV файл пуст', 'danger')
            return redirect(url_for('upload_csv'))
        
        csv_data.seek(0)
        csv_reader = csv.DictReader(csv_data, delimiter=',')
        
        if csv_reader.fieldnames is None:
            flash('Не удалось прочитать заголовки CSV файла', 'danger')
            return redirect(url_for('upload_csv'))
        
        # Проверяем и нормализуем колонки
        fieldnames = [col.strip() for col in csv_reader.fieldnames]
        
        required_columns = ['Врач', 'Фамилия', 'Кличка', 'Анализ']
        optional_columns = ['ID пациента', 'Время создания', 'Примечания']
        
        # Ищем колонки в файле
        found_columns = {}
        for col in required_columns + optional_columns:
            col_variants = [col, col.lower(), col.upper()]
            for variant in col_variants:
                if variant in fieldnames:
                    found_columns[col] = variant
                    break
        
        # Проверяем обязательные колонки
        missing_columns = [col for col in required_columns if col not in found_columns]
        if missing_columns:
            flash(f'Отсутствуют обязательные колонки: {", ".join(missing_columns)}', 'danger')
            flash(f'Найдены колонки: {", ".join(fieldnames)}', 'info')
            return redirect(url_for('upload_csv'))
        
        # Обрабатываем данные
        added_count = skipped_duplicates = skipped_empty = error_count = 0
        current_datetime = datetime.utcnow()
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                # Получаем данные из строки
                doctor_name = row.get(found_columns.get('Врач', ''), '').strip()
                client_surname = row.get(found_columns.get('Фамилия', ''), '').strip()
                pet_name = row.get(found_columns.get('Кличка', ''), '').strip()
                analysis_type = row.get(found_columns.get('Анализ', ''), '').strip()
                
                patient_id = row.get(found_columns.get('ID пациента', ''), '').strip() if 'ID пациента' in found_columns else ''
                time_str = row.get(found_columns.get('Время создания', ''), '').strip() if 'Время создания' in found_columns else ''
                notes = row.get(found_columns.get('Примечания', ''), '').strip() if 'Примечания' in found_columns else ''
                
                # Проверяем обязательные поля
                if not all([doctor_name, client_surname, pet_name, analysis_type]):
                    skipped_empty += 1
                    continue
                
                # Находим или создаем врача
                doctor = Doctor.query.filter_by(name=doctor_name).first()
                if not doctor:
                    doctor = Doctor(name=doctor_name)
                    db.session.add(doctor)
                    db.session.flush()
                
                # Обрабатываем время создания
                creation_time = parse_creation_time(time_str, current_datetime)
                
                # Проверяем дубликаты
                check_date = creation_time.date()
                existing_analyses = Analysis.query.filter(
                    db.and_(
                        Analysis.client_surname == client_surname,
                        Analysis.pet_name == pet_name,
                        Analysis.analysis_type == analysis_type,
                        Analysis.doctor_id == doctor.id,
                        db.func.date(Analysis.created_at) == check_date
                    )
                ).all()
                
                # Проверяем точные дубликаты
                is_duplicate = any(
                    existing.patient_id == patient_id and existing.notes == notes
                    for existing in existing_analyses
                )
                
                if is_duplicate:
                    skipped_duplicates += 1
                    continue
                
                # Создаем новый анализ
                new_analysis = Analysis(
                    patient_id=patient_id if patient_id else None,
                    client_surname=client_surname,
                    pet_name=pet_name,
                    analysis_type=analysis_type,
                    doctor_id=doctor.id,
                    notes=notes,
                    status='actual',
                    is_called=False,
                    created_at=creation_time,
                    updated_at=creation_time
                )
                
                db.session.add(new_analysis)
                added_count += 1
                
                if added_count % 50 == 0:
                    db.session.commit()
            
            except Exception as e:
                error_count += 1
                continue
        
        db.session.commit()
        
        # Формируем сообщение об успехе
        messages = []
        if added_count > 0:
            messages.append(f"[SUCCESS] Успешно добавлено {added_count} анализов")
        else:
            messages.append("[WARNING] Не удалось добавить анализы")
        
        if skipped_duplicates > 0:
            messages.append(f"пропущено {skipped_duplicates} дубликатов")
        if skipped_empty > 0:
            messages.append(f"пропущено {skipped_empty} строк с пустыми полями")
        if error_count > 0:
            messages.append(f"ошибок: {error_count}")
        
        flash('. '.join(messages), 'success' if added_count > 0 else 'warning')
        return redirect(url_for('index'))
    
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('upload_csv'))
    except Exception as e:
        flash(f'Ошибка при обработке CSV файла: {str(e)}', 'danger')
        return redirect(url_for('upload_csv'))

# Логи
@app.route('/logs')
@user_or_doctor_required  # Могут все авторизованные пользователи
def view_logs():
    log_files = []
    logs_dir = 'emergency_logs'
    
    if os.path.exists(logs_dir):
        for filename in sorted(os.listdir(logs_dir), reverse=True):
            if filename.startswith('emergency_') and filename.endswith('.txt'):
                filepath = os.path.join(logs_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    record_count = content.count('ВЛАДЕЛЕЦ:')
                    
                    log_files.append({
                        'filename': filename,
                        'date': filename.replace('emergency_', '').replace('.txt', ''),
                        'content': content,
                        'record_count': record_count,
                        'size': os.path.getsize(filepath)
                    })
                except Exception as e:
                    print(f'Ошибка чтения файла {filename}: {e}')
    
    return render_template('logs.html', log_files=log_files)

# Экспорт данных
@app.route('/export')
@user_or_doctor_required  # Могут все авторизованные пользователи
def export_data():
    try:
        analyses = Analysis.query.order_by(Analysis.created_at.desc()).all()
        
        output = StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        writer.writerow([
            'ID', 'ID пациента', 'Фамилия владельца', 'Кличка', 'Тип анализа',
            'Статус', 'Обработан', 'Дата обработки', 'Врач',
            'Примечания', 'Дата создания', 'Дата обновления'
        ])
        
        for analysis in analyses:
            writer.writerow([
                analysis.id,
                analysis.patient_id or '',
                analysis.client_surname,
                analysis.pet_name,
                analysis.analysis_type,
                analysis.status,
                'Да' if analysis.is_called else 'Нет',
                analysis.call_date.strftime('%d.%m.%Y %H:%M') if analysis.call_date else '',
                analysis.doctor.name if analysis.doctor else '',
                analysis.notes or '',
                analysis.created_at.strftime('%d.%m.%Y %H:%M'),
                analysis.updated_at.strftime('%d.%m.%Y %H:%M')
            ])
        
        output.seek(0)
        
        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    except Exception as e:
        flash(f'Ошибка при экспорте данных: {str(e)}', 'danger')
        return redirect(url_for('index'))

# API
@app.route('/api/stats')
@user_or_doctor_required  # Могут все авторизованные пользователи
def api_stats():
    try:
        total = Analysis.query.count()
        actual = Analysis.query.filter_by(status='actual').count()
        processed = Analysis.query.filter_by(status='processed').count()
        
        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'actual': actual,
                'processed': processed,
                'actual_percentage': int((actual / total * 100)) if total > 0 else 0
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Управление врачами
@app.route('/doctor/add', methods=['POST'])
@admin_required  # Только админы и суперадмины
def add_doctor():
    try:
        name = request.form.get('name', '').strip()
        
        if not name:
            flash('Введите имя врача', 'danger')
            return redirect(url_for('index'))
        
        existing = Doctor.query.filter_by(name=name).first()
        if existing:
            flash('Врач с таким именем уже существует', 'warning')
            return redirect(url_for('index'))
        
        doctor = Doctor(name=name)
        db.session.add(doctor)
        db.session.commit()
        
        flash(f'Врач {name} успешно добавлен', 'success')
    
    except Exception as e:
        flash(f'Ошибка при добавлении врача: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

# Управление базой данных
@app.route('/reset_all')
@admin_required  # Только админы и суперадмины
def reset_all():
    try:
        analyses = Analysis.query.all()
        for analysis in analyses:
            analysis.status = 'actual'
            analysis.is_called = False
            analysis.call_date = None
        
        db.session.commit()
        flash('Все анализы сброшены в статус "Актуальные"', 'info')
    
    except Exception as e:
        flash(f'Ошибка при сбросе: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

@app.route('/reset_database', methods=['POST'])
@super_admin_required  # Только суперадмин
def reset_database():
    try:
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        confirmation = request.form.get('confirmation', '').strip().lower()
        
        if password != Config.RESET_PASSWORD:
            flash('Неверный пароль', 'danger')
            return redirect(url_for('index'))
        
        if password != confirm_password:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('index'))
        
        if confirmation != 'сбросить базу данных':
            flash('Неверное подтверждение действия', 'danger')
            return redirect(url_for('index'))
        
        # Получаем статистику перед удалением
        total_analyses = Analysis.query.count()
        total_doctors = Doctor.query.count()
        
        # Удаляем все данные
        Analysis.query.delete()
        Doctor.query.delete()
        
        # Восстанавливаем врачей по умолчанию
        for doc_name in Config.DEFAULT_DOCTORS:
            doctor = Doctor(name=doc_name)
            db.session.add(doctor)
        
        db.session.commit()
        
        flash(f'[SUCCESS] База данных успешно сброшена! Удалено {total_analyses} анализов и {total_doctors} врачей. Добавлено {len(Config.DEFAULT_DOCTORS)} врачей по умолчанию.', 'success')
        
    except Exception as e:
        flash(f'[ERROR] Ошибка при сбросе базы данных: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

@app.route('/reset_database_page')
@super_admin_required  # Только суперадмин
def reset_database_page():
    """Страница для сброса базы данных"""
    current_user = User.query.filter_by(username=session.get('username')).first()
    total_analyses = Analysis.query.count()
    
    # Подсчет архивных анализов
    week_ago = datetime.utcnow() - timedelta(days=7)
    archived_count = Analysis.query.filter(
        db.and_(
            Analysis.status == 'processed',
            Analysis.call_date < week_ago
        )
    ).count()
    
    doctors_count = Doctor.query.count()
    
    return render_template('reset_database.html', 
                         user=current_user,
                         total_analyses=total_analyses,
                         archived_count=archived_count,
                         doctors_count=doctors_count)

# Маршрут для пересоздания базы данных (отладка)
@app.route('/reset_and_recreate', methods=['GET'])
def reset_and_recreate():
    """Сброс и пересоздание базы данных (для отладки)"""
    try:
        # Удаляем все таблицы
        db.drop_all()
        print("[INFO] Все таблицы удалены")
        
        # Создаем все таблицы заново
        db.create_all()
        print("[INFO] Все таблицы созданы заново")
        
        # Создаем врачей по умолчанию
        if Doctor.query.count() == 0:
            for doc_name in Config.DEFAULT_DOCTORS:
                doctor = Doctor(name=doc_name)
                db.session.add(doctor)
            db.session.commit()
            print(f"[SUCCESS] Создано {len(Config.DEFAULT_DOCTORS)} врачей по умолчанию")
        
        # Создаем администраторов
        create_admin_users()
        
        return jsonify({
            'success': True,
            'message': 'База данных успешно пересоздана',
            'super_admin': Config.SUPER_ADMIN_USERNAME,
            'admin': Config.LOGIN_USERNAME
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Обработчики ошибок
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# Запуск приложения
if __name__ == '__main__':
    with app.app_context():
        initialize_database()
    
    print("=" * 60)
    print("Система учета анализов Malvin Vet")
    print("=" * 60)
    print("Сервер запущен: http://localhost:5000")
    print("Учетные данные:")
    print(f"  Суперадмин: {Config.SUPER_ADMIN_USERNAME}")
    print(f"  Пароль суперадмина: {Config.SUPER_ADMIN_PASSWORD}")
    print(f"  Администратор: {Config.LOGIN_USERNAME}")
    print(f"  Пароль администратора: {Config.LOGIN_PASSWORD}")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)