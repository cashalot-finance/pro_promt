'use strict';

/**
 * Промт Арена - клиентская часть
 * Современный JavaScript для управления интерфейсом и взаимодействия с API
 */

// --- Глобальные константы ---
const API_BASE_URL = window.location.origin + '/api/v1';
const MAX_CHAR_COUNT = 16000; // Максимальное число символов в промте
const DEBOUNCE_DELAY = 300; // Задержка для debounce функций (мс)
const CACHE_TTL = 3600000; // Время жизни кеша (1 час в мс)

// --- Глобальные переменные состояния ---
const state = {
  currentView: 'single', // 'single' или 'compare'
  selectedModel1: null, // Первая выбранная модель
  selectedModel2: null, // Вторая выбранная модель для сравнения
  chatHistory: [], // История чата
  editorInstance: null, // Экземпляр редактора Monaco
  categories: [], // Список категорий из API
  allModels: [], // Список всех доступных моделей
  filteredModels: [], // Отфильтрованные модели (по категории/поиску)
  currentCategory: null, // Текущая выбранная категория
  apiKeys: {}, // Список сохраненных API ключей
  currentComparisonWinner: null, // Победитель в сравнении: 'model_1', 'model_2', 'tie'
  currentPrompt: '', // Текущий промт для сохранения оценки
  currentRatings: { model1: 0, model2: 0 }, // Текущие оценки для моделей
  isLoadingModels: false, // Индикатор загрузки моделей
  isLoadingResponse: false, // Индикатор ожидания ответа
  settingsVisible: false, // Видимость панели настроек
  outputPanelVisible: false, // Видимость панели вывода
  notifications: [], // Массив активных уведомлений
  editorContent: '', // Содержимое редактора кода
  editorMode: 'visualizer', // Режим редактора: 'visualizer' или 'editor'
  templatesVisible: false, // Видимость панели шаблонов
  promptTemplates: [], // Шаблоны промтов
  currentTemplateId: null, // ID текущего редактируемого шаблона
  model1Settings: { // Настройки для первой модели в режиме сравнения
    temperature: 0.7,
    maxTokens: 1024,
    systemPrompt: ''
  },
  model2Settings: { // Настройки для второй модели в режиме сравнения
    temperature: 0.7,
    maxTokens: 1024,
    systemPrompt: ''
  }
};

// Добавить в начало script.js
function checkAuthentication() {
  const basicAuth = localStorage.getItem('basic_auth');
  if (!basicAuth && dom.loginModal) {
      showModal(dom.loginModal);
  }
}

function createNotificationsContainer() {
  const container = document.createElement('div');
  container.id = 'notifications-container';
  container.className = 'notifications-container';
  document.body.appendChild(container);
  return container;
}

// --- Ссылки на DOM элементы ---
// Создаем объект для хранения ссылок на DOM-элементы
const dom = {};

/**
 * Инициализирует ссылки на DOM-элементы после загрузки страницы
 */
function initDomReferences() {
  // Основные контейнеры
  dom.appContainer = document.getElementById('app-container');
  dom.sidebar = document.getElementById('sidebar');
  dom.mainContent = document.getElementById('main-content');

  // Элементы категорий и моделей
  dom.categoriesContainer = document.getElementById('categories-container');
  dom.modelsContainer = document.getElementById('models-container');
  dom.modelSearch = document.getElementById('model-search');

  // Переключатели режимов и кнопки
  dom.modeSingleBtn = document.getElementById('mode-single');
  dom.modeCompareBtn = document.getElementById('mode-compare');
  dom.toggleSettingsBtn = document.getElementById('toggle-settings');
  dom.settingsPanel = document.getElementById('settings-panel');
  dom.clearChatBtn = document.getElementById('clear-chat');
  dom.setupKeysBtn = document.getElementById('setup-keys-btn');
  dom.viewLeaderboardBtn = document.getElementById('view-leaderboard-btn');

  // Индикаторы выбранных моделей
  dom.selectedModelsContainer = document.getElementById('selected-models-container');
  dom.model1Info = document.getElementById('model-1-info');
  dom.model2Info = document.getElementById('model-2-info');
  dom.noModelSelected = document.getElementById('no-model-selected');
  dom.model1Name = document.getElementById('model-1-name');
  dom.model2Name = document.getElementById('model-2-name');

  // Области чата
  dom.chatContainer = document.getElementById('chat-container');
  dom.chatAreaSingle = document.getElementById('chat-area-single');
  dom.chatAreaCompare = document.getElementById('chat-area-compare');
  dom.chatMessagesSingle = document.getElementById('chat-messages-single');
  dom.chatMessagesModel1 = document.getElementById('chat-messages-model-1');
  dom.chatMessagesModel2 = document.getElementById('chat-messages-model-2');

  // Элементы рейтинга
  dom.ratingStars = document.querySelectorAll('.rating-stars');
  dom.ratingValue1 = document.getElementById('rating-value-1');
  dom.ratingValue2 = document.getElementById('rating-value-2');
  dom.winnerModel1Btn = document.getElementById('winner-model-1');
  dom.winnerModel2Btn = document.getElementById('winner-model-2');
  dom.winnerTieBtn = document.getElementById('winner-tie');

  // Элементы ввода промта и настроек
  dom.promptInput = document.getElementById('prompt-input');
  dom.charCounter = document.getElementById('char-counter');
  dom.sendButton = document.getElementById('send-button');
  dom.maxTokensInput = document.getElementById('max-tokens');
  dom.temperatureInput = document.getElementById('temperature');
  dom.temperatureValue = document.getElementById('temperature-value');

  // Редактор/визуализатор
  dom.outputArea = document.getElementById('output-area');
  dom.toggleVisualizerBtn = document.getElementById('toggle-visualizer');
  dom.toggleEditorBtn = document.getElementById('toggle-editor');
  dom.codeVisualizer = document.getElementById('code-visualizer');
  dom.codeEditor = document.getElementById('code-editor');
  dom.editorLanguage = document.getElementById('editor-language');
  dom.toggleRunBtn = document.getElementById('toggle-run');
  dom.toggleOutputPanelBtn = document.getElementById('toggle-output-panel');

  // Модальные окна
  dom.apiKeysModal = document.getElementById('api-keys-modal');
  dom.apiKeysContainer = document.getElementById('api-keys-container');
  dom.saveApiKeysBtn = document.getElementById('save-api-keys');
  dom.leaderboardModal = document.getElementById('leaderboard-modal');
  dom.leaderboardCategory = document.getElementById('leaderboard-category');
  dom.leaderboardData = document.getElementById('leaderboard-data');
  dom.closeModalBtns = document.querySelectorAll('.close-modal');
  dom.loginModal = document.getElementById('login-modal');
  dom.loginForm = document.getElementById('login-form');

  // Шаблоны
  dom.templates = {
    modelItem: document.getElementById('model-item-template'),
    categoryItem: document.getElementById('category-item-template'),
    userMessage: document.getElementById('user-message-template'),
    aiMessage: document.getElementById('ai-message-template'),
    notification: document.getElementById('notification-template')
  };

  // Новые элементы для шаблонов промтов
  dom.modeUtils = document.querySelector('.mode-utils');
  dom.templatesPanel = document.getElementById('templates-panel');
  dom.createTemplateBtn = document.getElementById('create-template-btn');
  dom.templatesList = document.getElementById('templates-list');
  dom.templateSearch = document.getElementById('template-search');
  dom.templateTagFilter = document.getElementById('template-tag-filter');
  
  // Модальное окно шаблонов
  dom.templateModal = document.getElementById('template-modal');
  dom.templateForm = document.getElementById('template-form');
  dom.templateName = document.getElementById('template-name');
  dom.templateDescription = document.getElementById('template-description');
  dom.templatePromptText = document.getElementById('template-prompt-text');
  dom.templateTags = document.getElementById('template-tags');
  dom.templateIsPublic = document.getElementById('template-is-public');
  dom.templateSaveBtn = document.getElementById('template-save-btn');
  dom.templateModalTitle = document.getElementById('template-modal-title');
  
  // Элементы для индивидуальных настроек моделей
  dom.model1ParamsToggle = document.getElementById('model1-params-toggle');
  dom.model2ParamsToggle = document.getElementById('model2-params-toggle');
  dom.model1ParamsPanel = document.getElementById('model1-params-panel');
  dom.model2ParamsPanel = document.getElementById('model2-params-panel');
  dom.model1Temperature = document.getElementById('model1-temperature');
  dom.model2Temperature = document.getElementById('model2-temperature');
  dom.model1TemperatureValue = document.getElementById('model1-temperature-value');
  dom.model2TemperatureValue = document.getElementById('model2-temperature-value');
  dom.model1MaxTokens = document.getElementById('model1-max-tokens');
  dom.model2MaxTokens = document.getElementById('model2-max-tokens');
  dom.model1SystemPrompt = document.getElementById('model1-system-prompt');
  dom.model2SystemPrompt = document.getElementById('model2-system-prompt');
  dom.comparisonMessages1 = document.getElementById('comparison-messages-1');
  dom.comparisonMessages2 = document.getElementById('comparison-messages-2');
  dom.comparisonModel1Name = document.getElementById('comparison-model-1-name');
  dom.comparisonModel2Name = document.getElementById('comparison-model-2-name');
}

// --- Инициализация приложения ---
document.addEventListener('DOMContentLoaded', async () => {
  console.log('🚀 Инициализация Промт Арены...');
  
  // Инициализирует ссылки на DOM-элементы
  initDomReferences();

  // Проверяем авторизацию
  // Используем расширенную версию checkAuthentication из auth-fix.js
  await checkAuthentication();
  
  // Устанавливаем обработчики событий
  setupEventListeners();
  
  // Инициализируем редактор Monaco, если он нужен
  initMonacoEditor();
  
  // Загружаем начальные данные
  try {
    // Загружаем категории
    await fetchCategories();
    
    // Загружаем API ключи
    await fetchApiKeys();
    
    // Загружаем список моделей (требует ключей)
    await fetchModels();
    
    // Проверяем, есть ли уже API ключи, если нет - показываем модальное окно
    if (Object.keys(state.apiKeys).length === 0) {
      showNotification('Добавьте API ключи для работы с моделями', 'info', 8000);
      await fetchProviders();
      showModal(dom.apiKeysModal);
    }
  } catch (error) {
    console.error('Ошибка при инициализации данных:', error);
    showNotification('Ошибка загрузки данных. Пожалуйста, обновите страницу.', 'error');
  }
});

// Модифицируем обработчик DOMContentLoaded для добавления новых инициализаций
document.addEventListener('DOMContentLoaded', () => {
  loadSavedSettings();
  
  // Инициализация для шаблонов промтов
  if (typeof fetchPromptTemplates === 'function') {
    fetchPromptTemplates();
  }
  
  // Инициализация для фильтрации шаблонов
  if (dom.templateSearch) {
    dom.templateSearch.addEventListener('input', debounce(() => {
      filterTemplates();
    }, DEBOUNCE_DELAY));

    if (dom.templateTagFilter) {
      dom.templateTagFilter.addEventListener('change', () => {
        filterTemplates();
      });
    }
  }
});

/**
 * Проверяет авторизацию пользователя
 * Используем расширенную версию из auth-fix.js
 */
// const checkAuthentication = async () => {
//   const basicAuth = localStorage.getItem('basic_auth');
//   
//   if (!basicAuth && dom.loginModal) {
//     showModal(dom.loginModal);
//   }
// }

/**
 * Устанавливает все обработчики событий
 */
