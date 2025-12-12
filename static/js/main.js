// Основная инициализация и общие функции
document.addEventListener('DOMContentLoaded', function() {
    // Сохранение активной вкладки
    initTabPersistence();
    
    // Автоскрытие алертов
    initAutoDismissAlerts();
    
    // Обработка ошибок логотипа
    initLogoFallback();
});

function initTabPersistence() {
    const tabEls = document.querySelectorAll('button[data-bs-toggle="tab"]');
    tabEls.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(event) {
            localStorage.setItem('activeTab', event.target.id);
        });
    });
    
    const activeTab = localStorage.getItem('activeTab');
    if (activeTab && document.getElementById(activeTab)) {
        const tabTrigger = new bootstrap.Tab(document.getElementById(activeTab));
        tabTrigger.show();
    }
}

function initAutoDismissAlerts() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
}

function initLogoFallback() {
    const logoImg = document.querySelector('.navbar-brand img');
    if (!logoImg) return;
    
    logoImg.addEventListener('error', function() {
        const fallback = document.createElement('div');
        fallback.className = 'd-flex align-items-center';
        fallback.innerHTML = '<i class="bi bi-heart-pulse fs-3 text-light me-2"></i>';
        this.parentNode.insertBefore(fallback, this);
        this.style.display = 'none';
    });
}