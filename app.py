from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import csv
import os
import sys
import codecs
from functools import wraps  # ДОБАВЬТЕ ЭТУ СТРОКУ!

# Устанавливаем UTF-8 кодировку для вывода в Windows
if sys.platform == "win32":
    try:
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, 'strict')
    except:
        pass

app = Flask(__name__)
app.config['SECRET_KEY'] = 'malvin_secret_key_42'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['EMERGENCY_FOLDER'] = 'emergency_logs/'

# Создаем папки если их нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['EMERGENCY_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Модели базы данных
class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    analyses = db.relationship('Analysis', backref='doctor', lazy=True)

class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_surname = db.Column(db.String(100), nullable=False)
    pet_name = db.Column(db.String(100), nullable=False)
    analysis_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='actual')  # 'actual' или 'processed'
    called = db.Column(db.Boolean, default=False)
    called_date = db.Column(db.DateTime, nullable=True)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    notes = db.Column(db.Text, nullable=True)

# Функция инициализации базы данных
def initialize_database():
    with app.app_context():
        db.create_all()
        
        # Проверяем, есть ли уже данные
        if Doctor.query.count() == 0:
            print("Инициализация базы данных...")
            
            # Список врачей из документа
            doctors_list = [
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
            
            # Создаем врачей
            for doc_name in doctors_list:
                doctor = Doctor(name=doc_name)
                db.session.add(doctor)
            
            db.session.commit()
            
            # Получаем ID врачей после commit
            doctors = Doctor.query.all()
            doctors_dict = {doctor.name: doctor.id for doctor in doctors}
            
            # Данные анализов из документа
            analyses_data = [
                ('Бруштейн', 'Джони', 'кр', 'Волков И.Р.'),
                ('Улитина', 'Шони', 'м', 'Волков И.Р.'),
                ('Оганян', 'Чиж', 'м', 'Волков И.Р.'),
                ('Жукова', 'Кеша', 'кр, м', 'Волков И.Р.'),
                ('Харитонова', 'Мила', 'ВЮ', 'Волков И.Р.'),
                ('Русу', 'Цезарь', 'кр', 'Волков И.Р.'),
                ('Запруднова', 'Муся', 'кр', 'Волков И.Р.'),
                ('Белова', 'Энни', 'кр', 'Волков И.Р.'),
                ('Казаркина', 'Ларри', 'м', 'Волков И.Р.'),
                ('Карев', 'Яся', 'кр', 'Волков И.Р.'),
                ('Гуринова', 'Лиза', 'кр', 'Волков И.Р.'),
                ('Чистосердов', 'Амиго', 'ВЮ', 'Федосов М.А.'),
                ('Михайлова', 'Дуся', 'ВТ', 'Федосов М.А.'),
                ('Зубакова', 'Барсик', 'м', 'Федосов М.А.'),
                ('Яснева', 'Тимон', 'кр', 'Федосов М.А.'),
                ('Кузнецова', 'Жаклин', 'дерм', 'Шашурина Ю.Н'),
                ('Гречина', 'Ася', 'кр', 'Шашурина Ю.Н'),
                ('Ширяева', 'Моника', 'цито', 'Шашурина Ю.Н'),
                ('Бабиков', 'Внисент', 'ВЮ', 'Шашурина Ю.Н'),
                ('Кульман', 'Кеша', 'ди', 'Шашурина Ю.Н'),
                ('Мудайар', 'Рагнар', 'ВЮ', 'Шашурина Ю.Н'),
                ('Игонина', 'Муся', 'кр', 'Олейник А.С.'),
                ('Гарнова', 'Соня', 'кр', 'Олейник А.С.'),
                ('Солдатова', 'Черныш', 'ВЮ', 'Олейник А.С.'),
                ('Харитонова', 'Мила', 'кр', 'Олейник А.С.'),
                ('Капустина', 'Василий', 'кр, ВЮ', 'Олейник А.С.'),
                ('Королева', 'Мира', 'кр', 'Олейник А.С.'),
                ('Корнева', 'Айс', 'м, кр', 'Олейник А.С.'),
                ('Сидоров', 'Тима', 'м, кр', 'Олейник А.С.'),
                ('Медников', 'Рик', 'кр', 'Олейник А.С.'),
                ('Хохлов', 'Федор', 'м', 'Олейник А.С.'),
                ('Милеева', 'Мирон', 'ВЮ', 'Олейник А.С.'),
                ('Яркова', 'Тень', 'ВЮ', 'Олейник А.С.'),
                ('Кичерова', 'Мася', 'кр', 'Синюков С.С.'),
                ('Корчемкина', 'Ласка', 'кр', 'Синюков С.С.'),
                ('Евстигнеева', 'Нюша', 'кр', 'Синюков С.С.'),
                ('Ерофеева', 'Жулик', 'кр', 'Синюков С.С.'),
                ('Разгуляев', 'Матвей', 'кр', 'Синюков С.С.'),
                ('Корнилова', 'Василиса', 'кр', 'Синюков С.С.'),
                ('Кутякина', 'Глаша', 'кр', 'Синюков С.С.'),
                ('Юркова', 'Пуша', 'м', 'Синюков С.С.'),
                ('Чурахина', 'Миша', 'м', 'Соколова А.С'),
                ('Соколова', 'Сеня', 'кр', 'Соколова А.С'),
                ('Сироткина', 'Тоша', 'м', 'Соколова А.С'),
                ('Чеботарева', 'Харли', 'ВЮ', 'Соколова А.С'),
                ('Илларионова', 'Петя', 'кр', 'Соколова А.С'),
                ('Пелевин', 'Фридрих', 'кр', 'Соколова А.С'),
                ('Здор', 'Тигра', 'кр', 'Соколова А.С'),
                ('Ибрагимова', 'Зефир', 'кал, кр', 'Соколова А.С'),
                ('Медников', 'Рик', 'кр', 'Соколова А.С'),
                ('Смелов', 'Оди', 'м', 'Без врача'),
                ('Скрябина', 'Сема', 'м', 'Без врача'),
                ('Потехина', 'Буля', 'м', 'Без врача'),
                ('Замятин', 'Джина', 'ВЮ', 'Гришина А.С.'),
                ('Боброва', 'Фрося', 'кал', 'Гришина А.С.'),
                ('Леонов', 'Марс', 'кр', 'Гришина А.С.'),
                ('Родионова', 'Рокси', 'кр', 'Гришина А.С.'),
                ('Сумина', 'Лим', 'м', 'Гришина А.С.'),
                ('Уткина', 'Масяня', 'кр', 'Гришина А.С.'),
                ('Уткина', 'Персик', 'кр', 'Гришина А.С.'),
                ('Волчонкова', 'Рыжик', 'кр', 'Гришина А.С.'),
                ('Одаховский', 'Джек', 'кр', 'Гришина А.С.'),
                ('Лысов', 'Виктор', 'кал', 'Гришина А.С.'),
                ('Соколова', 'Ума', 'кр', 'Гришина А.С.'),
                ('Сироткина', 'Айко', 'кр', 'Гришина А.С.'),
                ('Королева', 'Мира', 'кр', 'Гришина А.С.'),
                ('Хомутова', 'Петр', 'кр', 'Гришина А.С.'),
                ('Глушков', 'Федор', 'м', 'Гришина А.С.'),
                ('Полякова', 'Федора', 'м', 'Гришина А.С.'),
                ('Мартиросян', 'Картье', 'ВЮ', 'Гришина А.С.'),
                ('Сидоров', 'Тима', 'м', 'Гришина А.С.'),
                ('Широков', 'Бронсон', 'кр', 'Гришина А.С.'),
                ('Горынцева', 'Буся', 'кр', 'Гришина А.С.'),
                ('Земскова', 'Дени', 'кр', 'Гришина А.С.'),
                ('Широков', 'Бронсон', 'кр', 'Гришина А.С.'),
                ('Арсеньева', 'Филти', 'кр', 'Гришина А.С.'),
                ('Дайнеко', 'Максим', 'кр', 'Гришина А.С.'),
                ('Земскова', 'Дени', 'кр', 'Гришина А.С.'),
                ('Фионин', 'Хадижа', 'кр', 'Соловьев Д.Е.'),
                ('Андреева', 'Стеша', 'кр', 'Титова Н.И'),
                ('Кузнецова', 'Роза', 'кр', 'Титова Н.И'),
                ('Гусева', 'Марси', 'ВЮ', 'Титова Н.И'),
                ('Полякова', 'Федора', 'кр', 'Титова Н.И'),
                ('Корнева', 'Айс', 'м', 'Титова Н.И'),
                ('Мартынова', 'Персей', 'м', 'Титова Н.И'),
                ('Шалыгина', 'Ричард', 'кал', 'Титова Н.И'),
                ('Фонинский', 'Чешир', 'кр', 'Титова Н.И'),
                ('Земскова', 'Дени', 'кр, м', 'Титова Н.И'),
                ('Герц', 'Волк', 'кр', 'Лочехина Е.А.'),
                ('Кутепова', 'Федор', 'кр', 'Лочехина Е.А.'),
                ('Рябчикова', 'Васька', 'кр', 'Лочехина Е.А.'),
                ('Карев', 'Яся', 'кр', 'Лочехина Е.А.'),
                ('Бутенко', 'Масяня', 'кр', 'Лочехина Е.А.'),
                ('Соловьев', 'Тима', 'кр', 'Лочехина Е.А.'),
                ('Булюкин', 'Василиса', 'кр', 'Лочехина Е.А.'),
                ('Кресниковский', 'Рой', 'кр', 'Лочехина Е.А.'),
                ('Шлемина', 'Лулу', 'кр', 'Лочехина Е.А.'),
                ('Меджидов', 'Симба', 'кр', 'Лочехина Е.А.'),
                ('Рожкова', 'Юджин', 'кр', 'Лочехина Е.А.'),
                ('Гаврилова', 'Мася', 'кр', 'Лочехина Е.А.'),
                ('Потехина', 'Буля', 'кр', 'Лочехина Е.А.'),
                ('Зайцева', 'Дина', 'кр', 'Лочехина Е.А.'),
                ('Прохоров', 'Пух', 'кр', 'Лочехина Е.А.'),
                ('Гурьева', 'Юки', 'кр', 'Лочехина Е.А.'),
                ('Колесова', 'Усик', 'кр', 'Лочехина Е.А.'),
                ('Колесникова', 'Макс', 'кр', 'Зюков И.И.'),
                ('Клюев', 'Марсель?', 'кр', 'Зюков И.И.'),
                ('Рыжова', 'Мила', 'кр', 'Зюков И.И.'),
                ('Смолина', 'Пушок', 'кр', 'Зюков И.И.'),
                ('Модина', 'Лексус', 'кр', 'Зюков И.И.'),
                ('Новикова', 'Тихон', 'кр', 'Синюкова Е.В.'),
                ('Данилова', 'Макс', 'кр, ВЮ', 'Синюкова Е.В.'),
                ('Усова', 'Мона', 'кр', 'Синюкова Е.В.'),
                ('Удовиков', 'Лиса', 'кр', 'Синюкова Е.В.'),
                ('Чикалина', 'Бусинка', 'м', 'Синюкова Е.В.'),
                ('Афонина', 'Лиза', 'кр', 'Синюкова Е.В.'),
                ('Соколова', 'Базилик', 'кал', 'Синюкова Е.В.'),
                ('Барановская', 'Тихон', 'кр', 'Синюкова Е.В.'),
                ('Иванова', 'Филя', 'кр', 'Макаренко В.А.'),
                ('Земскова', 'Дени', 'м', 'Макаренко В.А.'),
            ]
            
            # Преобразуем сокращения в полные названия
            def expand_analysis_type(abbr):
                mapping = {
                    'кр': 'Кровь',
                    'м': 'Моча',
                    'кал': 'Кал',
                    'цито': 'Цитология',
                    'ди': 'Диагностика',
                    'дерм': 'Дерматология',
                    'ВТ': 'Вет Юнион',
                    'ВЮ': 'Вет Юнион'
                }
                
                if ',' in abbr:
                    parts = [p.strip() for p in abbr.split(',')]
                    return ', '.join([mapping.get(p, p) for p in parts])
                else:
                    return mapping.get(abbr, abbr)
            
            # Добавляем анализы
            for surname, pet_name, analysis_abbr, doctor_name in analyses_data:
                if doctor_name in doctors_dict:
                    analysis_type = expand_analysis_type(analysis_abbr)
                    notes = f"Добавлено из документа 02.12.2025"
                    
                    analysis = Analysis(
                        client_surname=surname,
                        pet_name=pet_name,
                        analysis_type=analysis_type,
                        doctor_id=doctors_dict[doctor_name],
                        notes=notes
                    )
                    db.session.add(analysis)
            
            db.session.commit()
            print(f"[OK] Загружено {len(analyses_data)} анализов для {len(doctors_list)} врачей")
        else:
            print("[INFO] База данных уже инициализирована")

# Декоратор для проверки авторизации
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Система авторизации
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == 'Malvin_42' and password == '585188':
            session['logged_in'] = True
            session['username'] = username
            flash('Вы успешно вошли в систему', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверные учетные данные', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

# Главная страница с двумя вкладками
@app.route('/')
@login_required
def index():
    with app.app_context():
        actual_analyses = Analysis.query.filter_by(status='actual').order_by(Analysis.created_date.desc()).all()
        processed_analyses = Analysis.query.filter_by(status='processed').order_by(Analysis.called_date.desc()).all()
        doctors = Doctor.query.all()
        
        # Статистика по врачам
        doctor_stats = {}
        for doctor in doctors:
            actual_count = Analysis.query.filter_by(doctor_id=doctor.id, status='actual').count()
            processed_count = Analysis.query.filter_by(doctor_id=doctor.id, status='processed').count()
            doctor_stats[doctor.id] = {
                'name': doctor.name,
                'actual': actual_count,
                'processed': processed_count,
                'total': actual_count + processed_count
            }
        
        return render_template('index.html', 
                             actual_analyses=actual_analyses,
                             processed_analyses=processed_analyses,
                             doctors=doctors,
                             doctor_stats=doctor_stats)

# Отметка о звонке
@app.route('/mark_called/<int:analysis_id>', methods=['POST'])
@login_required
def mark_called(analysis_id):
    with app.app_context():
        analysis = Analysis.query.get_or_404(analysis_id)
        
        if not analysis.called:
            analysis.called = True
            analysis.status = 'processed'
            analysis.called_date = datetime.utcnow()
            db.session.commit()
            
            # Логирование в emergency файл
            log_emergency_call(analysis)
            
            flash(f'Анализ для {analysis.client_surname} ({analysis.pet_name}) отмечен как обработанный', 'success')
    
    return redirect(url_for('index'))

def log_emergency_call(analysis):
    """Логирование информации о звонке в файл"""
    timestamp = datetime.now().strftime('%Y-%m-%d')
    filename = f"emergency_{timestamp}.txt"
    filepath = os.path.join(app.config['EMERGENCY_FOLDER'], filename)
    
    # Добавляем в существующий файл или создаем новый
    mode = 'a' if os.path.exists(filepath) else 'w'
    
    with open(filepath, mode, encoding='utf-8') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"ВРЕМЯ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"ВЛАДЕЛЕЦ: {analysis.client_surname}\n")
        f.write(f"АНАЛИЗ: {analysis.analysis_type}\n")
        f.write(f"КЛИЧКА: {analysis.pet_name}\n")
        f.write(f"ВРАЧ: {analysis.doctor.name}\n")
        f.write(f"СТАТУС: Обработан\n")

# Добавление нового анализа
@app.route('/add_analysis', methods=['GET', 'POST'])
@login_required
def add_analysis():
    with app.app_context():
        doctors = Doctor.query.all()
        
        if request.method == 'POST':
            client_surname = request.form['client_surname']
            pet_name = request.form['pet_name']
            analysis_type = request.form['analysis_type']
            doctor_id = request.form['doctor_id']
            notes = request.form.get('notes', '')
            
            analysis = Analysis(
                client_surname=client_surname,
                pet_name=pet_name,
                analysis_type=analysis_type,
                doctor_id=doctor_id,
                notes=notes
            )
            
            db.session.add(analysis)
            db.session.commit()
            
            flash('Анализ успешно добавлен', 'success')
            return redirect(url_for('index'))
        
        return render_template('add_analysis.html', doctors=doctors)

# Редактирование анализа
@app.route('/edit_analysis/<int:analysis_id>', methods=['GET', 'POST'])
@login_required
def edit_analysis(analysis_id):
    with app.app_context():
        analysis = Analysis.query.get_or_404(analysis_id)
        doctors = Doctor.query.all()
        
        if request.method == 'POST':
            analysis.client_surname = request.form['client_surname']
            analysis.pet_name = request.form['pet_name']
            analysis.analysis_type = request.form['analysis_type']
            analysis.doctor_id = request.form['doctor_id']
            analysis.notes = request.form.get('notes', '')
            
            db.session.commit()
            
            flash('Анализ успешно обновлен', 'success')
            return redirect(url_for('index'))
        
        return render_template('edit_analysis.html', analysis=analysis, doctors=doctors)

# Удаление анализа
@app.route('/delete_analysis/<int:analysis_id>')
@login_required
def delete_analysis(analysis_id):
    with app.app_context():
        analysis = Analysis.query.get_or_404(analysis_id)
        db.session.delete(analysis)
        db.session.commit()
        
        flash('Анализ успешно удален', 'success')
        return redirect(url_for('index'))

# Загрузка файла с анализами
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    with app.app_context():
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('Файл не выбран', 'danger')
                return redirect(request.url)
            
            file = request.files['file']
            
            if file.filename == '':
                flash('Файл не выбран', 'danger')
                return redirect(request.url)
            
            if file and (file.filename.endswith('.csv') or file.filename.endswith('.txt')):
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(filepath)
                
                try:
                    if file.filename.endswith('.csv'):
                        df = pd.read_csv(filepath, encoding='utf-8')
                        
                        for _, row in df.iterrows():
                            doctor = Doctor.query.filter_by(name=row['Врач']).first()
                            if not doctor:
                                doctor = Doctor(name=row['Врач'])
                                db.session.add(doctor)
                                db.session.flush()
                            
                            analysis = Analysis(
                                client_surname=row['Фамилия'],
                                pet_name=row['Кличка'],
                                analysis_type=row['Анализ'],
                                doctor_id=doctor.id,
                                notes=row.get('Примечания', '')
                            )
                            db.session.add(analysis)
                        
                        db.session.commit()
                        flash(f'Успешно загружено {len(df)} анализов', 'success')
                    
                except Exception as e:
                    flash(f'Ошибка при обработке файла: {str(e)}', 'danger')
                
                return redirect(url_for('index'))
        
        return render_template('upload.html')

# Сброс всех анализов в актуальные
@app.route('/reset_to_actual')
@login_required
def reset_to_actual():
    """Возвращает все анализы в статус актуальных (для тестирования)"""
    with app.app_context():
        analyses = Analysis.query.all()
        for analysis in analyses:
            analysis.status = 'actual'
            analysis.called = False
            analysis.called_date = None
        
        db.session.commit()
        flash('Все анализы сброшены в статус "Актуальные"', 'info')
        return redirect(url_for('index'))

# Экспорт данных
@app.route('/export_csv')
@login_required
def export_csv():
    """Экспорт всех анализов в CSV"""
    with app.app_context():
        analyses = Analysis.query.all()
        
        csv_data = "Врач;Фамилия;Кличка;Анализ;Статус;Дата создания;Дата звонка;Примечания\n"
        
        for analysis in analyses:
            csv_data += f"{analysis.doctor.name};{analysis.client_surname};{analysis.pet_name};"
            csv_data += f"{analysis.analysis_type};{analysis.status};"
            csv_data += f"{analysis.created_date.strftime('%d.%m.%Y %H:%M') if analysis.created_date else ''};"
            csv_data += f"{analysis.called_date.strftime('%d.%m.%Y %H:%M') if analysis.called_date else ''};"
            csv_data += f"{analysis.notes or ''}\n"
        
        return csv_data, 200, {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename=analytics_export.csv'
        }

# Просмотр логов emergency
@app.route('/view_logs')
@login_required
def view_logs():
    """Просмотр лог-файлов"""
    log_files = []
    if os.path.exists(app.config['EMERGENCY_FOLDER']):
        for filename in sorted(os.listdir(app.config['EMERGENCY_FOLDER'])):
            if filename.startswith('emergency_') and filename.endswith('.txt'):
                filepath = os.path.join(app.config['EMERGENCY_FOLDER'], filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                log_files.append({
                    'filename': filename,
                    'content': content,
                    'size': len(content)
                })
    
    return render_template('logs.html', log_files=log_files)

# API для получения статистики
@app.route('/api/stats')
@login_required
def get_stats():
    with app.app_context():
        total = Analysis.query.count()
        actual = Analysis.query.filter_by(status='actual').count()
        processed = Analysis.query.filter_by(status='processed').count()
        
        # Статистика по врачам
        doctor_stats = []
        doctors = Doctor.query.all()
        for doctor in doctors:
            actual_count = Analysis.query.filter_by(doctor_id=doctor.id, status='actual').count()
            processed_count = Analysis.query.filter_by(doctor_id=doctor.id, status='processed').count()
            doctor_stats.append({
                'doctor': doctor.name,
                'actual': actual_count,
                'processed': processed_count,
                'total': actual_count + processed_count
            })
        
        return jsonify({
            'total': total,
            'actual': actual,
            'processed': processed,
            'doctor_stats': doctor_stats
        })

if __name__ == '__main__':
    # Инициализируем базу данных при запуске
    initialize_database()
    
    print("=" * 60)
    print("Система учета анализов Malvin Vet")
    print("=" * 60)
    
    # Показываем статистику
    with app.app_context():
        doctors = Doctor.query.all()
        print("Доступные врачи:")
        for doctor in doctors:
            count = Analysis.query.filter_by(doctor_id=doctor.id).count()
            print(f"  - {doctor.name}: {count} анализов")
        
        total = Analysis.query.count()
        actual = Analysis.query.filter_by(status='actual').count()
        print(f"\nВсего анализов: {total}")
        print(f"Актуальных: {actual}")
        print(f"Обработанных: {total - actual}")
    
    print("\nДля доступа используйте:")
    print("  Логин: Malvin_42")
    print("  Пароль: 585188")
    print("=" * 60)
    print("\nСервер запущен: http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)