function setupEventListeners() {
  // Поиск моделей с debounce
  dom.modelSearch.addEventListener('input', debounce(function(e) {
    filterModels(e.target.value);
  }, DEBOUNCE_DELAY));

  // Переключение режимов
  dom.modeSingleBtn.addEventListener('click', switchToSingleView);
  dom.modeCompareBtn.addEventListener('click', switchToCompareView);

  // Настройки и отладка
  dom.toggleSettingsBtn.addEventListener('click', () => {
    state.settingsVisible = !state.settingsVisible;
    dom.settingsPanel.classList.toggle('hidden', !state.settingsVisible);
  });

  // Значение температуры
  dom.temperatureInput.addEventListener('input', (e) => {
    const value = parseFloat(e.target.value).toFixed(1);
    dom.temperatureValue.textContent = value;
  });

  // Отправка промта
  dom.sendButton.addEventListener('click', handleSendPrompt);

  // Обработчик клавиш для промта (Ctrl+Enter для отправки)
  dom.promptInput.addEventListener('keydown', (e) => {
    if ((e.key === 'Enter' && e.ctrlKey) || (e.key === 'Enter' && e.metaKey)) {
      e.preventDefault();
      handleSendPrompt();
    }
  });

  // Счетчик символов в промте
  dom.promptInput.addEventListener('input', (e) => {
    const length = e.target.value.length;
    dom.charCounter.textContent = length;
    
    // Изменяем цвет при приближении к лимиту
    if (length > MAX_CHAR_COUNT * 0.8) {
      dom.charCounter.style.color = '#f59e0b'; // Желтый
    } else if (length > MAX_CHAR_COUNT) {
      dom.charCounter.style.color = '#ef4444'; // Красный
    } else {
      dom.charCounter.style.color = ''; // Сброс к дефолтному цвету
    }
    
    // Активируем кнопку отправки, если поле не пустое
    dom.sendButton.disabled = e.target.value.trim() === '';
  });

  // Очистка чата
  dom.clearChatBtn.addEventListener('click', clearChat);

  // Обработчики кнопок в выбранных моделях
  dom.model1Info?.querySelector('button')?.addEventListener('click', () => {
    state.selectedModel1 = null;
    updateSelectedModelsDisplay();
  });

  dom.model2Info?.querySelector('button')?.addEventListener('click', () => {
    state.selectedModel2 = null;
    updateSelectedModelsDisplay();
  });

  // Обработчики API ключей
  dom.setupKeysBtn.addEventListener('click', async () => {
    const providers = await fetchProviders();
    await renderApiKeysModal(providers);
    showModal(dom.apiKeysModal);
  });

  dom.saveApiKeysBtn.addEventListener('click', saveAllApiKeys);

  // Закрытие модальных окон
  dom.closeModalBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-backdrop');
      hideModal(modal);
    });
  });

  // Обработка клика вне модального окна для закрытия
  document.addEventListener('click', (e) => {
    const modals = document.querySelectorAll('.modal-backdrop:not(.hidden)');
    modals.forEach(modal => {
      if (e.target === modal) {
        hideModal(modal);
      }
    });
  });

  // Кнопка ESC для закрытия модальных окон
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const modal = document.querySelector('.modal-backdrop:not(.hidden)');
      if (modal) {
        hideModal(modal);
      }
    }
  });

  // Лидерборд
  dom.viewLeaderboardBtn.addEventListener('click', async () => {
    try {
      showModal(dom.leaderboardModal);
      await fetchLeaderboard();
    } catch (error) {
      showNotification('Ошибка загрузки лидерборда', 'error');
    }
  });

  dom.leaderboardCategory.addEventListener('change', async (e) => {
    try {
      await fetchLeaderboard(e.target.value);
    } catch (error) {
      showNotification('Ошибка загрузки лидерборда', 'error');
    }
  });

  // Рейтинги в режиме сравнения
  dom.ratingStars.forEach(starsContainer => {
    const stars = starsContainer.querySelectorAll('.star');
    const modelNum = starsContainer.dataset.model;
    const ratingValueEl = document.getElementById(`rating-value-${modelNum}`);
    
    stars.forEach(star => {
      star.addEventListener('click', (e) => {
        const rating = parseInt(e.target.dataset.value);
        
        // Подсвечиваем звезды
        stars.forEach(s => {
          s.classList.toggle('active', parseInt(s.dataset.value) <= rating);
        });
        
        // Обновляем отображение рейтинга
        if (ratingValueEl) {
          ratingValueEl.textContent = `${rating}/10`;
        }
        
        // Сохраняем оценку
        if (modelNum === '1') {
          state.currentRatings.model1 = rating;
        } else {
          state.currentRatings.model2 = rating;
        }
        
        // Если рейтинг дается модели в одиночном режиме
        if (state.currentView === 'single' && modelNum === '1' && state.selectedModel1) {
          submitRating(state.selectedModel1.id, state.currentPrompt, rating);
        }
      });
      
      // Добавляем анимацию при наведении
      star.addEventListener('mouseenter', (e) => {
        const rating = parseInt(e.target.dataset.value);
        stars.forEach(s => {
          s.classList.toggle('hover', parseInt(s.dataset.value) <= rating && 
                                      !s.classList.contains('active'));
        });
      });
      
      star.addEventListener('mouseleave', () => {
        stars.forEach(s => s.classList.remove('hover'));
      });
    });
  });

  // Выбор победителя в сравнении
  dom.winnerModel1Btn.addEventListener('click', () => {
    state.currentComparisonWinner = 'model_1';
    updateWinnerButtons('model_1');
    
    // Автоматически отправляем оценки, если были проставлены звезды
    if (state.currentRatings.model1 > 0) {
      submitRating(state.selectedModel1.id, state.currentPrompt, state.currentRatings.model1, 'model_1');
    }
    
    if (state.currentRatings.model2 > 0) {
      submitRating(state.selectedModel2.id, state.currentPrompt, state.currentRatings.model2, 'model_1');
    }
  });

  dom.winnerModel2Btn.addEventListener('click', () => {
    state.currentComparisonWinner = 'model_2';
    updateWinnerButtons('model_2');
    
    // Автоматически отправляем оценки, если были проставлены звезды
    if (state.currentRatings.model1 > 0) {
      submitRating(state.selectedModel1.id, state.currentPrompt, state.currentRatings.model1, 'model_2');
    }
    
    if (state.currentRatings.model2 > 0) {
      submitRating(state.selectedModel2.id, state.currentPrompt, state.currentRatings.model2, 'model_2');
    }
  });

  dom.winnerTieBtn.addEventListener('click', () => {
    state.currentComparisonWinner = 'tie';
    updateWinnerButtons('tie');
    
    // Автоматически отправляем оценки, если были проставлены звезды
    if (state.currentRatings.model1 > 0) {
      submitRating(state.selectedModel1.id, state.currentPrompt, state.currentRatings.model1, 'tie');
    }
    
    if (state.currentRatings.model2 > 0) {
      submitRating(state.selectedModel2.id, state.currentPrompt, state.currentRatings.model2, 'tie');
    }
  });

  // Редактор/визуализатор
  dom.toggleVisualizerBtn.addEventListener('click', () => {
    state.editorMode = 'visualizer';
    showVisualizer();
  });

  dom.toggleEditorBtn.addEventListener('click', () => {
    state.editorMode = 'editor';
    showEditor();
  });

  dom.editorLanguage.addEventListener('change', (e) => {
    if (state.editorInstance) {
      monaco.editor.setModelLanguage(state.editorInstance.getModel(), e.target.value);
    }
  });

  dom.toggleRunBtn.addEventListener('click', () => {
    runCurrentCode();
  });

  dom.toggleOutputPanelBtn.addEventListener('click', () => {
    toggleOutputPanel();
  });

  // Обработка формы логина
  if (dom.loginForm) {
    dom.loginForm.addEventListener('submit', async (e) => {
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
        
        // Пробуем получить категории для проверки
        const resp = await fetch(`${API_BASE_URL}/status`, {
          headers: { 'Authorization': authHeader }
        });
        
        if (resp.status === 401) {
          throw new Error('Неверный логин или пароль');
        }
        
        // Если успешно, сохраняем base64 в localStorage
        localStorage.setItem('basic_auth', authHeader);
        showNotification('Успешный вход!', 'success');
        hideModal(dom.loginModal);
        
        // Перезагружаем данные
        await fetchCategories();
        await fetchApiKeys();
        await fetchModels();
      } catch (error) {
        showNotification(error.message || 'Ошибка входа', 'error');
      }
    });
  }

  // Переключатель видимости панели шаблонов
  const toggleTemplatesBtn = document.createElement('button');
  toggleTemplatesBtn.id = 'toggle-templates';
  toggleTemplatesBtn.className = 'util-btn';
  toggleTemplatesBtn.setAttribute('aria-label', 'Шаблоны промтов');
  toggleTemplatesBtn.setAttribute('title', 'Шаблоны промтов');
  toggleTemplatesBtn.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
      <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
    </svg>
  `;
  
  // Добавляем кнопку в панель утилит рядом с существующими кнопками
  dom.modeUtils.insertBefore(toggleTemplatesBtn, dom.toggleSettingsBtn);

  // Обработчик для переключения видимости панели шаблонов
  toggleTemplatesBtn.addEventListener('click', () => {
    state.templatesVisible = !state.templatesVisible;
    
    if (state.templatesVisible) {
      // Показываем панель шаблонов
      dom.templatesPanel.classList.remove('hidden');
      fetchPromptTemplates(); // Загружаем шаблоны при открытии панели
    } else {
      // Скрываем панель шаблонов
      dom.templatesPanel.classList.add('hidden');
    }
  });

  // Кнопка создания нового шаблона
  dom.createTemplateBtn.addEventListener('click', () => {
    openTemplateModal();
  });

  // Закрытие модального окна шаблонов
  document.querySelector('.modal-close').addEventListener('click', closeTemplateModal);
  document.querySelector('.modal-cancel').addEventListener('click', closeTemplateModal);

  // Сохранение шаблона
  dom.templateForm.addEventListener('submit', (e) => {
    e.preventDefault();
    saveTemplate();
  });

  // Поиск шаблонов
  dom.templateSearch.addEventListener('input', debounce(() => {
    filterTemplates();
  }, DEBOUNCE_DELAY));

  // Фильтр по тегам
  dom.templateTagFilter.addEventListener('change', () => {
    filterTemplates();
  });

  // Обработчики для параметров моделей в режиме сравнения
  dom.model1ParamsToggle.addEventListener('click', () => toggleModelParams('model1'));
  dom.model2ParamsToggle.addEventListener('click', () => toggleModelParams('model2'));

  // Слайдеры температуры моделей
  dom.model1Temperature.addEventListener('input', () => {
    const value = dom.model1Temperature.value;
    dom.model1TemperatureValue.textContent = value;
    state.model1Settings.temperature = parseFloat(value);
  });

  dom.model2Temperature.addEventListener('input', () => {
    const value = dom.model2Temperature.value;
    dom.model2TemperatureValue.textContent = value;
    state.model2Settings.temperature = parseFloat(value);
  });

  // Поля ввода максимального числа токенов
  dom.model1MaxTokens.addEventListener('change', () => {
    state.model1Settings.maxTokens = parseInt(dom.model1MaxTokens.value);
  });

  dom.model2MaxTokens.addEventListener('change', () => {
    state.model2Settings.maxTokens = parseInt(dom.model2MaxTokens.value);
  });

  // Поля ввода системных промтов
  dom.model1SystemPrompt.addEventListener('change', () => {
    state.model1Settings.systemPrompt = dom.model1SystemPrompt.value;
  });

  dom.model2SystemPrompt.addEventListener('change', () => {
    state.model2Settings.systemPrompt = dom.model2SystemPrompt.value;
  });
}

// --- API функции ---
// Используем расширенные версии checkAuthentication и fetchApi из auth-fix.js
// const fetchApi = async (url, options = {}) => {
//   // ...
// }

/**
 * Базовая функция для взаимодействия с API
 * @param {string} url - путь к эндпоинту API
 * @param {object} options - параметры запроса
 * @returns {Promise<any>} - данные от API
 */
async function fetchApi(url, options = {}) {
  // Используем расширенную версию fetchApi из auth-fix.js
  return await fetchApi(url, options);
}

/**
 * Получение структуры категорий
 */
async function fetchCategories() {
  try {
    const data = await fetchApi('/categories');
    state.categories = data;
    renderCategories(data);
    console.log('Категории загружены:', data);
    
    // Заполняем выпадающий список категорий для лидерборда
    populateLeaderboardCategories(data);
    return data;
  } catch (error) {
    console.error('Ошибка при загрузке категорий:', error);
    showNotification('Не удалось загрузить категории', 'error');
    throw error;
  }
}

/**
 * Получение списка моделей
 * @param {string} categoryId - ID категории для фильтрации (опционально)
 */
async function fetchModels(categoryId = null) {
  try {
    state.isLoadingModels = true;
    
    let url = '/models';
    if (categoryId) {
      url += `?category=${encodeURIComponent(categoryId)}`;
    }
    
    const data = await fetchApi(url);
    state.allModels = data;
    state.filteredModels = data;
    renderModels(data);
    console.log('Модели загружены:', data.length);
    
    // Проверяем, есть ли модели, если нет - подсказываем добавить ключи
    if (data.length === 0) {
      const keysExist = Object.keys(state.apiKeys).length > 0;
      if (!keysExist) {
        showNotification('Добавьте API ключи, чтобы загрузить доступные модели', 'info', 5000);
      } else {
        showNotification('Нет доступных моделей для текущих API ключей', 'warning');
      }
    }
    
    // Обновляем интерфейс для отображения выбранных моделей
    updateSelectedModelsDisplay();
    
    // Включаем кнопку отправки, если есть хотя бы одна выбранная модель
    dom.sendButton.disabled = !(state.selectedModel1 || state.selectedModel2);
    
    state.isLoadingModels = false;
    return data;
  } catch (error) {
    state.isLoadingModels = false;
    console.error('Ошибка при загрузке моделей:', error);
    showNotification('Не удалось загрузить модели', 'error');
    throw error;
  }
}

/**
 * Получение списка API ключей
 */
async function fetchApiKeys() {
  try {
    const data = await fetchApi('/keys');
    // Преобразуем массив в объект для удобства доступа
    state.apiKeys = {};
    data.forEach(key => {
      state.apiKeys[key.provider] = key;
    });
    console.log('API ключи загружены:', Object.keys(state.apiKeys));
    return data;
  } catch (error) {
    console.error('Ошибка при загрузке API ключей:', error);
    showNotification('Не удалось загрузить API ключи', 'error');
    throw error;
  }
}

/**
 * Получение списка поддерживаемых провайдеров
 */
async function fetchProviders() {
  try {
    const data = await fetchApi('/config/providers');
    console.log('Провайдеры загружены:', Object.keys(data));
    
    // Если модальное окно видимо, обновляем его содержимое
    if (!dom.apiKeysModal.classList.contains('hidden')) {
      await renderApiKeysModal(data);
    }
    
    return data;
  } catch (error) {
    console.error('Ошибка при загрузке провайдеров:', error);
    showNotification('Не удалось загрузить список провайдеров', 'error');
    throw error;
  }
}

/**
 * Сохранение API ключа для провайдера
 * @param {string} provider - ID провайдера
 * @param {string} apiKey - API ключ
 */
async function saveApiKey(provider, apiKey) {
  try {
    if (!apiKey || apiKey.trim() === '') {
      throw new Error('API ключ не может быть пустым');
    }
    
    const data = await fetchApi('/keys', {
      method: 'POST',
      body: {
        provider,
        api_key: apiKey
      }
    });
    
    // Очищаем кеш моделей для этого провайдера
    await fetchApi(`/keys/${provider}/clear-cache`, {
      method: 'POST'
    });
    
    showNotification(`API ключ для ${provider} успешно сохранен`, 'success');
    return data;
  } catch (error) {
    console.error(`Ошибка при сохранении API ключа для ${provider}:`, error);
    showNotification(`Ошибка сохранения ключа для ${provider}: ${error.message || 'Неизвестная ошибка'}`, 'error');
    throw error;
  }
}

/**
 * Удаление API ключа для провайдера
 * @param {string} provider - ID провайдера
 */
async function deleteApiKey(provider) {
  try {
    await fetchApi(`/keys/${provider}`, {
      method: 'DELETE'
    });
    
    // Удаляем ключ из локального объекта
    if (state.apiKeys[provider]) {
      delete state.apiKeys[provider];
    }
    
    showNotification(`API ключ для ${provider} удален`, 'success');
    return true;
  } catch (error) {
    console.error(`Ошибка при удалении API ключа для ${provider}:`, error);
    showNotification(`Ошибка удаления ключа для ${provider}: ${error.message || 'Неизвестная ошибка'}`, 'error');
    throw error;
  }
}

/**
 * Отправляет промт одной модели
 * @param {string} modelId - ID модели
 * @param {string} prompt - Текст промта
 * @param {object} params - Дополнительные параметры (max_tokens, temperature)
 */
async function sendPromptToModel(modelId, prompt, params = {}) {
  try {
    const requestBody = {
      model_id: modelId,
      prompt: prompt,
      ...params
    };
    
    const response = await fetchApi('/interact', {
      method: 'POST',
      body: requestBody
    });
    
    return response;
  } catch (error) {
    console.error(`Ошибка при отправке промта к модели ${modelId}:`, error);
    
    // Создаем объект ответа с ошибкой для унификации обработки
    return {
      model_id: modelId,
      response: '',
      error: error.data?.detail || error.message || 'Неизвестная ошибка при обращении к API'
    };
  }
}

/**
 * Отправляет промт двум моделям для сравнения
 * @param {string} modelId1 - ID первой модели
 * @param {string} modelId2 - ID второй модели
 * @param {string} prompt - Текст промта
 * @param {object} params - Дополнительные параметры (max_tokens, temperature)
 */
async function sendComparisonPrompt(modelId1, modelId2, prompt, params = {}) {
  try {
    // Создаем индивидуальные параметры для каждой модели
    const model1Params = {
      max_tokens: state.model1Settings.maxTokens,
      temperature: state.model1Settings.temperature,
      system_prompt: state.model1Settings.systemPrompt || null
    };

    const model2Params = {
      max_tokens: state.model2Settings.maxTokens,
      temperature: state.model2Settings.temperature,
      system_prompt: state.model2Settings.systemPrompt || null
    };

    const response = await fetchApi(`/interactions/compare`, {
      method: 'POST',
      body: JSON.stringify({
        model_id_1: modelId1,
        model_id_2: modelId2,
        prompt: prompt,
        ...model1Params,
        ...model2Params
      })
    });
    
    return response;
  } catch (error) {
    console.error('Ошибка при сравнении моделей:', error);
    throw error;
  }
}

/**
 * Отправляет оценку модели
 * @param {string} modelId - ID модели
 * @param {string} promptText - Текст промта
 * @param {number} rating - Оценка (1-10)
 * @param {string} comparisonWinner - Победитель в сравнении (null, 'model_1', 'model_2', 'tie')
 */
async function submitRating(modelId, promptText, rating, comparisonWinner = null) {
  try {
    if (!rating || rating < 1 || rating > 10) {
      throw new Error('Оценка должна быть от 1 до 10');
    }
    
    const requestBody = {
      model_id: modelId,
      prompt_text: promptText,
      rating: rating,
      comparison_winner: comparisonWinner,
      user_identifier: getUserIdentifier()
    };
    
    const response = await fetchApi('/rate', {
      method: 'POST',
      body: requestBody
    });
    
    showNotification(`Ваша оценка (${rating}/10) успешно сохранена`, 'success');
    return response;
  } catch (error) {
    console.error(`Ошибка при отправке оценки для модели ${modelId}:`, error);
    showNotification(`Ошибка сохранения оценки: ${error.message || 'Неизвестная ошибка'}`, 'error');
    throw error;
  }
}

/**
 * Получает идентификатор пользователя или сессии
 * Для анонимных пользователей генерирует и сохраняет в localStorage
 */
function getUserIdentifier() {
  let userId = localStorage.getItem('promptArenaUserId');
  if (!userId) {
    userId = 'user_' + Math.random().toString(36).substring(2, 15);
    localStorage.setItem('promptArenaUserId', userId);
  }
  return userId;
}

/**
 * Получает данные лидерборда
 * @param {string} categoryId - ID категории для фильтрации (опционально)
 */
async function fetchLeaderboard(categoryId = null) {
  try {
    dom.leaderboardData.innerHTML = '<tr><td colspan="7" class="text-center py-4">Загрузка данных...</td></tr>';
    
    let url = '/leaderboard';
    if (categoryId) {
      url += `?category=${encodeURIComponent(categoryId)}`;
    }
    
    const data = await fetchApi(url);
    renderLeaderboard(data);
    console.log('Лидерборд загружен:', data);
    return data;
  } catch (error) {
    console.error('Ошибка при загрузке лидерборда:', error);
    showNotification('Не удалось загрузить лидерборд', 'error');
    throw error;
  }
}

// --- Функции рендеринга UI ---

/**
 * Рендерит древовидный список категорий
 * @param {Array} categoriesList - список категорий из API
 * @param {HTMLElement} container - контейнер для отображения
 * @param {number} level - уровень вложенности (для рекурсии)
 */
function renderCategories(categoriesList, container = dom.categoriesContainer, level = 0) {
  // Очищаем контейнер для первого уровня
  if (level === 0) {
    container.innerHTML = '';
  }
  
  categoriesList.forEach(category => {
    // Клонируем шаблон для категории
    const categoryEl = dom.templates.categoryItem.content.cloneNode(true).querySelector('.category-item');
    
    // Добавляем подкласс для подкатегорий
    if (level > 0) {
      categoryEl.classList.add('subcategory-item');
    }
    
    // Устанавливаем id и имя категории
    categoryEl.dataset.categoryId = category.id;
    categoryEl.querySelector('.category-name').textContent = category.name;
    
    // Добавляем иконку, если есть подкатегории
    if (category.subcategories?.length) {
      const icon = document.createElement('span');
      icon.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
      `;
      categoryEl.appendChild(icon);
    }
    
    // Добавляем обработчик клика
    categoryEl.addEventListener('click', () => handleCategoryClick(category.id));
    
    container.appendChild(categoryEl);
    
    // Рекурсивно отображаем подкатегории, если они есть
    if (category.subcategories && category.subcategories.length > 0) {
      // Создаем контейнер для подкатегорий
      const subcatContainer = document.createElement('div');
      subcatContainer.classList.add('subcategory-container');
      subcatContainer.style.display = 'none'; // Скрыты по умолчанию
      container.appendChild(subcatContainer);
      
      renderCategories(category.subcategories, subcatContainer, level + 1);
      
      // Добавляем обработчик для раскрытия/скрытия подкатегорий
      categoryEl.addEventListener('click', (e) => {
        e.stopPropagation();
        subcatContainer.style.display = subcatContainer.style.display === 'none' ? 'block' : 'none';
        const icon = categoryEl.querySelector('svg');
        if (icon) {
          icon.style.transform = subcatContainer.style.display === 'none' ? 'rotate(0deg)' : 'rotate(180deg)';
        }
      });
    }
  });
}

