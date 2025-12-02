# app.py - полная исправленная версия
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
import pandas as pd
import os
import csv
from io import StringIO
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
            'Шашурина Ю.Н',
            'Олейник А.С.',
            'Синюков С.С.',
            'Соколова А.С',
            'Гришина А.С.',
            'Соловьев Д.Е.',
            'Титова Н.И',
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
            flash('Неверные учетные данные. Логин: Malvin_42, Пароль: 585188', 'danger')
    
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
        status = request.args.get('status', 'actual')
        search = request.args.get('search', '').strip()
        
        # Базовый запрос
        query = Analysis.query
        
        # Применяем фильтры
        if doctor_id:
            query = query.filter_by(doctor_id=doctor_id)
        
        if status in ['actual', 'processed']:
            query = query.filter_by(status=status)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                db.or_(
                    Analysis.client_surname.ilike(search_term),
                    Analysis.pet_name.ilike(search_term),
                    Analysis.analysis_type.ilike(search_term),
                    Analysis.notes.ilike(search_term)
                )
            )
        
        # Сортировка
        if status == 'actual':
            analyses = query.order_by(Analysis.created_at.desc()).all()
        else:
            analyses = query.order_by(Analysis.call_date.desc()).all()
        
        # Получаем всех врачей для фильтра
        doctors = Doctor.query.order_by(Doctor.name).all()
        
        # Статистика
        total_analyses = Analysis.query.count()
        actual_count = Analysis.query.filter_by(status='actual').count()
        processed_count = Analysis.query.filter_by(status='processed').count()
        
        # Статистика по врачам
        doctor_stats = []
        for doctor in doctors:
            doctor_actual = Analysis.query.filter_by(doctor_id=doctor.id, status='actual').count()
            doctor_processed = Analysis.query.filter_by(doctor_id=doctor.id, status='processed').count()
            doctor_total = doctor_actual + doctor_processed
            
            if doctor_total > 0:
                progress = int((doctor_processed / doctor_total) * 100)
            else:
                progress = 0
                
            doctor_stats.append({
                'id': doctor.id,
                'name': doctor.name,
                'actual': doctor_actual,
                'processed': doctor_processed,
                'total': doctor_total,
                'progress': progress
            })
        
        return render_template('index.html',
                             analyses=analyses,
                             doctors=doctors,
                             doctor_stats=doctor_stats,
                             total_analyses=total_analyses,
                             actual_count=actual_count,
                             processed_count=processed_count,
                             selected_doctor=doctor_id,
                             selected_status=status,
                             search_query=search)
    
    except Exception as e:
        flash(f'Ошибка при загрузке данных: {str(e)}', 'danger')
        return render_template('index.html', analyses=[], doctors=[], doctor_stats=[])

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
    
    return redirect(url_for('index'))

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
СТАТУС: Обработан
{'='*60}
"""
    
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f'Ошибка при записи лога: {e}')

# Добавить новый анализ
@app.route('/analysis/add', methods=['GET', 'POST'])
@login_required
def add_analysis():
    doctors = Doctor.query.order_by(Doctor.name).all()
    
    if request.method == 'POST':
        try:
            client_surname = request.form.get('client_surname', '').strip()
            pet_name = request.form.get('pet_name', '').strip()
            analysis_type = request.form.get('analysis_type', '').strip()
            doctor_id = request.form.get('doctor_id', type=int)
            notes = request.form.get('notes', '').strip()
            
            # Проверяем обязательные поля
            if not client_surname or not pet_name or not analysis_type or not doctor_id:
                flash('Пожалуйста, заполните все обязательные поля', 'danger')
                return render_template('add_analysis.html', doctors=doctors)
            
            # Создаем новый анализ
            analysis = Analysis(
                client_surname=client_surname,
                pet_name=pet_name,
                analysis_type=analysis_type,
                doctor_id=doctor_id,
                notes=notes,
                status='actual',
                is_called=False
            )
            
            db.session.add(analysis)
            db.session.commit()
            
            flash(f'Анализ успешно добавлен для {client_surname} ({pet_name})', 'success')
            return redirect(url_for('index'))
        
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
            analysis.client_surname = request.form.get('client_surname', '').strip()
            analysis.pet_name = request.form.get('pet_name', '').strip()
            analysis.analysis_type = request.form.get('analysis_type', '').strip()
            analysis.doctor_id = request.form.get('doctor_id', type=int)
            analysis.notes = request.form.get('notes', '').strip()
            
            db.session.commit()
            
            flash('Анализ успешно обновлен', 'success')
            return redirect(url_for('index'))
        
        except Exception as e:
            flash(f'Ошибка при обновлении анализа: {str(e)}', 'danger')
    
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
    
    return redirect(url_for('index'))

# Загрузка CSV файла
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_csv():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('Файл не выбран', 'danger')
            return redirect(url_for('upload_csv'))
        
        file = request.files['csv_file']
        
        if file.filename == '':
            flash('Файл не выбран', 'danger')
            return redirect(url_for('upload_csv'))
        
        if not file.filename.endswith('.csv'):
            flash('Пожалуйста, загрузите CSV файл', 'danger')
            return redirect(url_for('upload_csv'))
        
        try:
            # Сохраняем файл
            filename = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Читаем CSV
            df = pd.read_csv(filepath, encoding='utf-8')
            
            # Проверяем необходимые колонки
            required_columns = ['Врач', 'Фамилия', 'Кличка', 'Анализ']
            for col in required_columns:
                if col not in df.columns:
                    flash(f'В файле отсутствует обязательная колонка: {col}', 'danger')
                    return redirect(url_for('upload_csv'))
            
            added_count = 0
            for _, row in df.iterrows():
                try:
                    # Находим или создаем врача
                    doctor_name = str(row['Врач']).strip()
                    doctor = Doctor.query.filter_by(name=doctor_name).first()
                    
                    if not doctor:
                        doctor = Doctor(name=doctor_name)
                        db.session.add(doctor)
                        db.session.flush()
                    
                    # Создаем анализ
                    analysis = Analysis(
                        client_surname=str(row['Фамилия']).strip(),
                        pet_name=str(row['Кличка']).strip(),
                        analysis_type=str(row['Анализ']).strip(),
                        doctor_id=doctor.id,
                        notes=str(row.get('Примечания', '')).strip(),
                        status='actual',
                        is_called=False
                    )
                    
                    db.session.add(analysis)
                    added_count += 1
                    
                except Exception as row_error:
                    print(f"Ошибка в строке {_}: {row_error}")
                    continue
            
            db.session.commit()
            flash(f'Успешно добавлено {added_count} анализов из {len(df)} строк', 'success')
            
        except Exception as e:
            flash(f'Ошибка при обработке файла: {str(e)}', 'danger')
            print(traceback.format_exc())
        
        return redirect(url_for('index'))
    
    return render_template('upload.html')

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
            'ID', 'Фамилия владельца', 'Кличка', 'Тип анализа',
            'Статус', 'Обработан', 'Дата обработки', 'Врач',
            'Примечания', 'Дата создания', 'Дата обновления'
        ])
        
        # Данные
        for analysis in analyses:
            writer.writerow([
                analysis.id,
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
            StringIO(output.getvalue()),
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