        // Выбор типа анализа через быстрые кнопки
        function selectAnalysisType(type) {
            const selectElement = document.getElementById('analysis_type');
            const customField = document.getElementById('customTypeField');
            const badges = document.querySelectorAll('.analysis-type-badge');
            
            // Сбрасываем активные бейджи
            badges.forEach(badge => {
                badge.classList.remove('active');
                if (badge.getAttribute('data-value') === type) {
                    badge.classList.add('active');
                }
            });
            
            // Устанавливаем значение в select
            selectElement.value = type;
            
            // Показываем/скрываем поле для другого типа
            if (type === 'Другое') {
                customField.style.display = 'block';
                document.getElementById('custom_analysis_type').required = true;
            } else {
                customField.style.display = 'none';
                document.getElementById('custom_analysis_type').required = false;
            }
            
            // Скрываем сообщение об ошибке
            document.getElementById('analysisTypeError').style.display = 'none';
            selectElement.classList.remove('is-invalid');
        }
        
        // Выбор врача через быстрые кнопки
        function selectDoctor(doctorId, doctorName) {
            const selectElement = document.getElementById('doctor_id');
            selectElement.value = doctorId;
            
            // Скрываем сообщение об ошибке
            document.getElementById('doctorError').style.display = 'none';
            selectElement.classList.remove('is-invalid');
            
            // Визуальная обратная связь
            const buttons = document.querySelectorAll('.btn-outline-primary');
            buttons.forEach(btn => {
                btn.classList.remove('active', 'btn-primary');
                btn.classList.add('btn-outline-primary');
                if (btn.textContent.trim() === doctorName) {
                    btn.classList.remove('btn-outline-primary');
                    btn.classList.add('btn-primary', 'active');
                }
            });
        }
        
        // Установка текущего времени
        document.getElementById('setCurrentTimeBtn').addEventListener('click', function() {
            const now = new Date();
            const hours = now.getHours().toString().padStart(2, '0');
            const minutes = now.getMinutes().toString().padStart(2, '0');
            
            document.getElementById('custom_time').value = `${hours}:${minutes}`;
            
            // Визуальная обратная связь
            this.innerHTML = '<i class="bi bi-check-lg"></i> Установлено';
            this.classList.remove('btn-outline-secondary');
            this.classList.add('btn-success');
            
            setTimeout(() => {
                this.innerHTML = '<i class="bi bi-clock"></i> Сейчас';
                this.classList.remove('btn-success');
                this.classList.add('btn-outline-secondary');
            }, 1500);
        });
        
        // Валидация формы
        document.getElementById('addAnalysisForm').addEventListener('submit', function(event) {
            let isValid = true;
            const form = event.target;
            
            // Проверка обязательных полей
            const requiredFields = [
                { id: 'client_surname', errorId: 'surnameError' },
                { id: 'pet_name', errorId: 'petNameError' },
                { id: 'analysis_type', errorId: 'analysisTypeError' },
                { id: 'doctor_id', errorId: 'doctorError' }
            ];
            
            requiredFields.forEach(field => {
                const element = document.getElementById(field.id);
                const errorElement = document.getElementById(field.errorId);
                
                if (!element.value || element.value === '') {
                    isValid = false;
                    element.classList.add('is-invalid');
                    errorElement.style.display = 'block';
                } else {
                    element.classList.remove('is-invalid');
                    errorElement.style.display = 'none';
                }
            });
            
            // Проверка кастомного типа анализа
            const analysisType = document.getElementById('analysis_type').value;
            if (analysisType === 'Другое') {
                const customType = document.getElementById('custom_analysis_type');
                if (!customType.value || customType.value === '') {
                    isValid = false;
                    customType.classList.add('is-invalid');
                    customType.focus();
                    return false;
                }
            }
            
            if (!isValid) {
                event.preventDefault();
                event.stopPropagation();
                
                // Прокрутка к первой ошибке
                const firstError = document.querySelector('.is-invalid');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstError.focus();
                }
                
                return false;
            }
            
            // Если тип анализа "Другое", меняем значение
            if (analysisType === 'Другое') {
                const customType = document.getElementById('custom_analysis_type');
                document.getElementById('analysis_type').value = customType.value;
            }
            
            // Проверка даты (если не указана, ставим сегодня)
            const dateInput = document.getElementById('custom_date');
            if (!dateInput.value) {
                const today = new Date().toISOString().split('T')[0];
                dateInput.value = today;
            }
            
            // Проверка времени (если не указано, ставим текущее)
            const timeInput = document.getElementById('custom_time');
            if (!timeInput.value) {
                const now = new Date();
                const hours = now.getHours().toString().padStart(2, '0');
                const minutes = now.getMinutes().toString().padStart(2, '0');
                timeInput.value = `${hours}:${minutes}`;
            }
            
            // Показываем индикатор загрузки
            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Сохранение...';
            submitBtn.disabled = true;
        });
        
        // Сброс формы
        document.querySelector('button[type="reset"]').addEventListener('click', function() {
            if (confirm('Вы уверены, что хотите очистить все поля формы?')) {
                // Сбрасываем активные бейджи
                const badges = document.querySelectorAll('.analysis-type-badge');
                badges.forEach(badge => badge.classList.remove('active'));
                
                // Скрываем сообщения об ошибках
                const errorMessages = document.querySelectorAll('.validation-message');
                errorMessages.forEach(msg => msg.style.display = 'none');
                
                // Сбрасываем классы ошибок
                const invalidFields = document.querySelectorAll('.is-invalid');
                invalidFields.forEach(field => field.classList.remove('is-invalid'));
                
                // Скрываем поле для другого типа
                document.getElementById('customTypeField').style.display = 'none';
                
                // Сбрасываем активные кнопки врачей
                const doctorButtons = document.querySelectorAll('.btn-outline-primary.active');
                doctorButtons.forEach(btn => {
                    btn.classList.remove('active', 'btn-primary');
                    btn.classList.add('btn-outline-primary');
                });
                
                // Сбрасываем кнопку времени
                const timeBtn = document.getElementById('setCurrentTimeBtn');
                timeBtn.innerHTML = '<i class="bi bi-clock"></i> Сейчас';
                timeBtn.classList.remove('btn-success');
                timeBtn.classList.add('btn-outline-secondary');
                
                // Устанавливаем сегодняшнюю дату по умолчанию
                const today = new Date().toISOString().split('T')[0];
                document.getElementById('custom_date').value = today;
                
                // Устанавливаем текущее время по умолчанию
                const now = new Date();
                const hours = now.getHours().toString().padStart(2, '0');
                const minutes = now.getMinutes().toString().padStart(2, '0');
                document.getElementById('custom_time').value = `${hours}:${minutes}`;
            }
        });
        
        // Автофокус на первом поле
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('client_surname').focus();
            
            // Устанавливаем сегодняшнюю дату по умолчанию
            const dateInput = document.getElementById('custom_date');
            if (!dateInput.value) {
                const today = new Date().toISOString().split('T')[0];
                dateInput.value = today;
            }
            
            // Устанавливаем текущее время по умолчанию
            const timeInput = document.getElementById('custom_time');
            if (!timeInput.value) {
                const now = new Date();
                const hours = now.getHours().toString().padStart(2, '0');
                const minutes = now.getMinutes().toString().padStart(2, '0');
                timeInput.value = `${hours}:${minutes}`;
            }
            
            // Проверяем если выбран тип "Другое", показываем поле
            const analysisType = document.getElementById('analysis_type').value;
            if (analysisType === 'Другое') {
                document.getElementById('customTypeField').style.display = 'block';
            }
            
            // Добавляем активный класс выбранному типу анализа
            if (analysisType) {
                const badges = document.querySelectorAll('.analysis-type-badge');
                badges.forEach(badge => {
                    if (badge.getAttribute('data-value') === analysisType) {
                        badge.classList.add('active');
                    }
                });
            }
        });
        
        // Обработка изменений в select типа анализа
        document.getElementById('analysis_type').addEventListener('change', function() {
            const type = this.value;
            const customField = document.getElementById('customTypeField');
            const badges = document.querySelectorAll('.analysis-type-badge');
            
            // Обновляем активные бейджи
            badges.forEach(badge => {
                badge.classList.remove('active');
                if (badge.getAttribute('data-value') === type) {
                    badge.classList.add('active');
                }
            });
            
            // Показываем/скрываем поле для другого типа
            if (type === 'Другое') {
                customField.style.display = 'block';
                document.getElementById('custom_analysis_type').required = true;
            } else {
                customField.style.display = 'none';
                document.getElementById('custom_analysis_type').required = false;
            }
        });