/**
 * Заполняет список категорий для фильтрации лидерборда
 * @param {Array} categoriesList - список категорий из API
 */
function populateLeaderboardCategories(categoriesList) {
  // Рекурсивная функция для добавления всех категорий и подкатегорий
  function addCategories(categories, prefix = '') {
    categories.forEach(category => {
      const option = document.createElement('option');
      option.value = category.id;
      option.textContent = prefix + category.name;
      dom.leaderboardCategory.appendChild(option);
      
      if (category.subcategories && category.subcategories.length > 0) {
        addCategories(category.subcategories, prefix + '• ');
      }
    });
  }
  
  // Очищаем все, кроме первого пункта "Все категории"
  while (dom.leaderboardCategory.children.length > 1) {
    dom.leaderboardCategory.removeChild(dom.leaderboardCategory.lastChild);
  }
  
  // Добавляем категории
  addCategories(categoriesList);
}

/**
 * Рендерит список моделей
 * @param {Array} modelsList - список моделей из API
 */
function renderModels(modelsList) {
  dom.modelsContainer.innerHTML = '';
  
  if (state.isLoadingModels) {
    // Отображаем скелетон загрузки
    for (let i = 0; i < 5; i++) {
      const skeleton = document.createElement('div');
      skeleton.className = 'skeleton h-16 mb-2';
      dom.modelsContainer.appendChild(skeleton);
    }
    return;
  }
  
  if (modelsList.length === 0) {
    dom.modelsContainer.innerHTML = `
      <div class="text-center text-gray-500 my-6 p-4">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 mx-auto mb-2 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
        <p>Нет доступных моделей для выбранных параметров</p>
        <p class="text-sm mt-2">Протестируйте модели и дайте им оценки, чтобы они появились в лидерборде</p>
      </div>
    `;
    return;
  }
  
  modelsList.forEach(model => {
    // Клонируем шаблон модели
    const modelItem = dom.templates.modelItem.content.cloneNode(true).querySelector('.model-item');
    
    // Добавляем классы, если модель выбрана
    if (state.selectedModel1 && state.selectedModel1.id === model.id) {
      modelItem.classList.add('selected-model-1');
    } else if (state.selectedModel2 && state.selectedModel2.id === model.id) {
      modelItem.classList.add('selected-model-2');
    }
    
    // Устанавливаем данные модели
    modelItem.dataset.modelId = model.id;
    modelItem.querySelector('.model-name').textContent = model.name;
    modelItem.querySelector('.model-provider').textContent = model.provider;
    
    // Добавляем бейдж категории, если она есть
    const categoryBadge = modelItem.querySelector('.model-category-badge');
    if (model.category) {
      categoryBadge.textContent = formatCategoryName(model.category);
    } else {
      categoryBadge.style.display = 'none';
    }
    
    // Добавляем обработчик клика
    modelItem.addEventListener('click', () => handleModelSelect(model));
    
    dom.modelsContainer.appendChild(modelItem);
  });
}

