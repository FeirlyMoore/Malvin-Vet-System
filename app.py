# app.py - полная исправленная версия с фильтром по дате, новой логикой загрузки CSV и архивацией
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
import pandas as pd
import os
import csv
from io import StringIO, BytesIO
from functools import wraps
import traceback

app = Flask(__name__)
app.secret_key = 'malvin_vet_secret_key_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///malvin_vet.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Создаем папки
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('emergency_logs', exist_ok=True)

db = SQLAlchemy(app)

# Модели
class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    analyses = db.relationship('Analysis', backref='doctor_ref', lazy=True, cascade='all, delete-orphan')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50))  # Новое поле: ID пациента
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

# Создаем таблицы и начальные данные
with app.app_context():
    db.create_all()
    
    # Добавляем врачей если их нет
    if Doctor.query.count() == 0:
        initial_doctors = [
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
        
        for doc_name in initial_doctors:
            doctor = Doctor(name=doc_name)
            db.session.add(doctor)
        
        db.session.commit()
        print("✅ Созданы врачи по умолчанию")

# Декоратор для проверки авторизации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Пожалуйста, войдите в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Главная страница - логин
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if username == 'Malvin_42' and password == '585188':
            session['logged_in'] = True
            session['username'] = username
            flash('Добро пожаловать в систему учета анализов!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверные учетные данные.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы успешно вышли из системы', 'info')
    return redirect(url_for('login'))

# Главная страница - список анализов
@app.route('/')
@login_required
def index():
    try:
        # Получаем фильтры
        doctor_id = request.args.get('doctor_id', type=int)
        search = request.args.get('search', '').strip()
        date_filter = request.args.get('date', '').strip()
        
        # Рассчитываем дату недельной давности для архива
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Базовый запрос для НЕАРХИВНЫХ анализов (актуальные + свежие обработанные)
        query = Analysis.query.filter(
            db.or_(
                Analysis.status == 'actual',
                db.and_(
                    Analysis.status == 'processed',
                    Analysis.call_date >= week_ago
                )
            )
        )
        
        # Отдельный запрос для АРХИВНЫХ анализов (обработанные старше 7 дней)
        archive_query = Analysis.query.filter(
            db.and_(
                Analysis.status == 'processed',
                Analysis.call_date < week_ago
            )
        )
        
        # Применяем фильтры врача к основному запросу
        if doctor_id:
            query = query.filter_by(doctor_id=doctor_id)
        
        # Применяем фильтры врача к архивному запросу
        if doctor_id:
            archive_query = archive_query.filter_by(doctor_id=doctor_id)
        
        # Применяем поиск по тексту к основному запросу
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    Analysis.client_surname.ilike(search_term),
                    Analysis.pet_name.ilike(search_term),
                    Analysis.analysis_type.ilike(search_term),
                    Analysis.notes.ilike(search_term),
                    Analysis.patient_id.ilike(search_term)
                )
            )
        
        # Применяем поиск по тексту к архивному запросу
        if search:
            search_term = f"%{search}%"
            archive_query = archive_query.filter(
                db.or_(
                    Analysis.client_surname.ilike(search_term),
                    Analysis.pet_name.ilike(search_term),
                    Analysis.analysis_type.ilike(search_term),
                    Analysis.notes.ilike(search_term),
                    Analysis.patient_id.ilike(search_term)
                )
            )
        
        # Применяем фильтр по дате создания к основному запросу
        if date_filter:
            try:
                date_obj = datetime.strptime(date_filter, '%d.%m.%Y').date()
                query = query.filter(db.func.date(Analysis.created_at) == date_obj)
            except ValueError:
                flash(f'Неверный формат даты: {date_filter}. Используйте ДД.ММ.ГГГГ', 'warning')
        
        # Применяем фильтр по дате создания к архивному запросу
        if date_filter:
            try:
                date_obj = datetime.strptime(date_filter, '%d.%m.%Y').date()
                archive_query = archive_query.filter(db.func.date(Analysis.created_at) == date_obj)
            except ValueError:
                # Игнорируем, так как уже было предупреждение
                pass
        
        # Получаем НЕАРХИВНЫЕ анализы согласно фильтрам
        non_archived_analyses = query.order_by(Analysis.created_at.desc()).all()
        
        # Получаем АРХИВНЫЕ анализы согласно фильтрам
        archived_analyses = archive_query.order_by(Analysis.call_date.desc()).all()
        
        # Разделяем неархивные на актуальные и свежие обработанные
        actual_analyses = [a for a in non_archived_analyses if a.status == 'actual']
        actual_analyses.sort(key=lambda x: x.created_at, reverse=True)
        
        # Свежие обработанные (менее 7 дней) - сортируем по дате обработки
        processed_analyses = [a for a in non_archived_analyses if a.status == 'processed']
        processed_analyses.sort(key=lambda x: x.call_date or datetime.min, reverse=True)
        
        # Архивные - сортируем по дате обработки
        archived_analyses.sort(key=lambda x: x.call_date or datetime.min, reverse=True)
        
        # Для обратной совместимости
        analyses = non_archived_analyses
        
        # Получаем всех врачей для фильтра
        doctors = Doctor.query.order_by(Doctor.name).all()
        
        # Статистика (только по НЕАРХИВНЫМ анализам)
        total_non_archived = len(non_archived_analyses)
        actual_count = len(actual_analyses)
        processed_fresh_count = len(processed_analyses)
        archived_count = len(archived_analyses)
        
        # Статистика по врачам (только по неархивным)
        doctor_stats = []
        for doctor in doctors:
            # Актуальные
            doctor_actual = len([a for a in actual_analyses if a.doctor_id == doctor.id])
            # Свежие обработанные
            doctor_processed_fresh = len([a for a in processed_analyses if a.doctor_id == doctor.id])
            doctor_total = doctor_actual + doctor_processed_fresh
            
            if doctor_total > 0:
                progress = int((doctor_processed_fresh / doctor_total) * 100)
            else:
                progress = 0
                
            doctor_stats.append({
                'id': doctor.id,
                'name': doctor.name,
                'actual': doctor_actual,
                'processed': doctor_processed_fresh,
                'total': doctor_total,
                'progress': progress
            })

        now = datetime.now()
        
        return render_template('index.html',
                             analyses=analyses,
                             actual_analyses=actual_analyses,      # Только актуальные
                             processed_analyses=processed_analyses, # Свежие обработанные (<7 дней)
                             archived_analyses=archived_analyses,   # Архивные (>7 дней)
                             doctors=doctors,
                             doctor_stats=doctor_stats,
                             total_analyses=total_non_archived,    # Только неархивные
                             actual_count=actual_count,
                             processed_count=processed_fresh_count, # Только свежие обработанные
                             archived_count=archived_count,         # Количество архивных
                             selected_doctor=doctor_id,
                             search_query=search,
                             date_filter=date_filter,
                             week_ago=week_ago,
                             now=now)
    
    except Exception as e:
        flash(f'Ошибка при загрузке данных: {str(e)}', 'danger')
        print(f"Ошибка в функции index: {str(e)}")
        traceback.print_exc()
        
        # Возвращаем значения по умолчанию при ошибке
        return render_template('index.html', 
                              analyses=[], 
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

def log_emergency_call(analysis):
    """Создает лог-файл с информацией о звонке"""
    today = date.today().strftime('%Y-%m-%d')
    filename = f'emergency_{today}.txt'
    filepath = os.path.join('emergency_logs', filename)
    
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

# Отметить анализ как обработанный
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
            
            # Логируем в emergency файл
            log_emergency_call(analysis)
            
            flash(f'Анализ для {analysis.client_surname} ({analysis.pet_name}) отмечен как обработанный', 'success')
        else:
            flash('Этот анализ уже был обработан ранее', 'info')

    except Exception as e:
        flash(f'Ошибка при отметке анализа: {str(e)}', 'danger')
    
    # Получаем параметры редиректа из формы
    doctor_id = request.form.get('redirect_doctor_id', '')
    search = request.form.get('redirect_search', '')
    date_filter = request.form.get('redirect_date', '')
    
    # Формируем URL с сохранением фильтров
    redirect_url = url_for('index',
                          doctor_id=doctor_id if doctor_id else None,
                          search=search if search else None,
                          date=date_filter if date_filter else None)
    return redirect(redirect_url)

# Добавить новый анализ
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
            
            if not client_surname or not pet_name or not analysis_type:
                flash('Заполните обязательные поля: Фамилия, Кличка, Тип анализа', 'danger')
                return render_template('add_analysis.html', doctors=doctors)
            
            # Проверяем врача
            doctor = Doctor.query.get(doctor_id)
            if not doctor:
                flash('Выберите врача', 'danger')
                return render_template('add_analysis.html', doctors=doctors)
            
            # Обрабатываем дату и время
            created_at = datetime.utcnow()
            if custom_date:
                try:
                    if custom_time:
                        datetime_str = f"{custom_date} {custom_time}"
                        created_at = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
                    else:
                        date_obj = datetime.strptime(custom_date, '%Y-%m-%d')
                        created_at = datetime.combine(date_obj, datetime.now().time())
                except ValueError:
                    flash('Неверный формат даты или времени', 'danger')
                    return render_template('add_analysis.html', doctors=doctors)
            
            # Проверяем на дубликат среди всех анализов
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
            
            # Проверяем, есть ли точный дубликат
            is_duplicate = False
            for existing_analysis in existing_analyses:
                if (existing_analysis.patient_id == patient_id and
                    existing_analysis.notes == notes):
                    is_duplicate = True
                    break
            
            if is_duplicate:
                flash('Анализ с такими данными уже существует в системе', 'warning')
                return render_template('add_analysis.html', doctors=doctors)
            
            # Создаем анализ
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
            
            # Получаем параметры редиректа из формы
            redirect_doctor_id = request.form.get('redirect_doctor_id', '')
            redirect_search = request.form.get('redirect_search', '')
            redirect_date = request.form.get('redirect_date', '')
            
            # Формируем URL с сохранением фильтров
            redirect_url = url_for('index',
                                  doctor_id=redirect_doctor_id if redirect_doctor_id else None,
                                  search=redirect_search if redirect_search else None,
                                  date=redirect_date if redirect_date else None)
            return redirect(redirect_url)
        
        except Exception as e:
            flash(f'Ошибка при добавлении анализа: {str(e)}', 'danger')
    
    return render_template('add_analysis.html', doctors=doctors)

# Редактировать анализ
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
        
        # Получаем параметры редиректа из формы
        doctor_id = request.form.get('redirect_doctor_id', '')
        search = request.form.get('redirect_search', '')
        date_filter = request.form.get('redirect_date', '')
        
        # Формируем URL с сохранением фильтров
        redirect_url = url_for('index',
                              doctor_id=doctor_id if doctor_id else None,
                              search=search if search else None,
                              date=date_filter if date_filter else None)
        return redirect(redirect_url)
    
    return render_template('edit_analysis.html', analysis=analysis, doctors=doctors)

# Удалить анализ
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
    
    # Получаем параметры редиректа из формы
    doctor_id = request.form.get('redirect_doctor_id', '')
    search = request.form.get('redirect_search', '')
    date_filter = request.form.get('redirect_date', '')
    
    # Формируем URL с сохранением фильтров
    redirect_url = url_for('index',
                          doctor_id=doctor_id if doctor_id else None,
                          search=search if search else None,
                          date=date_filter if date_filter else None)
    return redirect(redirect_url)

# Принудительное перемещение анализа в архив
@app.route('/analysis/<int:analysis_id>/archive', methods=['POST'])
@login_required
def archive_analysis(analysis_id):
    try:
        analysis = Analysis.query.get_or_404(analysis_id)
        
        if analysis.status == 'processed' and analysis.call_date:
            # Устанавливаем старую дату обработки (имитируем архив)
            analysis.call_date = analysis.call_date - timedelta(days=8)
            db.session.commit()
            flash(f'Анализ для {analysis.client_surname} перемещен в архив', 'success')
        else:
            flash('Только обработанные анализы можно перемещать в архив', 'warning')
    
    except Exception as e:
        flash(f'Ошибка при перемещении в архив: {str(e)}', 'danger')
    
    # Сохраняем фильтры
    doctor_id = request.form.get('redirect_doctor_id', '')
    search = request.form.get('redirect_search', '')
    date_filter = request.form.get('redirect_date', '')
    
    redirect_url = url_for('index',
                          doctor_id=doctor_id if doctor_id else None,
                          search=search if search else None,
                          date=date_filter if date_filter else None)
    return redirect(redirect_url)

# Массовое архивирование старых записей
@app.route('/archive_old', methods=['POST'])
@login_required
def archive_old():
    try:
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Находим свежие обработанные анализы (меньше 7 дней)
        fresh_analyses = Analysis.query.filter(
            db.and_(
                Analysis.status == 'processed',
                Analysis.call_date >= week_ago
            )
        ).all()
        
        count = 0
        for analysis in fresh_analyses:
            # Устанавливаем старую дату (имитация архива)
            analysis.call_date = analysis.call_date - timedelta(days=8)
            count += 1
        
        db.session.commit()
        flash(f'В архив перемещено {count} анализов', 'success')
    
    except Exception as e:
        flash(f'Ошибка при архивировании: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

# ЗАГРУЗКА CSV - ОБНОВЛЕННАЯ ВЕРСИЯ С ID ПАЦИЕНТА И ВРЕМЕНЕМ
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_csv():
    if request.method == 'GET':
        return render_template('upload.html')
    
    if request.method == 'POST':
        try:
            # Проверяем наличие файла в запросе
            if 'csv_file' not in request.files:
                flash('Файл не найден в запросе', 'danger')
                return redirect(url_for('upload_csv'))
            
            file = request.files['csv_file']
            
            # Проверяем, выбран ли файл
            if file.filename == '' or file.filename is None:
                flash('Файл не выбран', 'danger')
                return redirect(url_for('upload_csv'))
            
            # Проверяем расширение файла
            if not file.filename.lower().endswith('.csv'):
                flash('Пожалуйста, загрузите CSV файл с расширением .csv', 'danger')
                return redirect(url_for('upload_csv'))
            
            # Проверяем размер файла (макс 10MB)
            file.seek(0, 2)  # Переходим в конец файла
            file_size = file.tell()  # Получаем размер
            file.seek(0)  # Возвращаемся в начало
            
            if file_size > 10 * 1024 * 1024:  # 10MB
                flash('Файл слишком большой. Максимальный размер: 10MB', 'danger')
                return redirect(url_for('upload_csv'))
            
            # Читаем содержимое файла
            import io
            file_content = file.read()
            
            if not file_content:
                flash('Файл пуст', 'danger')
                return redirect(url_for('upload_csv'))
            
            # Пробуем разные кодировки
            encodings = ['utf-8', 'cp1251', 'windows-1251', 'latin-1', 'iso-8859-1']
            decoded_content = None
            
            for encoding in encodings:
                try:
                    decoded_content = file_content.decode(encoding)
                    print(f"Файл прочитан с кодировкой: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if decoded_content is None:
                flash('Не удалось прочитать файл. Сохраните файл в кодировке UTF-8', 'danger')
                return redirect(url_for('upload_csv'))
            
            # Обрабатываем CSV
            import csv
            csv_data = io.StringIO(decoded_content)
            
            # Читаем первую строку для проверки
            first_line = csv_data.readline().strip()
            if not first_line:
                flash('CSV файл пуст', 'danger')
                return redirect(url_for('upload_csv'))
            
            # Возвращаемся в начало файла
            csv_data.seek(0)
            
            # Читаем CSV
            csv_reader = csv.DictReader(csv_data, delimiter=',')
            
            # Проверяем заголовки
            if csv_reader.fieldnames is None:
                flash('Не удалось прочитать заголовки CSV файла', 'danger')
                return redirect(url_for('upload_csv'))
            
            # Нормализуем названия колонок
            fieldnames = [col.strip() for col in csv_reader.fieldnames]
            
            # Проверяем обязательные колонки (старые)
            required_columns = ['Врач', 'Фамилия', 'Кличка', 'Анализ']
            
            # Новые необязательные колонки
            optional_columns = ['ID пациента', 'Время создания']
            
            # Все возможные колонки
            all_columns = required_columns + optional_columns
            
            # Ищем колонки в файле (разные варианты написания)
            found_columns = {}
            for col in all_columns:
                col_variants = [col, col.lower(), col.upper()]
                for variant in col_variants:
                    if variant in fieldnames:
                        found_columns[col] = variant
                        break
            
            # Проверяем обязательные колонки
            missing_columns = []
            for col in required_columns:
                if col not in found_columns:
                    missing_columns.append(col)
            
            if missing_columns:
                flash(f'Отсутствуют обязательные колонки: {", ".join(missing_columns)}', 'danger')
                flash(f'Найдены колонки: {", ".join(fieldnames)}', 'info')
                return redirect(url_for('upload_csv'))
            
            # Обрабатываем данные
            added_count = 0
            skipped_duplicates = 0
            skipped_empty = 0
            error_count = 0
            
            # Получаем текущую дату и время для использования по умолчанию
            current_datetime = datetime.utcnow()
            
            for row_num, row in enumerate(csv_reader, start=2):  # start=2 (заголовки - строка 1)
                try:
                    # Получаем данные из строки с учетом разных вариантов названий колонок
                    doctor_name = ''
                    client_surname = ''
                    pet_name = ''
                    analysis_type = ''
                    patient_id = ''
                    creation_time = None
                    
                    # Ищем данные в разных вариантах колонок
                    # Врач
                    if 'Врач' in found_columns:
                        doctor_name = str(row[found_columns['Врач']]).strip() if row.get(found_columns['Врач']) else ''
                    
                    # Фамилия
                    if 'Фамилия' in found_columns:
                        client_surname = str(row[found_columns['Фамилия']]).strip() if row.get(found_columns['Фамилия']) else ''
                    
                    # Кличка
                    if 'Кличка' in found_columns:
                        pet_name = str(row[found_columns['Кличка']]).strip() if row.get(found_columns['Кличка']) else ''
                    
                    # Анализ
                    if 'Анализ' in found_columns:
                        analysis_type = str(row[found_columns['Анализ']]).strip() if row.get(found_columns['Анализ']) else ''
                    
                    # ID пациента (необязательное поле)
                    if 'ID пациента' in found_columns and found_columns['ID пациента'] in row:
                        patient_id = str(row[found_columns['ID пациента']]).strip()
                    
                    # Время создания (необязательное поле)
                    if 'Время создания' in found_columns and found_columns['Время создания'] in row:
                        time_str = str(row[found_columns['Время создания']]).strip()
                        if time_str:
                            try:
                                # Пробуем разные форматы времени
                                formats = [
                                    '%d.%m.%Y %H:%M',    # 25.03.2024 14:30
                                    '%Y-%m-%d %H:%M:%S', # 2024-03-25 14:30:00
                                    '%d/%m/%Y %H:%M',    # 25/03/2024 14:30
                                    '%H:%M %d.%m.%Y',    # 14:30 25.03.2024
                                    '%d.%m.%Y',          # 25.03.2024 (только дата)
                                    '%Y-%m-%d %H:%M',    # 2024-03-25 14:30
                                    '%d.%m.%Y %H:%M:%S', # 25.03.2024 14:30:00
                                ]
                                
                                for fmt in formats:
                                    try:
                                        creation_time = datetime.strptime(time_str, fmt)
                                        break
                                    except ValueError:
                                        continue
                                
                                # Если не распарсилось, используем текущее время
                                if not creation_time:
                                    creation_time = current_datetime
                                    print(f"Строка {row_num}: не удалось распарсить время '{time_str}', используется текущее время")
                            except Exception as e:
                                print(f"Строка {row_num}: ошибка при парсинге времени: {e}")
                                creation_time = current_datetime
                    
                    # Если время не указано, используем текущее
                    if not creation_time:
                        creation_time = current_datetime
                    
                    # Проверяем, что все обязательные поля заполнены
                    if not doctor_name or not client_surname or not pet_name or not analysis_type:
                        print(f"Строка {row_num}: пропущена - не все обязательные поля заполнены")
                        skipped_empty += 1
                        continue
                    
                    # Находим или создаем врача
                    doctor = Doctor.query.filter_by(name=doctor_name).first()
                    if not doctor:
                        doctor = Doctor(name=doctor_name)
                        db.session.add(doctor)
                        db.session.flush()  # Получаем ID без коммита
                    
                    # Подготавливаем данные для проверки дубликатов
                    check_date = creation_time.date()  # Только дата для проверки дубликатов
                    
                    # Проверяем на дубликаты среди ВСЕХ анализов (и актуальных, и обработанных)
                    existing_analyses = Analysis.query.filter(
                        db.and_(
                            Analysis.client_surname == client_surname,
                            Analysis.pet_name == pet_name,
                            Analysis.analysis_type == analysis_type,
                            Analysis.doctor_id == doctor.id,
                            db.func.date(Analysis.created_at) == check_date
                        )
                    ).all()
                    
                    # Получаем примечания
                    notes = str(row.get('Примечания', '')).strip()
                    
                    # Проверяем, есть ли точный дубликат (все поля совпадают)
                    is_duplicate = False
                    for existing_analysis in existing_analyses:
                        # Сравниваем все поля
                        if (existing_analysis.patient_id == patient_id and
                            existing_analysis.notes == notes):
                            is_duplicate = True
                            break
                    
                    if is_duplicate:
                        print(f"Строка {row_num}: пропущена - точный дубликат найден")
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
                    
                    # Коммитим каждые 50 записей
                    if added_count % 50 == 0:
                        db.session.commit()
                        print(f"Добавлено {added_count} записей...")
                    
                except Exception as e:
                    print(f"Ошибка в строке {row_num}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    error_count += 1
                    continue
            
            # Финальный коммит
            db.session.commit()
            
            # Формируем сообщение об успехе
            if added_count > 0:
                message = f"✅ Успешно добавлено {added_count} анализов"
                if skipped_duplicates > 0:
                    message += f", пропущено {skipped_duplicates} дубликатов"
                if skipped_empty > 0:
                    message += f", пропущено {skipped_empty} строк с пустыми полями"
                if error_count > 0:
                    message += f", ошибок: {error_count}"
                flash(message, 'success')
            else:
                message = "⚠️ Не удалось добавить анализы"
                if skipped_duplicates > 0:
                    message += f". Пропущено {skipped_duplicates} дубликатов"
                if skipped_empty > 0:
                    message += f". Пропущено {skipped_empty} строк с пустыми полями"
                if error_count > 0:
                    message += f". Ошибок: {error_count}"
                flash(message, 'warning')
            
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f'Ошибка при обработке запроса: {str(e)}', 'danger')
            import traceback
            traceback.print_exc()
            return redirect(url_for('upload_csv'))
    
    return redirect(url_for('upload_csv'))

# Просмотр логов
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
                    
                    # Подсчитываем количество записей
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
        
        # Создаем CSV в памяти
        output = StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        # Заголовки
        writer.writerow([
            'ID', 'ID пациента', 'Фамилия владельца', 'Кличка', 'Тип анализа',
            'Статус', 'Обработан', 'Дата обработки', 'Врач',
            'Примечания', 'Дата создания', 'Дата обновления'
        ])
        
        # Данные
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
        
        # Возвращаем файл
        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    except Exception as e:
        flash(f'Ошибка при экспорте данных: {str(e)}', 'danger')
        return redirect(url_for('index'))

# API для статистики
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

# Добавить врача
@app.route('/doctor/add', methods=['POST'])
@login_required
def add_doctor():
    try:
        name = request.form.get('name', '').strip()
        
        if not name:
            flash('Введите имя врача', 'danger')
            return redirect(url_for('index'))
        
        # Проверяем, нет ли уже такого врача
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

# Сбросить все анализы в актуальные (для тестирования)
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

# Сброс базы данных с подтверждением по паролю
@app.route('/reset_database', methods=['POST'])
@login_required
def reset_database():
    try:
        # Получаем пароль из формы
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        confirmation = request.form.get('confirmation', '').strip().lower()
        
        # Проверяем пароль
        if password != 'FeirlyMoore_42':
            flash('Неверный пароль', 'danger')
            return redirect(url_for('index'))
        
        # Проверяем подтверждение пароля
        if password != confirm_password:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('index'))
        
        # Проверяем текстовое подтверждение
        if confirmation != 'сбросить базу данных':
            flash('Неверное подтверждение действия', 'danger')
            return redirect(url_for('index'))
        
        # Получаем статистику перед удалением
        total_analyses = Analysis.query.count()
        total_doctors = Doctor.query.count()
        
        # Удаляем все анализы
        Analysis.query.delete()
        
        # Удаляем всех врачей (кроме предустановленных, которые добавятся снова)
        Doctor.query.delete()
        
        # Добавляем врачей по умолчанию
        initial_doctors = [
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
        
        for doc_name in initial_doctors:
            doctor = Doctor(name=doc_name)
            db.session.add(doctor)
        
        db.session.commit()
        
        flash(f'✅ База данных успешно сброшена! Удалено {total_analyses} анализов и {total_doctors} врачей. Добавлено 14 врачей по умолчанию.', 'success')
        
    except Exception as e:
        flash(f'❌ Ошибка при сбросе базы данных: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

# Обработка 404 ошибок
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

# Обработка 500 ошибок  
@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    print("=" * 60)
    print("Система учета анализов Malvin Vet")
    print("=" * 60)
    print("Сервер запущен: http://localhost:5000")
    print("Логин: Malvin_42")
    print("Пароль: 585188")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
