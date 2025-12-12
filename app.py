# app.py - оптимизированная версия системы учета анализов Malvin Vet
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import pandas as pd
import os
import csv
from io import StringIO, BytesIO
from functools import wraps
import traceback
import io

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
    LOGIN_USERNAME = 'Malvin_42'
    LOGIN_PASSWORD = '585188'
    RESET_PASSWORD = 'FeirlyMoore_42'

# Инициализация приложения
app = Flask(__name__)
app.config.from_object(Config)

# Создаем необходимые директории
for folder in [app.config['UPLOAD_FOLDER'], 'emergency_logs']:
    os.makedirs(folder, exist_ok=True)

db = SQLAlchemy(app)

# Модели данных
class Doctor(db.Model):
    """Модель врача"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    analyses = db.relationship('Analysis', backref='doctor_ref', lazy=True, cascade='all, delete-orphan')
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
    
    doctor = db.relationship('Doctor', backref='analysis_ref')

# Утилиты
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

def login_required(f):
    """Декоратор для проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
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
        print("✅ Созданы врачи по умолчанию")

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
        
        if username == Config.LOGIN_USERNAME and password == Config.LOGIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            flash('Добро пожаловать в систему учета анализов!', 'success')
            return redirect(url_for('index'))
        
        flash('Неверные учетные данные.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы успешно вышли из системы', 'info')
    return redirect(url_for('login'))

# Главная страница
@app.route('/')
@login_required
def index():
    try:
        # Получаем параметры фильтрации
        doctor_id = request.args.get('doctor_id', type=int)
        search = request.args.get('search', '').strip()
        date_filter = request.args.get('date', '').strip()
        
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
                             now=datetime.now())
    
    except Exception as e:
        flash(f'Ошибка при загрузке данных: {str(e)}', 'danger')
        print(f"Ошибка в функции index: {str(e)}")
        traceback.print_exc()
        
        # Возвращаем значения по умолчанию при ошибке
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
                              now=datetime.now())

# Обработка анализов
@app.route('/analysis/<int:analysis_id>/mark_called', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
        csv_data = io.StringIO(decoded_content)
        
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
            messages.append(f"✅ Успешно добавлено {added_count} анализов")
        else:
            messages.append("⚠️ Не удалось добавить анализы")
        
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required 
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
@login_required
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
        
        flash(f'✅ База данных успешно сброшена! Удалено {total_analyses} анализов и {total_doctors} врачей. Добавлено {len(Config.DEFAULT_DOCTORS)} врачей по умолчанию.', 'success')
        
    except Exception as e:
        flash(f'❌ Ошибка при сбросе базы данных: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

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
    print(f"Логин: {Config.LOGIN_USERNAME}")
    print(f"Пароль: {Config.LOGIN_PASSWORD}")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)