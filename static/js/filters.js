// Логика фильтров и обработки дат
class FilterHandler {
    static initDateInput() {
        const dateInput = document.querySelector('input[name="date"]');
        if (!dateInput) return;
        
        dateInput.addEventListener('input', FilterHandler.formatDateInput);
        dateInput.addEventListener('focus', FilterHandler.showDateHint);
        dateInput.addEventListener('blur', FilterHandler.resetDatePlaceholder);
    }
    
    static formatDateInput(e) {
        let value = e.target.value.replace(/\D/g, '');
        
        if (value.length > 2) {
            value = value.slice(0, 2) + '.' + value.slice(2);
        }
        if (value.length > 5) {
            value = value.slice(0, 5) + '.' + value.slice(5, 9);
        }
        
        e.target.value = value;
    }
    
    static showDateHint(e) {
        const input = e.target;
        if (!input.value) {
            const today = new Date();
            const day = String(today.getDate()).padStart(2, '0');
            const month = String(today.getMonth() + 1).padStart(2, '0');
            const year = today.getFullYear();
            input.placeholder = `Например: ${day}.${month}.${year}`;
        }
    }
    
    static resetDatePlaceholder(e) {
        e.target.placeholder = 'ДД.ММ.ГГГГ';
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    FilterHandler.initDateInput();
});