/**
 * Форматирует имя категории для отображения
 * @param {string} categoryId - ID категории
 */
function formatCategoryName(categoryId) {
  // Если это ID подкатегории (например, programming_general), берем только последнюю часть
  if (categoryId.includes('_')) {
    const parts = categoryId.split('_');
    return parts[parts.length - 1].charAt(0).toUpperCase() + parts[parts.length - 1].slice(1);
  }
  return categoryId.charAt(0).toUpperCase() + categoryId.slice(1);
}

/**
 * Фильтрует список моделей по поисковому запросу
 * @param {string} query - поисковый запрос
 */
function filterModels(query) {
  if (!query) {
    state.filteredModels = [...state.allModels];
  } else {
    const lowerQuery = query.toLowerCase();
    state.filteredModels = state.allModels.filter(model => {
      return model.name.toLowerCase().includes(lowerQuery) || 
             model.provider.toLowerCase().includes(lowerQuery) || 
             (model.category && model.category.toLowerCase().includes(lowerQuery));
    });
  }
  
  renderModels(state.filteredModels);
}

/**
 * Обновляет индикаторы выбранных моделей
 */
function updateSelectedModelsDisplay() {
  // Скрываем/показываем элементы
  dom.model1Info.classList.toggle('hidden', !state.selectedModel1);
  dom.model2Info.classList.toggle('hidden', !state.selectedModel2);
  dom.noModelSelected.classList.toggle('hidden', state.selectedModel1 || state.selectedModel2);
  
  // Обновляем информацию о моделях
  if (state.selectedModel1) {
    dom.model1Info.querySelector('.model-name').textContent = state.selectedModel1.name;
    dom.model1Name.textContent = state.selectedModel1.name;
  }
  
  if (state.selectedModel2) {
    dom.model2Info.querySelector('.model-name').textContent = state.selectedModel2.name;
    dom.model2Name.textContent = state.selectedModel2.name;
  }
  
  // Активируем кнопку отправки, если выбрана хотя бы одна модель и в поле промта есть текст
  dom.sendButton.disabled = !(state.selectedModel1 || state.selectedModel2) || dom.promptInput.value.trim() === '';
  
  // Обновляем список моделей, чтобы показать выбранные
  renderModels(state.filteredModels);
}

/**
 * Отображает сообщение пользователя в чате
 * @param {string} message - текст сообщения
 * @param {string} targetAreaId - ID контейнера для отображения
 */
function renderUserMessage(message, targetAreaId) {
  // Санитизация сообщения от XSS
  const sanitizedMessage = escapeHtml(message);
  
  const messageContainer = document.getElementById(targetAreaId);
  
  // Если первое сообщение, удаляем placeholder
  const emptyState = messageContainer.querySelector('.chat-empty-state');
  if (emptyState) {
    messageContainer.removeChild(emptyState);
  }
  
  // Клонируем шаблон сообщения
  const messageEl = dom.templates.userMessage.content.cloneNode(true).querySelector('.chat-message');
  
  // Заполняем содержимое с использованием textContent для безопасности
  messageEl.querySelector('.message-content').textContent = sanitizedMessage;
  messageEl.querySelector('.message-timestamp').textContent = formatTime(new Date());
  
  messageContainer.appendChild(messageEl);
  messageContainer.scrollTop = messageContainer.scrollHeight;
}

/**
 * Отображает сообщение от модели в чате
 * @param {string} message - текст сообщения
 * @param {string} targetAreaId - ID контейнера для отображения
 * @param {boolean} isError - является ли сообщение ошибкой
 */
function renderModelMessage(message, targetAreaId, isError = false) {
  const messageContainer = document.getElementById(targetAreaId);
  
  // Если первое сообщение, удаляем placeholder
  const emptyState = messageContainer.querySelector('.chat-empty-state');
  if (emptyState) {
    messageContainer.removeChild(emptyState);
  }
  
  // Клонируем шаблон сообщения
  const messageEl = dom.templates.aiMessage.content.cloneNode(true).querySelector('.chat-message');
  
  if (isError) {
    messageEl.classList.add('error-message');
    messageEl.querySelector('.message-content').innerHTML = `
      <div class="text-red-500">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 inline-block mr-1" viewBox="0 0 20 20" fill="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
        <strong>Ошибка:</strong> ${escapeHtml(message)}
      </div>
    `;
  } else {
    // Используем marked.js для преобразования Markdown
    try {
      // Добавляем заголовок с кнопкой копирования для блоков кода
      const markedOptions = {
        highlight: (code, language) => {
          return `<div class="code-header">
                   <span class="code-language">${language || 'Код'}</span>
                   <div class="code-actions">
                     <button class="code-action-btn copy-code">Копировать</button>
                     <button class="code-action-btn run-code">Запустить</button>
                   </div>
                 </div>
                 <pre><code class="language-${language || 'text'}">${escapeHtml(code)}</code></pre>`;
        }
      };
      
      // Используем DOMPurify для безопасного HTML
      messageEl.querySelector('.message-content').innerHTML = DOMPurify.sanitize(
        marked.parse(message, markedOptions)
      );
      
      // Добавляем обработчики для кнопок кода
      messageEl.querySelectorAll('.copy-code').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const codeBlock = e.target.closest('.code-header').nextElementSibling;
          if (codeBlock) {
            const code = codeBlock.textContent;
            navigator.clipboard.writeText(code);
            btn.textContent = 'Скопировано!';
            setTimeout(() => { btn.textContent = 'Копировать'; }, 2000);
          }
        });
      });
      
      messageEl.querySelectorAll('.run-code').forEach(btn => {
        btn.addEventListener('click', () => {
          const codeHeader = e.target.closest('.code-header');
          const language = codeHeader.querySelector('.code-language').textContent.toLowerCase();
          const codeBlock = codeHeader.nextElementSibling;
          
          if (codeBlock) {
            const code = codeBlock.textContent;
            openOutputPanel(code, language);
          }
        });
      });
    } catch (e) {
      console.error('Ошибка при обработке Markdown:', e);
      messageEl.querySelector('.message-content').textContent = message;
    }
  }
  
  // Устанавливаем временную метку
  messageEl.querySelector('.message-timestamp').textContent = formatTime(new Date());
  
  messageContainer.appendChild(messageEl);
  messageContainer.scrollTop = messageContainer.scrollHeight;
  
  // Чтобы не перегружать DOM, ограничиваем количество сообщений
  const MAX_MESSAGES = 50;
  const messages = messageContainer.querySelectorAll('.chat-message');
  if (messages.length > MAX_MESSAGES) {
    for (let i = 0; i < messages.length - MAX_MESSAGES; i++) {
      messageContainer.removeChild(messages[i]);
    }
  }
}

/**
 * Отображает индикатор загрузки в области чата
 * @param {string} targetAreaId - ID элемента, куда добавить индикатор
 * @returns {HTMLElement} - созданный элемент индикатора загрузки
 */
function renderLoadingMessage(targetAreaId) {
  const targetArea = document.getElementById(targetAreaId);
  
  // Создаем элемент сообщения загрузки
  const loadingElement = document.createElement('div');
  loadingElement.classList.add('chat-message', 'ai-message', 'loading-message');
  
  // Создаем анимацию загрузки с тремя точками
  loadingElement.innerHTML = `
    <div class="message-header">
      <div class="message-avatar">AI</div>
      <div class="message-timestamp">${formatTime(new Date())}</div>
    </div>
    <div class="flex items-center p-2">
      <div class="loading-dots flex">
        <span class="w-2 h-2 bg-gray-600 rounded-full mr-1 animate-pulse"></span>
        <span class="w-2 h-2 bg-gray-600 rounded-full mr-1 animate-pulse" style="animation-delay: 0.2s"></span>
        <span class="w-2 h-2 bg-gray-600 rounded-full animate-pulse" style="animation-delay: 0.4s"></span>
      </div>
    </div>
  `;
  
  targetArea.appendChild(loadingElement);
  targetArea.scrollTop = targetArea.scrollHeight;
  
  return loadingElement;
}

/**
 * Рендерит содержимое модального окна API ключей
 * @param {Object} providers - объект провайдеров из API
 */
