/**
 * Исправления для проблем с аутентификацией в Prompt Arena
 * 
 * Этот файл содержит исправления для устранения проблем с аутентификацией
 * в приложении Prompt Arena, чтобы обеспечить сохранение сессии при обновлении
 * страницы и корректную работу с API.
 */

// Ждем загрузки DOM
document.addEventListener('DOMContentLoaded', () => {
    console.log('🔧 Применение исправлений для аутентификации...');
    
    // Переопределение функции проверки аутентификации
    if (typeof checkAuthentication === 'function') {
        const originalCheckAuth = checkAuthentication;
        window.checkAuthentication = function() {
            const basicAuth = localStorage.getItem('basic_auth');
            const username = localStorage.getItem('username');
            
            console.log(`🔐 Проверка аутентификации. Auth: ${basicAuth ? 'Есть' : 'Нет'}, Username: ${username ? 'Есть' : 'Нет'}`);
            
            if (!basicAuth && dom.loginModal) {
                showModal(dom.loginModal);
            } else if (basicAuth && !username) {
                // Если есть токен, но нет имени пользователя, извлекаем его из токена и сохраняем
                try {
                    // Извлекаем имя пользователя из токена Basic Auth
                    const base64Credentials = basicAuth.split(' ')[1];
                    const credentials = atob(base64Credentials).split(':');
                    const extractedUsername = credentials[0];
                    localStorage.setItem('username', extractedUsername);
                    console.log('✅ Имя пользователя восстановлено из токена:', extractedUsername);
                } catch (e) {
                    console.error('❌ Ошибка при восстановлении имени пользователя:', e);
                }
            }
            
            // Если есть авторизация, загружаем шаблоны промтов
            if (basicAuth && typeof fetchPromptTemplates === 'function') {
                console.log('📋 Загрузка шаблонов промтов...');
                setTimeout(() => fetchPromptTemplates(), 500);
            }
        };
        console.log('✅ Функция проверки аутентификации успешно расширена.');
    }
    
    // Переопределение обработчика формы логина
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        // Сохраняем старый обработчик и удаляем его
        const oldHandlers = loginForm.onsubmit;
        loginForm.onsubmit = null;
        
        // Добавляем новый обработчик
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('login-username').value.trim();
            const password = document.getElementById('login-password').value.trim();
            
            if (!username || !password) {
                showNotification('Введите логин и пароль', 'warning');
                return;
            }
            
            try {
                // Проверяем авторизацию через Basic Auth
                const authHeader = 'Basic ' + btoa(`${username}:${password}`);
                
                // Пробуем получить статус для проверки
                const resp = await fetch(`${API_BASE_URL}/status`, {
                    headers: { 'Authorization': authHeader }
                });
                
                if (resp.status === 401) {
                    throw new Error('Неверный логин или пароль');
                }
                
                // Если успешно, сохраняем в localStorage
                localStorage.setItem('basic_auth', authHeader);
                localStorage.setItem('username', username);
                console.log('✅ Аутентификация успешна, данные сохранены в localStorage');
                
                showNotification('Успешный вход!', 'success');
                hideModal(document.getElementById('login-modal'));
                
                // Перезагружаем данные
                await fetchCategories();
                await fetchApiKeys();
                await fetchModels();
                
                // Загружаем шаблоны промтов
                if (typeof fetchPromptTemplates === 'function') {
                    console.log('📋 Загрузка шаблонов промтов после входа...');
                    await fetchPromptTemplates();
                }
            } catch (error) {
                console.error('❌ Ошибка аутентификации:', error);
                showNotification(error.message || 'Ошибка входа', 'error');
            }
        });
        
        console.log('✅ Обработчик формы логина успешно заменен.');
    }
    
    // Расширение функции fetchApi для более устойчивой аутентификации
    if (typeof fetchApi === 'function') {
        const originalFetchApi = fetchApi;
        window.fetchApi = async function(url, options = {}) {
            const defaultOptions = {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            };
            // Добавляем заголовок авторизации, если он есть в localStorage
            const auth = localStorage.getItem('basic_auth');
            if (auth) {
                defaultOptions.headers['Authorization'] = auth;
            }
            const mergedOptions = { ...defaultOptions, ...options };
            try {
                // Вызываем fetch напрямую, без рекурсии
                const response = await fetch(`${API_BASE_URL}${url}`, mergedOptions);
            
            } catch (error) {
                console.error('❌ Ошибка API запроса:', error);
                throw error;
            }
        };
        console.log('✅ Функция fetchApi успешно расширена.');
    }
});
