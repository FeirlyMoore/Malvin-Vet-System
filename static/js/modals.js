// Логика модальных окон
class ModalHandler {
    static initCallModal() {
        const modal = document.getElementById('confirmCallModal');
        if (!modal) return;
        
        modal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            ModalHandler.updateModalContent(button, 'call');
        });
        
        const confirmButton = document.getElementById('confirmCallButton');
        if (confirmButton) {
            confirmButton.addEventListener('click', () => {
                document.getElementById('confirmCallForm').submit();
            });
        }
    }
    
    static initDeleteModal() {
        const modal = document.getElementById('confirmDeleteModal');
        if (!modal) return;
        
        modal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            ModalHandler.updateModalContent(button, 'delete');
        });
        
        const confirmButton = document.getElementById('confirmDeleteButton');
        if (confirmButton) {
            confirmButton.addEventListener('click', () => {
                document.getElementById('confirmDeleteForm').submit();
            });
        }
    }
    
    static initResetDatabaseModal() {
        const form = document.getElementById('resetDatabaseForm');
        if (!form) return;
        
        const resetButton = document.getElementById('resetDatabaseButton');
        const confirmCheckbox = document.getElementById('confirmDelete');
        
        if (resetButton && confirmCheckbox) {
            resetButton.disabled = true;
            
            confirmCheckbox.addEventListener('change', function() {
                resetButton.disabled = !this.checked;
            });
        }
        
        form.addEventListener('submit', ModalHandler.validateResetForm);
    }
    
    static updateModalContent(button, type) {
        const prefixes = {
            'call': 'modalCall',
            'delete': 'modalDelete'
        };
        const prefix = prefixes[type];
        
        // Правильно определяем data-атрибуты
        const fields = [
            { htmlField: 'analysis-id', jsField: 'AnalysisId', isValue: true },
            { htmlField: 'client-surname', jsField: 'ClientSurname', isValue: false },
            { htmlField: 'pet-name', jsField: 'PetName', isValue: false },
            { htmlField: 'analysis-type', jsField: 'AnalysisType', isValue: false },
            { htmlField: 'doctor-name', jsField: 'DoctorName', isValue: false },
            { htmlField: 'patient-id', jsField: 'PatientId', isValue: false },
            { htmlField: 'created-at', jsField: 'CreatedAt', isValue: false }
        ];
        
        fields.forEach(field => {
            const value = button.getAttribute(`data-${field.htmlField}`);
            const element = document.getElementById(prefix + field.jsField);
            if (element) {
                if (field.isValue) {
                    element.value = value || '';
                } else {
                    element.textContent = (field.htmlField === 'patient-id' && !value) ? '—' : (value || '');
                }
            }
        });
        
        // Специфичные поля для delete
        if (type === 'delete') {
            const status = button.getAttribute('data-analysis-status');
            const statusText = ModalHandler.getStatusText(status);
            const statusElement = document.getElementById('modalDeleteAnalysisStatus');
            if (statusElement) {
                statusElement.textContent = statusText;
            }
        }
        
        // Обновление action формы
        const form = document.getElementById(`confirm${type.charAt(0).toUpperCase() + type.slice(1)}Form`);
        if (form) {
            const analysisId = button.getAttribute('data-analysis-id');
            if (type === 'call') {
                form.action = `/analysis/${analysisId}/mark_called`;
            } else {
                form.action = `/analysis/${analysisId}/delete`;
            }
        }
        
        // Отладочная информация (можно удалить после тестирования)
        console.log(`Modal ${type} updated for analysis:`, button.getAttribute('data-analysis-id'));
    }
    
    static getStatusText(status) {
        const statusMap = {
            'actual': 'Актуальный',
            'processed': 'Обработанный',
            'archived': 'Архивный'
        };
        return statusMap[status] || 'Неизвестно';
    }
    
    static validateResetForm(e) {
        e.preventDefault();
        const form = e.target;
        const password = form.querySelector('input[name="password"]').value;
        const confirmPassword = form.querySelector('input[name="confirm_password"]').value;
        const confirmation = form.querySelector('input[name="confirmation"]').value;
        const resetButton = document.getElementById('resetDatabaseButton');
        
        // Проверки
        if (password !== 'FeirlyMoore_42') {
            alert('Неверный пароль!');
            return false;
        }
        
        if (password !== confirmPassword) {
            alert('Пароли не совпадают!');
            return false;
        }
        
        if (confirmation.toLowerCase() !== 'сбросить базу данных') {
            alert('Неверное текстовое подтверждение! Введите: "сбросить базу данных"');
            return false;
        }
        
        if (!confirm('❗ ВНИМАНИЕ! Это действие удалит ВСЕ данные без возможности восстановления. Вы уверены?')) {
            return false;
        }
        
        // Показать индикатор загрузки
        if (resetButton) {
            resetButton.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Сброс...';
            resetButton.disabled = true;
        }
        
        form.submit();
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    ModalHandler.initCallModal();
    ModalHandler.initDeleteModal();
    ModalHandler.initResetDatabaseModal();
    
    // Для отладки: проверяем, что все кнопки имеют правильные data-атрибуты
    const callButtons = document.querySelectorAll('[data-bs-target="#confirmCallModal"]');
    const deleteButtons = document.querySelectorAll('[data-bs-target="#confirmDeleteModal"]');
    
    console.log(`Found ${callButtons.length} call buttons, ${deleteButtons.length} delete buttons`);
});