async function renderApiKeysModal(providers) {
  // Получаем текущие API ключи
  const keys = await fetchApiKeys();
  dom.apiKeysContainer.innerHTML = '';
  
  // Создаем элементы формы для каждого провайдера
  Object.entries(providers).forEach(([providerId, providerName]) => {
    const keyExists = state.apiKeys[providerId] !== undefined;
    
    const keyItem = document.createElement('div');
    keyItem.classList.add('api-key-item');
    
    // Информация о провайдере
    const providerDiv = document.createElement('div');
    providerDiv.innerHTML = `
      <div class="api-key-provider">${providerName}</div>
      ${getProviderUrl(providerId) ? `
        <a href="${getProviderUrl(providerId)}" class="api-key-url" target="_blank" rel="noopener noreferrer">
          Получить ключ
        </a>` 
        : ''}
    `;
    
    // Поле для ввода ключа
    const keyInput = document.createElement('input');
    keyInput.type = 'password';
    keyInput.classList.add('api-key-input');
    keyInput.placeholder = `Введите API ключ ${providerName}`;
    keyInput.dataset.provider = providerId;
    
    // Если ключ уже сохранен, показываем маску
    if (keyExists) {
      keyInput.value = '••••••••••••••••••••••••••••';
      keyInput.dataset.saved = 'true';
    }
    
    // Добавляем кнопку удаления, если ключ уже сохранен
    const actionsDiv = document.createElement('div');
    if (keyExists) {
      const deleteBtn = document.createElement('button');
      deleteBtn.classList.add('api-key-delete');
      deleteBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>';
      
      deleteBtn.addEventListener('click', async () => {
        try {
          await deleteApiKey(providerId);
          
          // Обновляем отображение
          keyInput.value = '';
          keyInput.dataset.saved = 'false';
          actionsDiv.removeChild(deleteBtn);
          
          // Обновляем списки
          await fetchModels(state.currentCategory);
        } catch (error) {
          showNotification(`Ошибка при удалении ключа: ${error.message}`, 'error');
        }
      });
      
      actionsDiv.appendChild(deleteBtn);
    }
    
    keyItem.appendChild(providerDiv);
    keyItem.appendChild(keyInput);
    keyItem.appendChild(actionsDiv);
    
    dom.apiKeysContainer.appendChild(keyItem);
  });
}

/**
 * Возвращает URL для получения API ключа для провайдера
 * @param {string} providerId - ID провайдера
 * @returns {string|null} - URL или null, если нет URL
 */
function getProviderUrl(providerId) {
  const urls = {
    'openai': 'https://platform.openai.com/api-keys',
    'google': 'https://aistudio.google.com/app/apikey',
    'anthropic': 'https://console.anthropic.com/',
    'mistral': 'https://console.mistral.ai/',
    'groq': 'https://console.groq.com/',
    'huggingface_hub': 'https://huggingface.co/settings/tokens'
  };
  
  return urls[providerId] || null;
}

/**
 * Рендерит данные лидерборда
 * @param {Array} leaderboardEntries - данные лидерборда из API
 */
function renderLeaderboard(leaderboardEntries) {
  dom.leaderboardData.innerHTML = '';
  
  if (leaderboardEntries.length === 0) {
    dom.leaderboardData.innerHTML = `
      <tr>
        <td colspan="7" class="text-center py-8">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12 mx-auto mb-2 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V9a2 2 0 012-2h2m0-4l4-4m0 0l4 4m-2 5v-1" />
          </svg>
          <p class="text-gray-500">Нет данных для отображения</p>
          <p class="text-sm text-gray-400 mt-2">Протестируйте модели и дайте им оценки, чтобы они появились в лидерборде</p>
        </td>
      </tr>
    `;
    return;
  }
  
  leaderboardEntries.forEach(entry => {
    const row = document.createElement('tr');
    
    // Ранг (с медалью для топ-3)
    const rankCell = document.createElement('td');
    rankCell.classList.add('py-2', 'px-4', 'border-b');
    if (entry.rank <= 3) {
      let medal = '🥇';
      if (entry.rank === 2) medal = '🥈';
      if (entry.rank === 3) medal = '🥉';
      rankCell.innerHTML = `<div class="leaderboard-rank"><span class="rank-medal">${medal}</span>${entry.rank}</div>`;
    } else {
      rankCell.innerHTML = `<div class="leaderboard-rank">${entry.rank}</div>`;
    }
    
    // Модель
    const modelCell = document.createElement('td');
    modelCell.classList.add('py-2', 'px-4', 'border-b');
    modelCell.innerHTML = `
      <div class="leaderboard-model">${escapeHtml(entry.name)}</div>
      <div class="leaderboard-provider">${escapeHtml(entry.provider)}</div>
    `;
    
    // Провайдер (скрыт, уже включен в ячейку модели)
    const providerCell = document.createElement('td');
    providerCell.classList.add('py-2', 'px-4', 'border-b', 'hidden', 'md:table-cell');
    providerCell.textContent = entry.provider;
    
    // Категория
    const categoryCell = document.createElement('td');
    categoryCell.classList.add('py-2', 'px-4', 'border-b', 'hidden', 'md:table-cell');
    categoryCell.textContent = entry.category ? formatCategoryName(entry.category) : '-';
    
    // Средний рейтинг
    const ratingCell = document.createElement('td');
    ratingCell.classList.add('py-2', 'px-4', 'border-b');
    
    // Отображаем звезды для первых 5 баллов
    const fullStars = Math.floor(entry.average_rating);
    const halfStar = entry.average_rating - fullStars >= 0.5;
    let stars = '★'.repeat(Math.min(fullStars, 5));
    if (halfStar && fullStars < 5) stars += '½';
    
    ratingCell.innerHTML = `
      <div class="leaderboard-rating">
        <span class="leaderboard-rating-stars">${stars}</span>
        <span>${entry.average_rating.toFixed(1)}</span>
      </div>
    `;
    
    // Количество оценок
    const countCell = document.createElement('td');
    countCell.classList.add('py-2', 'px-4', 'border-b', 'text-center');
    countCell.textContent = entry.rating_count;
    
    // Действия
    const actionsCell = document.createElement('td');
    actionsCell.classList.add('py-2', 'px-4', 'border-b', 'leaderboard-action');
    
    const selectBtn = document.createElement('button');
    selectBtn.textContent = 'Выбрать';
    selectBtn.classList.add('leaderboard-select-btn');
    selectBtn.addEventListener('click', () => {
      // Закрываем модальное окно
      hideModal(dom.leaderboardModal);
      
      // Находим полную информацию о модели
      const modelInfo = state.allModels.find(m => m.id === entry.model_id);
      if (modelInfo) {
        // Выбираем модель
        handleModelSelect(modelInfo);
      } else {
        showNotification('Модель временно недоступна', 'error');
      }
    });
    
    actionsCell.appendChild(selectBtn);
    
    row.appendChild(rankCell);
    row.appendChild(modelCell);
    row.appendChild(providerCell);
    row.appendChild(categoryCell);
    row.appendChild(ratingCell);
    row.appendChild(countCell);
    row.appendChild(actionsCell);
    
    dom.leaderboardData.appendChild(row);
  });
}

// --- Обработчики Событий ---

/**
 * Обработчик выбора категории
 * @param {string} categoryId - ID выбранной категории
 */
function handleCategoryClick(categoryId) {
  // Убираем класс active у всех категорий
  document.querySelectorAll('.category-item').forEach(item => {
    item.classList.remove('active');
  });
  
  // Добавляем класс active выбранной категории
  document.querySelector(`.category-item[data-category-id="${categoryId}"]`).classList.add('active');
  
  // Запоминаем текущую категорию
  state.currentCategory = categoryId;
  
  // Загружаем модели для этой категории
  fetchModels(categoryId);
}

/**
 * Обработчик выбора модели
 * @param {object} model - информация о выбранной модели
 */
function handleModelSelect(model) {
  if (state.currentView === 'single') {
    // В одиночном режиме просто заменяем первую модель
    state.selectedModel1 = model;
    state.selectedModel2 = null;
  } else {
    // В режиме сравнения
    if (!state.selectedModel1) {
      // Если первая не выбрана, выбираем ее
      state.selectedModel1 = model;
    } else if (!state.selectedModel2) {
      // Если первая выбрана, а вторая нет, выбираем вторую
      // Но проверяем, не выбрана ли та же самая модель
      if (state.selectedModel1.id === model.id) {
        showNotification('Пожалуйста, выберите другую модель для сравнения', 'warning');
        return;
      }
      state.selectedModel2 = model;
    } else {
      // Если обе выбраны, заменяем первую, если это не та же самая что вторая
      if (state.selectedModel2.id === model.id) {
        showNotification('Эта модель уже выбрана в качестве второй модели', 'warning');
        return;
      }
      state.selectedModel1 = model;
    }
  }
  
  // Обновляем отображение выбранных моделей
  updateSelectedModelsDisplay();
}

/**
 * Обработчик отправки промта
 */
async function handleSendPrompt() {
  // Получаем текст промта
  const promptText = dom.promptInput.value.trim();
  
  // Проверяем, не пустой ли промт
  if (!promptText) {
    showNotification('Введите текст промта', 'warning');
    return;
  }
  
  // Проверяем длину промта
  if (promptText.length > MAX_CHAR_COUNT) {
    showNotification(`Превышена максимальная длина промта (${MAX_CHAR_COUNT} символов)`, 'error');
    return;
  }
  
  // Проверяем наличие потенциально опасных скриптов
  const sensitivePatterns = [
    /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
    /javascript\s*:/gi,
    /on\w+\s*=/gi,
    /\bdata\s*:/gi
  ];
  
  const hasSuspiciousContent = sensitivePatterns.some(pattern => pattern.test(promptText));
  
  if (hasSuspiciousContent) {
    // Предупреждаем пользователя
    if (!confirm('Промт содержит потенциально небезопасный код. Вы уверены, что хотите его отправить?')) {
      return;
    }
  }
  
  // Очищаем поле ввода
  dom.promptInput.value = '';
  
  // Сохраняем промт в состоянии (нужно для сохранения рейтинга)
  state.currentPrompt = promptText;
  
  // Очищаем состояние рейтинга
  state.currentRatings = { model1: 0, model2: 0 };
  state.currentComparisonWinner = null;
  
  if (state.currentView === 'single') {
    await handleSingleModeSubmit(promptText);
  } else if (state.currentView === 'compare') {
    await handleComparisonSubmit(promptText);
  }
}

/**
 * Обрабатывает отправку промта и обновляет интерфейс в режиме сравнения
 * @param {string} prompt - Текст промта 
 */
async function handleComparisonSubmit(prompt) {
  // Проверяем, выбраны ли обе модели
  if (!state.selectedModel1 || !state.selectedModel2) {
    showNotification('Для сравнения нужно выбрать две модели', 'warning');
    return;
  }
  
  // Показываем индикатор загрузки
  state.isLoadingResponse = true;
  toggleLoadingIndicator(true);
  
  // Показываем сообщение пользователя в обоих колонках сравнения
  displayUserMessageInComparison(prompt);
  
  // Создаем сообщения AI с индикаторами загрузки
  const msg1El = createLoadingMessageForComparison(1);
  const msg2El = createLoadingMessageForComparison(2);
  
  try {
    const params = {
      max_tokens: dom.maxTokensInput.value,
      temperature: dom.temperatureInput.value
    };
    
    const result = await sendComparisonPrompt(
      state.selectedModel1.id, 
      state.selectedModel2.id, 
      prompt, 
      params
    );
    
    // Обновляем интерфейс с результатами
    updateComparisonUIWithResponse(result, msg1El, msg2El);
    
    // Сохраняем промт для возможной оценки
    state.currentPrompt = prompt;
    
  } catch (error) {
    console.error('Ошибка при сравнении моделей:', error);
    updateComparisonUIWithError(error, msg1El, msg2El);
    showNotification('Ошибка при сравнении моделей', 'error');
  } finally {
    // Убираем индикатор загрузки
    state.isLoadingResponse = false;
    toggleLoadingIndicator(false);
    
    // Прокручиваем чат вниз
    scrollChatToBottom(dom.comparisonMessages1);
    scrollChatToBottom(dom.comparisonMessages2);
  }
}

