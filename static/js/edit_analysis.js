        // Инициализация при загрузке
        document.addEventListener('DOMContentLoaded', function() {
            initializeForm();
        });
        
        // Инициализация формы
        function initializeForm() {
            // Проверяем, если тип анализа "Другое"
            const currentType = document.getElementById('analysis_type').value;
            const customField = document.getElementById('customTypeField');
            
            if (currentType === 'Другое') {
                customField.style.display = 'block';
                document.getElementById('custom_analysis_type').required = true;
            }
            
            // Устанавливаем текущую дату и время по умолчанию, если не заполнены
            const dateField = document.getElementById('custom_date');
            const timeField = document.getElementById('custom_time');
            
            if (!dateField.value) {
                dateField.value = new Date().toISOString().split('T')[0];
            }
            
            if (!timeField.value) {
                const now = new Date();
                timeField.value = now.getHours().toString().padStart(2, '0') + ':' + 
                                 now.getMinutes().toString().padStart(2, '0');
            }
            
            // Автофокус на первом поле
            document.getElementById('client_surname').focus();
            
            // Устанавливаем начальные значения формы для отслеживания изменений
            window.initialFormState = getFormState();
        }
        
        // Получение состояния формы
        function getFormState() {
            const form = document.getElementById('editAnalysisForm');
            const formData = new FormData(form);
            const state = {};
            
            for (let [key, value] of formData.entries()) {
                state[key] = value;
            }
            
            return JSON.stringify(state);
        }
        
        // Проверка изменений в форме
        function hasFormChanged() {
            const currentState = getFormState();
            return currentState !== window.initialFormState;
        }
        
        // Выбор типа анализа через быстрые кнопки
        function selectAnalysisType(type) {
            const selectElement = document.getElementById('analysis_type');
            const customField = document.getElementById('customTypeField');
            const badges = document.querySelectorAll('.analysis-type-badge');
            
            // Сбрасываем активные бейджи
            badges.forEach(badge => {
                badge.style.borderColor = 'transparent';
                badge.style.boxShadow = 'none';
                if (badge.getAttribute('data-value') === type) {
                    badge.style.borderColor = 'var(--malvin-accent)';
                    badge.style.boxShadow = '0 0 0 3px rgba(56, 178, 172, 0.2)';
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
        
        // Подтверждение отметки звонка
        function confirmMarkCalled() {
            const clientName = document.getElementById('client_surname').value;
            const petName = document.getElementById('pet_name').value;
            
            return confirm(`Вы уверены, что хотите отметить анализ для ${clientName} (${petName}) как обработанный?\n\nПосле этого анализ переместится в раздел "Проработанные".`);
        }
        
        // Подтверждение удаления
        function confirmDelete() {
            const clientName = document.getElementById('client_surname').value;
            const petName = document.getElementById('pet_name').value;
            
            return confirm(`ВНИМАНИЕ: Вы собираетесь УДАЛИТЬ анализ для ${clientName} (${petName}).\n\nЭто действие невозможно отменить. Все данные будут безвозвратно удалены.\n\nПродолжить?`);
        }
        
        // Сброс формы
        function resetForm() {
            if (!confirm('Вы уверены, что хотите сбросить все изменения? Введенные данные будут потеряны.')) {
                return;
            }
            
            // Восстанавливаем исходные значения
            const originalType = '{{ analysis.analysis_type }}';
            const originalDoctorId = {{ analysis.doctor_id }};
            const originalDate = '{{ analysis.created_at.strftime("%Y-%m-%d") if analysis.created_at else "" }}';
            const originalTime = '{{ analysis.created_at.strftime("%H:%M") if analysis.created_at else "" }}';
            
            // Сбрасываем активные бейджи
            const badges = document.querySelectorAll('.analysis-type-badge');
            badges.forEach(badge => {
                badge.style.borderColor = 'transparent';
                badge.style.boxShadow = 'none';
                if (badge.getAttribute('data-value') === originalType) {
                    badge.style.borderColor = 'var(--malvin-accent)';
                    badge.style.boxShadow = '0 0 0 3px rgba(56, 178, 172, 0.2)';
                }
            });
            
            // Восстанавливаем выпадающие списки и поля
            document.getElementById('analysis_type').value = originalType;
            document.getElementById('doctor_id').value = originalDoctorId;
            document.getElementById('client_surname').value = '{{ analysis.client_surname }}';
            document.getElementById('pet_name').value = '{{ analysis.pet_name }}';
            document.getElementById('patient_id').value = '{{ analysis.patient_id or "" }}';
            document.getElementById('notes').value = '{{ analysis.notes or "" }}';
            document.getElementById('custom_date').value = originalDate;
            document.getElementById('custom_time').value = originalTime;
            
            // Обрабатываем поле "Другое"
            const customField = document.getElementById('customTypeField');
            if (originalType === 'Другое') {
                customField.style.display = 'block';
            } else {
                customField.style.display = 'none';
            }
            
            // Скрываем сообщения об ошибках
            const errorMessages = document.querySelectorAll('.validation-message');
            errorMessages.forEach(msg => msg.style.display = 'none');
            
            // Сбрасываем классы ошибок
            const invalidFields = document.querySelectorAll('.is-invalid');
            invalidFields.forEach(field => field.classList.remove('is-invalid'));
            
            // Обновляем начальное состояние
            window.initialFormState = getFormState();
        }
        
        // Валидация формы
        document.getElementById('editAnalysisForm').addEventListener('submit', function(event) {
            event.preventDefault();
            
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
            
            // Показываем индикатор загрузки
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Сохранение...';
            submitBtn.disabled = true;
            
            // Отправляем форму
            setTimeout(() => {
                form.submit();
            }, 500);
        });
        
        // Обработка изменений в select типа анализа
        document.getElementById('analysis_type').addEventListener('change', function() {
            const type = this.value;
            const customField = document.getElementById('customTypeField');
            const badges = document.querySelectorAll('.analysis-type-badge');
            
            // Обновляем активные бейджи
            badges.forEach(badge => {
                badge.style.borderColor = 'transparent';
                badge.style.boxShadow = 'none';
                if (badge.getAttribute('data-value') === type) {
                    badge.style.borderColor = 'var(--malvin-accent)';
                    badge.style.boxShadow = '0 0 0 3px rgba(56, 178, 172, 0.2)';
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
        
        // Установка текущего времени
        function setCurrentTime() {
            const now = new Date();
            document.getElementById('custom_time').value = 
                now.getHours().toString().padStart(2, '0') + ':' + 
                now.getMinutes().toString().padStart(2, '0');
        }
        
        // Установка текущей даты
        function setCurrentDate() {
            document.getElementById('custom_date').value = new Date().toISOString().split('T')[0];
        }
        
        // Предупреждение о несохраненных изменениях
        window.addEventListener('beforeunload', function(e) {
            if (hasFormChanged()) {
                e.preventDefault();
                e.returnValue = 'У вас есть несохраненные изменения. Вы уверены, что хотите покинуть страницу?';
                return e.returnValue;
            }
        });
        
        // Отслеживание изменений в форме
        const form = document.getElementById('editAnalysisForm');
        form.addEventListener('input', function() {
            window.formChanged = true;
        });
        
        form.addEventListener('submit', function() {
            window.formChanged = false;
        });
        
        // Добавляем кнопки для быстрой установки даты и времени
        document.addEventListener('DOMContentLoaded', function() {
            // Добавляем кнопки рядом с полями даты и времени
            const dateField = document.getElementById('custom_date');
            const timeField = document.getElementById('custom_time');
            
            // Создаем кнопку для даты
            const dateButton = document.createElement('button');
            dateButton.type = 'button';
            dateButton.className = 'btn btn-sm btn-outline-secondary mt-1';
            dateButton.innerHTML = '<i class="bi bi-calendar-check me-1"></i>Сегодня';
            dateButton.onclick = setCurrentDate;
            
            // Создаем кнопку для времени
            const timeButton = document.createElement('button');
            timeButton.type = 'button';
            timeButton.className = 'btn btn-sm btn-outline-secondary mt-1';
            timeButton.innerHTML = '<i class="bi bi-clock me-1"></i>Сейчас';
            timeButton.onclick = setCurrentTime;
            
            // Вставляем кнопки после полей
            dateField.parentNode.appendChild(dateButton);
            timeField.parentNode.appendChild(timeButton);
        });