/**
 * Создает сообщение с индикатором загрузки для режима сравнения
 * @param {number} column - Номер колонки (1 или 2)
 * @returns {HTMLElement} - DOM-элемент сообщения
 */
function createLoadingMessageForComparison(column) {
  const messagesContainer = column === 1 ? dom.comparisonMessages1 : dom.comparisonMessages2;
  
  const messageEl = document.createElement('div');
  messageEl.className = 'ai-message';
  messageEl.innerHTML = `
    <div class="message-header">
      <div class="message-avatar">AI ${column}</div>
      <div class="message-timestamp">${formatTime(new Date())}</div>
    </div>
    <div class="message-content">
      <div class="loading-indicator">
        <span class="loader-dot"></span>
        <span class="loader-dot"></span>
        <span class="loader-dot"></span>
      </div>
    </div>
  `;
  
  messagesContainer.appendChild(messageEl);
  return messageEl;
}

/**
 * Отображает сообщение пользователя в обеих колонках сравнения
 * @param {string} prompt - Текст промта 
 */
function displayUserMessageInComparison(prompt) {
  // Создаем сообщение пользователя
  const userMessageHTML = `
    <div class="user-message">
      <div class="message-header">
        <div class="message-avatar">Я</div>
        <div class="message-timestamp">${formatTime(new Date())}</div>
      </div>
      <div class="message-content">
        ${formatMessageContent(prompt)}
      </div>
    </div>
  `;
  
  // Добавляем сообщение в обе колонки
  dom.comparisonMessages1.insertAdjacentHTML('beforeend', userMessageHTML);
  dom.comparisonMessages2.insertAdjacentHTML('beforeend', userMessageHTML);
}

/**
 * Сбрасывает звезды рейтинга
 */
function resetRatingStars() {
  document.querySelectorAll('.rating-stars .star').forEach(star => {
    star.classList.remove('active', 'hover');
  });
  
  // Сбрасываем отображаемые значения
  if (dom.ratingValue1) dom.ratingValue1.textContent = '0/10';
  if (dom.ratingValue2) dom.ratingValue2.textContent = '0/10';
}

/**
 * Обновляет состояние кнопок выбора победителя
 * @param {string} winner - 'model_1', 'model_2', 'tie' или null
 */
function updateWinnerButtons(winner) {
  dom.winnerModel1Btn.classList.toggle('selected', winner === 'model_1');
  dom.winnerModel2Btn.classList.toggle('selected', winner === 'model_2');
  dom.winnerTieBtn.classList.toggle('selected', winner === 'tie');
}

// --- Функции редактора и визуализатора ---

/**
 * Инициализирует Monaco Editor
 */
function initMonacoEditor() {
  // Используем require.config от Monaco
  require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.34.0/min/vs' } });
  
  // Определяем конфигурацию для web workers
  window.MonacoEnvironment = {
    getWorkerUrl: function(workerId, label) {
      return `data:text/javascript;charset=utf-8,${encodeURIComponent(`
        self.MonacoEnvironment = {
          baseUrl: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.34.0/min/'
        };
        importScripts('https://cdn.jsdelivr.net/npm/monaco-editor@0.34.0/min/vs/base/worker/workerMain.js');
      `)}`;
    }
  };
  
  console.log('Monaco Editor готов к инициализации');
}

/**
 * Создает экземпляр Monaco Editor, если он еще не создан
 */
async function ensureEditorExists() {
  if (state.editorInstance) {
    return Promise.resolve(state.editorInstance);
  }
  
  return new Promise((resolve) => {
    require(['vs/editor/editor.main'], () => {
      // Настраиваем тему редактора
      monaco.editor.defineTheme('promptArena', {
        base: 'vs',
        inherit: true,
        rules: [
          { token: 'comment', foreground: '6A9955', fontStyle: 'italic' },
          { token: 'keyword', foreground: '0000FF' },
          { token: 'string', foreground: 'A31515' }
        ],
        colors: {
          'editor.foreground': '#000000',
          'editor.background': '#FFFFFF',
          'editor.lineHighlightBackground': '#F7F7F7',
          'editorCursor.foreground': '#000000',
          'editor.selectionBackground': '#ADD6FF',
          'editor.inactiveSelectionBackground': '#E5EBF1'
        }
      });
      
      state.editorInstance = monaco.editor.create(dom.codeEditor, {
        value: state.editorContent || '',
        language: dom.editorLanguage.value,
        theme: 'promptArena',
        automaticLayout: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 14,
        lineNumbers: 'on',
        renderLineHighlight: 'all',
        roundedSelection: true,
        selectOnLineNumbers: true,
        tabSize: 2
      });
      
      // Сохраняем содержимое при изменении
      state.editorInstance.onDidChangeModelContent(() => {
        state.editorContent = state.editorInstance.getValue();
      });
      
      resolve(state.editorInstance);
    });
  });
}

/**
 * Переключает на режим редактора
 */
function showEditor() {
  // Обновляем классы кнопок
  dom.toggleVisualizerBtn.classList.remove('active');
  dom.toggleEditorBtn.classList.add('active');
  
  // Показываем редактор, скрываем визуализатор
  dom.codeEditor.classList.remove('hidden');
  dom.codeVisualizer.classList.add('hidden');
  
  // Убеждаемся, что редактор создан
  ensureEditorExists().then(() => {
    state.editorInstance.layout();
  });
}

/**
 * Переключает на режим визуализатора
 */
function showVisualizer() {
  // Обновляем классы кнопок
  dom.toggleEditorBtn.classList.remove('active');
  dom.toggleVisualizerBtn.classList.add('active');
  
  // Показываем визуализатор, скрываем редактор
  dom.codeVisualizer.classList.remove('hidden');
  dom.codeEditor.classList.add('hidden');
  
  // Если есть содержимое редактора, обновляем визуализатор
  if (state.editorContent) {
    // Если это HTML, обновляем визуализатор
    if (dom.editorLanguage.value === 'html') {
      updateCodeVisualizer(state.editorContent);
    }
  }
}

/**
 * Извлекает блоки кода из Markdown
 * @param {string} markdown - Markdown-текст
 * @returns {Array} - Массив объектов с кодом и языком
 */
function extractCodeBlocks(markdown) {
  const codeBlockRegex = /```([a-zA-Z]*)\n([\s\S]*?)```/g;
  const blocks = [];
  
  let match;
  while ((match = codeBlockRegex.exec(markdown)) !== null) {
    const language = match[1] || 'text';
    const code = match[2];
    
    blocks.push({ language, code });
  }
  
  return blocks;
}

/**
 * Извлекает первый блок кода из ответа и устанавливает его в редактор/визуализатор
 * @param {string} response - текст ответа от модели
 */
function extractAndSetupFirstCodeBlock(response) {
  const blocks = extractCodeBlocks(response);
  
  if (blocks.length > 0) {
    const firstBlock = blocks[0];
    
    // Нормализуем имя языка для редактора
    let editorLanguage = firstBlock.language.toLowerCase();
    
    // Преобразуем некоторые сокращения в полные имена языков
    const languageMap = {
      'js': 'javascript',
      'py': 'python',
      'ts': 'typescript',
      'rb': 'ruby',
      'md': 'markdown'
    };
    
    if (languageMap[editorLanguage]) {
      editorLanguage = languageMap[editorLanguage];
    }
    
    // Проверяем, есть ли такой язык в списке
    const options = Array.from(dom.editorLanguage.options).map(opt => opt.value);
    if (options.includes(editorLanguage)) {
      dom.editorLanguage.value = editorLanguage;
    } else {
      // Если язык неизвестен, используем text
      dom.editorLanguage.value = 'text';
    }
    
    // Устанавливаем код в редактор
    state.editorContent = firstBlock.code;
    
    ensureEditorExists().then(editor => {
      editor.setValue(firstBlock.code);
      
      if (language) {
        monaco.editor.setModelLanguage(editor.getModel(), dom.editorLanguage.value);
      }
      
      // Если язык HTML, показываем в визуализаторе
      if (dom.editorLanguage.value === 'html') {
        updateCodeVisualizer(firstBlock.code);
        // Показываем визуализатор по умолчанию
        showVisualizer();
      } else {
        // Для других языков показываем редактор
        showEditor();
      }
    });
  }
}

/**
 * Обновляет визуализатор кода HTML
 * @param {string} htmlContent - HTML код для визуализации
 */
function updateCodeVisualizer(htmlContent) {
  // Очищаем содержимое визуализатора
  dom.codeVisualizer.innerHTML = '';
  
  try {
    // Создаем iframe для безопасной визуализации HTML
    const iframe = document.createElement('iframe');
    iframe.style.width = '100%';
    iframe.style.height = '100%';
    iframe.style.border = 'none';
    iframe.style.backgroundColor = 'white';
    
    dom.codeVisualizer.appendChild(iframe);
    
    // Используем DOMPurify для санитизации HTML
    const cleanHtml = DOMPurify.sanitize(htmlContent);
    
    // Получаем document внутри iframe
    const iframeDoc = iframe.contentWindow.document;
    
    // Записываем HTML
    iframeDoc.open();
    iframeDoc.write(`
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Визуализация HTML</title>
          <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
          </style>
        </head>
        <body>${cleanHtml}</body>
      </html>
    `);
    iframeDoc.close();
  } catch (error) {
    console.error('Ошибка при визуализации HTML:', error);
    dom.codeVisualizer.innerHTML = `
      <div class="p-4 text-red-500">
        <h3 class="font-semibold">Ошибка визуализации</h3>
        <p>${escapeHtml(error.message)}</p>
      </div>
    `;
  }
}

/**
 * Запускает текущий код
 */
function runCurrentCode() {
  // Получаем текущий язык
  const language = dom.editorLanguage.value;
  
  // Получаем код из редактора
  const code = state.editorContent || (state.editorInstance ? state.editorInstance.getValue() : '');
  
  // Если код пустой, показываем сообщение
  if (!code.trim()) {
    showNotification('Нет кода для запуска', 'warning');
    return;
  }
  
  // Обрабатываем в зависимости от языка
  if (language === 'html') {
    updateCodeVisualizer(code);
    showVisualizer();
  } else if (language === 'javascript') {
    try {
      // Создаем iframe для изолированного выполнения JavaScript
      const iframe = document.createElement('iframe');
      iframe.style.display = 'none';
      document.body.appendChild(iframe);
      
      // Добавляем console.log, который будет выводить в визуализатор
      let consoleOutput = '';
      iframe.contentWindow.console = {
        log: (...args) => {
          consoleOutput += args.map(arg => {
            if (typeof arg === 'object') {
              return JSON.stringify(arg, null, 2);
            }
            return String(arg);
          }).join(' ') + '\n';
        },
        error: (...args) => {
          consoleOutput += `<span class="text-red-500">Error: ${args.map(String).join(' ')}</span>\n`;
        },
        warn: (...args) => {
          consoleOutput += `<span class="text-yellow-500">Warning: ${args.map(String).join(' ')}</span>\n`;
        }
      };
      
      // Выполняем код
      iframe.contentWindow.eval(code);
      
      // Отображаем результат в визуализаторе
      dom.codeVisualizer.innerHTML = `
        <div class="p-4 font-mono whitespace-pre-wrap text-sm bg-gray-900 text-white rounded-md overflow-auto">
          ${consoleOutput || '<span class="text-gray-400">// Нет вывода в консоль</span>'}
        </div>
      `;
      
      // Показываем визуализатор
      showVisualizer();
      
      // Удаляем iframe
      document.body.removeChild(iframe);
    } catch (error) {
      // Отображаем ошибку
      dom.codeVisualizer.innerHTML = `
        <div class="p-4 font-mono whitespace-pre-wrap text-sm bg-gray-900 text-white rounded-md overflow-auto">
          <span class="text-red-500">Error: ${escapeHtml(error.message)}</span>
        </div>
      `;
      showVisualizer();
    }
  } else {
    showNotification(`Выполнение кода на языке ${language} не поддерживается`, 'info');
  }
}

/**
 * Переключает видимость панели вывода
 */
function toggleOutputPanel() {
  if (state.outputPanelVisible) {
    // Закрываем панель
    dom.outputArea.style.height = '0';
    setTimeout(() => {
      dom.outputArea.style.display = 'none';
    }, 300); // Время анимации
    
    // Меняем иконку кнопки
    dom.toggleOutputPanelBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
      </svg>
    `;
  } else {
    // Открываем панель
    dom.outputArea.style.display = 'flex';
    setTimeout(() => {
      dom.outputArea.style.height = '40%';
      
      // Если редактор уже создан, перерисовываем его
      if (state.editorInstance) {
        state.editorInstance.layout();
      }
    }, 10); // Небольшая задержка для применения стилей
    
    // Меняем иконку кнопки
    dom.toggleOutputPanelBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clip-rule="evenodd" />
      </svg>
    `;
  }
  
  state.outputPanelVisible = !state.outputPanelVisible;
}

/**
 * Открывает панель вывода и опционально устанавливает код
 * @param {string} code - код для редактора (опционально)
 * @param {string} language - язык кода (опционально)
 */
function openOutputPanel(code, language) {
  // Показываем панель, если она скрыта
  if (!state.outputPanelVisible) {
    dom.outputArea.style.display = 'flex';
    dom.outputArea.style.height = '40%';
    state.outputPanelVisible = true;
    
    // Меняем иконку кнопки
    dom.toggleOutputPanelBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clip-rule="evenodd" />
      </svg>
    `;
  }
  
  // Если передан код, устанавливаем его в редактор
  if (code) {
    state.editorContent = code;
    
    // Если передан язык, устанавливаем его
    if (language) {
      // Преобразуем некоторые сокращения в полные имена языков
      const languageMap = {
        'js': 'javascript',
        'py': 'python',
        'ts': 'typescript',
        'rb': 'ruby',
        'md': 'markdown'
      };
      
      const normalizedLanguage = languageMap[language] || language;
      
      // Проверяем, есть ли такой язык в списке
      const options = Array.from(dom.editorLanguage.options).map(opt => opt.value);
      if (options.includes(normalizedLanguage)) {
        dom.editorLanguage.value = normalizedLanguage;
      }
    }
    
    // Инициализируем редактор и устанавливаем код
    ensureEditorExists().then(editor => {
      editor.setValue(code);
      
      if (language) {
        monaco.editor.setModelLanguage(editor.getModel(), dom.editorLanguage.value);
      }
      
      // Если язык HTML, показываем в визуализаторе
      if (dom.editorLanguage.value === 'html') {
        updateCodeVisualizer(code);
        // Показываем визуализатор по умолчанию
        showVisualizer();
      } else {
        // Для других языков показываем редактор
        showEditor();
      }
    });
  }
}

// --- Модальные окна ---

/**
 * Показывает модальное окно
 * @param {HTMLElement} modal - элемент модального окна
 */
function showModal(modal) {
  if (!modal) return;
  
  // Показываем бэкдроп
  modal.classList.remove('hidden');
  
  // Добавляем класс visible для анимации
  setTimeout(() => {
    modal.classList.add('visible');
    
    // Находим и фокусируем первый инпут, если есть
    const firstInput = modal.querySelector('input');
    if (firstInput) {
      firstInput.focus();
    }
  }, 10);
}

/**
 * Скрывает модальное окно
 * @param {HTMLElement} modal - элемент модального окна
 */
function hideModal(modal) {
  if (!modal) return;
  
  // Удаляем класс visible для анимации
  modal.classList.remove('visible');
  
  // Скрываем бэкдроп после анимации
  setTimeout(() => {
    modal.classList.add('hidden');
  }, 300); // Время анимации
}

// --- Уведомления ---

/**
 * Показывает уведомление
 * @param {string} message - текст уведомления
 * @param {string} type - тип уведомления (success, error, warning, info)
 * @param {number} duration - длительность отображения в мс
 */
function showNotification(message, type = 'info', duration = 5000) {
  // Санитизация сообщения от XSS
  const sanitizedMessage = escapeHtml(message);
  
  // Клонируем шаблон уведомления
  const notificationEl = dom.templates.notification.content.cloneNode(true).querySelector('.notification');
  
  // Добавляем класс в зависимости от типа
  notificationEl.classList.add(`notification-${type}`);
  
  // Устанавливаем текст уведомления (безопасно)
  notificationEl.querySelector('.notification-message').textContent = sanitizedMessage;
  
  // Генерируем уникальный ID для уведомления
  const id = randomId();
  notificationEl.dataset.id = id;
  
  // Добавляем кнопку закрытия
  const closeBtn = notificationEl.querySelector('.notification-close');
  closeBtn.addEventListener('click', () => {
    removeNotification(id);
  });
  
  // Добавляем уведомление в контейнер
  const container = document.getElementById('notifications-container') || createNotificationsContainer();
  container.appendChild(notificationEl);
  
  // Добавляем в массив активных уведомлений
  state.notifications.push({
    id,
    element: notificationEl,
    timer: setTimeout(() => {
      removeNotification(id);
    }, duration)
  });
  
  // Показываем уведомление с анимацией
  setTimeout(() => {
    notificationEl.classList.add('notification-visible');
  }, 10);
  
  return id;
}

// --- Вспомогательные функции ---

/**
 * Экранирует HTML специальные символы
 * @param {string} text - исходный текст
 * @returns {string} - экранированный текст
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Форматирует время в часы:минуты
 * @param {Date} date - объект даты
 * @returns {string} - отформатированное время
 */
function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/**
 * Функция debounce для отложенного вызова
 * @param {Function} func - функция для вызова
 * @param {number} wait - время ожидания в мс
 * @returns {Function} - обернутая функция
 */
function debounce(func, wait) {
  let timeout;
  return function(...args) {
    const context = this;
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(context, args), wait);
  };
}

/**
 * Случайный идентификатор
 * @returns {string} - случайный ID
 */
function randomId() {
  return Math.random().toString(36).substring(2, 15);
}

// Функции для сохранения и загрузки настроек из localStorage
const storage = {
  save: (key, value) => {
    try {
      localStorage.setItem(`promptArena_${key}`, JSON.stringify(value));
    } catch (e) {
      console.error('Ошибка при сохранении в localStorage:', e);
    }
  },
  
  load: (key, defaultValue = null) => {
    try {
      const value = localStorage.getItem(`promptArena_${key}`);
      return value ? JSON.parse(value) : defaultValue;
    } catch (e) {
      console.error('Ошибка при загрузке из localStorage:', e);
      return defaultValue;
    }
  },
  
  remove: (key) => {
    try {
      localStorage.removeItem(`promptArena_${key}`);
    } catch (e) {
      console.error('Ошибка при удалении из localStorage:', e);
    }
  }
};

// Загрузка сохраненных настроек при запуске
function loadSavedSettings() {
  const savedMaxTokens = storage.load('maxTokens');
  if (savedMaxTokens) {
    dom.maxTokensInput.value = savedMaxTokens;
  }
  
  const savedTemperature = storage.load('temperature');
  if (savedTemperature) {
    dom.temperatureInput.value = savedTemperature;
    dom.temperatureValue.textContent = savedTemperature;
  }
}

// Сохранение настроек при изменении
dom.maxTokensInput.addEventListener('change', () => {
  storage.save('maxTokens', dom.maxTokensInput.value);
});

dom.temperatureInput.addEventListener('change', () => {
  storage.save('temperature', dom.temperatureInput.value);
});

// Автоматически загружаем настройки при инициализации
document.addEventListener('DOMContentLoaded', () => {
  loadSavedSettings();
});

// --- Функции для работы с шаблонами промтов ---

/**
 * Получает список шаблонов промтов
 * @param {string} tag - Опциональный тег для фильтрации
 * @returns {Promise<Array>} - Список шаблонов промтов
 */
async function fetchPromptTemplates(tag = '') {
  try {
    let url = `/prompt-templates`;
    if (tag) {
      url += `?tag=${encodeURIComponent(tag)}`;
    }
    
    const templates = await fetchApi(url);
    state.promptTemplates = templates;
    
    // Обновляем UI
    renderPromptTemplates(templates);
    updateTagFilter(templates);
    
    return templates;
  } catch (error) {
    // Расширенный вывод ошибки
    if (error && (error.status || error.message || error.data)) {
      console.error('Ошибка при получении шаблонов промтов:', {
        status: error.status,
        message: error.message,
        data: error.data
      });
    } else {
      console.error('Ошибка при получении шаблонов промтов:', error);
    }
    showNotification('Не удалось загрузить шаблоны промтов', 'error');
    return [];
  }
}

/**
 * Получает шаблон промта по ID
 * @param {number} templateId - ID шаблона
 * @returns {Promise<object>} - Данные шаблона
 */
async function fetchPromptTemplate(templateId) {
  try {
    return await fetchApi(`/prompt-templates/${templateId}`);
  } catch (error) {
    console.error(`Ошибка при получении шаблона промта #${templateId}:`, error);
    showNotification('Не удалось загрузить шаблон промта', 'error');
    return null;
  }
}

/**
 * Создает новый шаблон промта
 * @param {object} templateData - Данные шаблона
 * @returns {Promise<object>} - Созданный шаблон
 */
async function createPromptTemplate(templateData) {
  try {
    const newTemplate = await fetchApi(`/prompt-templates`, {
      method: 'POST',
      body: JSON.stringify(templateData)
    });
    
    // Обновляем список шаблонов
    await fetchPromptTemplates();
    
    showNotification('Шаблон промта успешно создан', 'success');
    return newTemplate;
  } catch (error) {
    console.error('Ошибка при создании шаблона промта:', error);
    showNotification('Не удалось создать шаблон промта', 'error');
    return null;
  }
}

/**
 * Обновляет существующий шаблон промта
 * @param {number} templateId - ID шаблона
 * @param {object} templateData - Данные шаблона
 * @returns {Promise<object>} - Обновленный шаблон
 */
async function updatePromptTemplate(templateId, templateData) {
  try {
    const updatedTemplate = await fetchApi(`/prompt-templates/${templateId}`, {
      method: 'PUT',
      body: JSON.stringify(templateData)
    });
    
    // Обновляем список шаблонов
    await fetchPromptTemplates();
    
    showNotification('Шаблон промта успешно обновлен', 'success');
    return updatedTemplate;
  } catch (error) {
    console.error(`Ошибка при обновлении шаблона промта #${templateId}:`, error);
    showNotification('Не удалось обновить шаблон промта', 'error');
    return null;
  }
}

/**
 * Удаляет шаблон промта
 * @param {number} templateId - ID шаблона
 * @returns {Promise<boolean>} - Успешность операции
 */
async function deletePromptTemplate(templateId) {
  try {
    await fetchApi(`/prompt-templates/${templateId}`, {
      method: 'DELETE'
    });
    
    // Обновляем список шаблонов
    await fetchPromptTemplates();
    
    showNotification('Шаблон промта успешно удален', 'success');
    return true;
  } catch (error) {
    console.error(`Ошибка при удалении шаблона промта #${templateId}:`, error);
    showNotification('Не удалось удалить шаблон промта', 'error');
    return false;
  }
}

/**
 * Отображает шаблоны промтов в UI
 * @param {Array} templates - Список шаблонов
 */
function renderPromptTemplates(templates) {
  // Очищаем контейнер
  dom.templatesList.innerHTML = '';
  
  if (templates.length === 0) {
    dom.templatesList.innerHTML = `
      <div class="empty-state">
        <p>Шаблонов промтов не найдено</p>
      </div>
    `;
    return;
  }
  
  // Создаем элементы шаблонов
  templates.forEach(template => {
    const templateEl = createTemplateElement(template);
    dom.templatesList.appendChild(templateEl);
  });
}

/**
 * Создает DOM-элемент для шаблона промта
 * @param {object} template - Данные шаблона
 * @returns {HTMLElement} - DOM-элемент
 */
function createTemplateElement(template) {
  const templateTemplate = document.getElementById('prompt-template-item-template');
  const templateEl = templateTemplate.content.cloneNode(true).querySelector('.template-item');
  
  // Заполняем данные
  templateEl.querySelector('.template-name').textContent = template.name;
  
  if (template.description) {
    templateEl.querySelector('.template-description').textContent = template.description;
  } else {
    templateEl.querySelector('.template-description').remove();
  }
  
  // Добавляем теги, если есть
  if (template.tags) {
    const tagsContainer = templateEl.querySelector('.template-tags');
    const tagsList = template.tags.split(',').map(tag => tag.trim()).filter(tag => tag);
    
    tagsList.forEach(tag => {
      const tagEl = document.createElement('span');
      tagEl.className = 'template-tag';
      tagEl.textContent = tag;
      tagsContainer.appendChild(tagEl);
    });
  }
  
  // Добавляем обработчики событий для кнопок
  const useBtn = templateEl.querySelector('.template-use-btn');
  const editBtn = templateEl.querySelector('.template-edit-btn');
  const deleteBtn = templateEl.querySelector('.template-delete-btn');
  
  useBtn.addEventListener('click', () => {
    useTemplate(template);
  });
  
  editBtn.addEventListener('click', () => {
    editTemplate(template.id);
  });
  
  deleteBtn.addEventListener('click', () => {
    if (confirm(`Вы уверены, что хотите удалить шаблон "${template.name}"?`)) {
      deletePromptTemplate(template.id);
    }
  });
  
  return templateEl;
}

/**
 * Обновляет выпадающий список тегов
 * @param {Array} templates - Список шаблонов
 */
function updateTagFilter(templates) {
  // Получаем уникальные теги из всех шаблонов
  const allTags = new Set();
  
  templates.forEach(template => {
    if (template.tags) {
      const tagsList = template.tags.split(',').map(tag => tag.trim()).filter(tag => tag);
      tagsList.forEach(tag => allTags.add(tag));
    }
  });
  
  // Очищаем текущие опции, кроме первой (Все теги)
  while (dom.templateTagFilter.options.length > 1) {
    dom.templateTagFilter.remove(1);
  }
  
  // Добавляем теги в выпадающий список
  allTags.forEach(tag => {
    const option = document.createElement('option');
    option.value = tag;
    option.textContent = tag;
    dom.templateTagFilter.appendChild(option);
  });
}

/**
 * Фильтрует шаблоны промтов по поисковому запросу и тегу
 */
function filterTemplates() {
  const searchQuery = dom.templateSearch.value.toLowerCase();
  const selectedTag = dom.templateTagFilter.value;
  
  let filteredTemplates = state.promptTemplates;
  
  // Фильтрация по поисковому запросу
  if (searchQuery) {
    filteredTemplates = filteredTemplates.filter(template => 
      template.name.toLowerCase().includes(searchQuery) || 
      (template.description && template.description.toLowerCase().includes(searchQuery))
    );
  }
  
  // Фильтрация по тегу
  if (selectedTag) {
    filteredTemplates = filteredTemplates.filter(template => {
      if (!template.tags) return false;
      const tagsList = template.tags.split(',').map(tag => tag.trim());
      return tagsList.includes(selectedTag);
    });
  }
  
  // Обновляем отображение
  renderPromptTemplates(filteredTemplates);
}

/**
 * Открывает модальное окно для создания/редактирования шаблона
 * @param {boolean} isEdit - Режим редактирования
 */
function openTemplateModal(isEdit = false) {
  // Сбрасываем поля формы, если создаем новый шаблон
  if (!isEdit) {
    dom.templateForm.reset();
    state.currentTemplateId = null;
    dom.templateModalTitle.textContent = 'Создать новый шаблон';
    dom.templateSaveBtn.textContent = 'Создать';
  } else {
    dom.templateModalTitle.textContent = 'Редактировать шаблон';
    dom.templateSaveBtn.textContent = 'Сохранить';
  }
  
  // Показываем модальное окно
  dom.templateModal.classList.remove('hidden');
}

/**
 * Закрывает модальное окно шаблона
 */
function closeTemplateModal() {
  dom.templateModal.classList.add('hidden');
}

/**
 * Сохраняет шаблон (создает новый или обновляет существующий)
 */
async function saveTemplate() {
  // Получаем данные из формы
  const templateData = {
    name: dom.templateName.value,
    prompt_text: dom.templatePromptText.value,
    description: dom.templateDescription.value || null,
    tags: dom.templateTags.value || null,
    is_public: dom.templateIsPublic.checked
  };
  
  // Создаем новый или обновляем существующий шаблон
  if (state.currentTemplateId) {
    await updatePromptTemplate(state.currentTemplateId, templateData);
  } else {
    await createPromptTemplate(templateData);
  }
  
  // Закрываем модальное окно
  closeTemplateModal();
}

/**
 * Использует шаблон промта в текущем сообщении
 * @param {object} template - Данные шаблона
 */
function useTemplate(template) {
  // Вставляем текст шаблона в поле ввода сообщения
  dom.promptInput.value = template.prompt_text;
  
  // Если панель шаблонов открыта, закрываем ее
  state.templatesVisible = false;
  dom.templatesPanel.classList.add('hidden');
  
  // Фокусируемся на поле ввода
  dom.promptInput.focus();
}

/**
 * Переключает видимость панели параметров модели
 * @param {string} modelName - 'model1' или 'model2'
 */
function toggleModelParams(modelName) {
  const panel = modelName === 'model1' ? dom.model1ParamsPanel : dom.model2ParamsPanel;
  
  if (panel.classList.contains('hidden')) {
    panel.classList.remove('hidden');
  } else {
    panel.classList.add('hidden');
  }
}

/**
 * Обновляет интерфейс сравнения с полученными ответами
 * @param {object} result - Результат сравнения 
 * @param {HTMLElement} msg1El - Элемент сообщения для первой модели
 * @param {HTMLElement} msg2El - Элемент сообщения для второй модели
 */
function updateComparisonUIWithResponse(result, msg1El, msg2El) {
  // Обновляем содержимое сообщений
  const response1 = result.response_1;
  const response2 = result.response_2;
  
  // Обрабатываем ответ первой модели
  if (response1) {
    const formattedResponse = formatMessageContent(response1.response);
    const contentEl = msg1El.querySelector('.message-content');
    contentEl.innerHTML = formattedResponse;
    
    // Добавляем информацию о времени генерации, если доступна
    if (response1.elapsed_time) {
      const infoEl = document.createElement('div');
      infoEl.className = 'message-info';
      infoEl.textContent = `Время генерации: ${response1.elapsed_time.toFixed(2)} сек.`;
      contentEl.appendChild(infoEl);
    }
    
    // Если есть ошибка, отображаем ее
    if (response1.error) {
      const errorEl = document.createElement('div');
      errorEl.className = 'message-error';
      errorEl.textContent = response1.error;
      contentEl.innerHTML = '';
      contentEl.appendChild(errorEl);
    }
  }
  
  // Обрабатываем ответ второй модели
  if (response2) {
    const formattedResponse = formatMessageContent(response2.response);
    const contentEl = msg2El.querySelector('.message-content');
    contentEl.innerHTML = formattedResponse;
    
    // Добавляем информацию о времени генерации, если доступна
    if (response2.elapsed_time) {
      const infoEl = document.createElement('div');
      infoEl.className = 'message-info';
      infoEl.textContent = `Время генерации: ${response2.elapsed_time.toFixed(2)} сек.`;
      contentEl.appendChild(infoEl);
    }
    
    // Если есть ошибка, отображаем ее
    if (response2.error) {
      const errorEl = document.createElement('div');
      errorEl.className = 'message-error';
      errorEl.textContent = response2.error;
      contentEl.innerHTML = '';
      contentEl.appendChild(errorEl);
    }
  }
  
  // Обновляем элементы для выбора победителя, если оба ответа успешны
  if (!response1.error && !response2.error) {
    enableComparisonVoting();
  }
}

/**
 * Обновляет интерфейс с ошибкой при сравнении
 * @param {Error} error - Объект ошибки
 * @param {HTMLElement} msg1El - Элемент сообщения для первой модели
 * @param {HTMLElement} msg2El - Элемент сообщения для второй модели
 */
function updateComparisonUIWithError(error, msg1El, msg2El) {
  const errorMessage = error.message || 'Произошла ошибка при сравнении моделей';
  
  // Обновляем оба сообщения с ошибкой
  [msg1El, msg2El].forEach(msgEl => {
    const contentEl = msgEl.querySelector('.message-content');
    const errorEl = document.createElement('div');
    errorEl.className = 'message-error';
    errorEl.textContent = errorMessage;
    contentEl.innerHTML = '';
    contentEl.appendChild(errorEl);
  });
  
  // Отключаем возможность голосования
  disableComparisonVoting();
}

/**
 * Активирует элементы интерфейса для выбора победителя в сравнении
 */
function enableComparisonVoting() {
  // Если в UI есть элементы для голосования, активируем их
  if (dom.winnerModel1Btn && dom.winnerModel2Btn && dom.winnerTieBtn) {
    dom.winnerModel1Btn.removeAttribute('disabled');
    dom.winnerModel2Btn.removeAttribute('disabled');
    dom.winnerTieBtn.removeAttribute('disabled');
    
    // Обновляем надписи на кнопках
    dom.winnerModel1Btn.textContent = `${state.selectedModel1.name} лучше`;
    dom.winnerModel2Btn.textContent = `${state.selectedModel2.name} лучше`;
  }
}

/**
 * Деактивирует элементы интерфейса для выбора победителя в сравнении
 */
function disableComparisonVoting() {
  // Если в UI есть элементы для голосования, деактивируем их
  if (dom.winnerModel1Btn && dom.winnerModel2Btn && dom.winnerTieBtn) {
    dom.winnerModel1Btn.setAttribute('disabled', 'disabled');
    dom.winnerModel2Btn.setAttribute('disabled', 'disabled');
    dom.winnerTieBtn.setAttribute('disabled', 'disabled');
  }
}