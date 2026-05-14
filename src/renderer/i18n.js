export const dict = {
  en: {
    home: 'Home', sessions: 'Sessions', new: '+ New', settings: 'Settings', contacts: 'Help & contacts', presets: 'Presets',
    search: 'Search', allGroups: 'All groups', connect: 'Connect', open: 'Open', duplicate: 'Duplicate', edit: 'Edit', delete: 'Delete',
    save: 'Save', saveConnect: 'Save and connect', cancel: 'Close', name: 'Name', host: 'Host / IP', port: 'Port', username: 'Username',
    password: 'Password', savePassword: 'Save password securely', authMode: 'Auth mode', privateKey: 'Private key', browse: 'Browse',
    group: 'Group', groupColor: 'Group color', addGroup: 'Add new group…', tags: 'Tags', notes: 'Notes', favorite: 'Favorite',
    startDir: 'Start directory', tunnels: 'SSH tunnels / port forwarding', protocol: 'Protocol', serialPort: 'Serial port', serialBaud: 'Baud rate',
    files: 'Files', splitRight: 'Split →', splitDown: 'Split ↓', splitGrid: 'Grid 2×2', reconnect: 'Reconnect', copy: 'Copy', paste: 'Paste', clear: 'Clear', disconnect: 'Disconnect',
    run: 'Run', selectPreset: 'Select preset', noPresets: 'No presets', commandPresets: 'Command presets', presetName: 'Preset name', commands: 'Commands',
    bulkHint: 'Multi-line presets and pasted text are sent as one block. This is useful for docker-compose, mkdir/cd chains and install scripts.',
    dashboard: 'Dashboard', quickConnect: 'Quick connect', recent: 'Recent sessions', quickActions: 'Quick actions', total: 'Sessions', groups: 'Groups', favorites: 'Favorites',
    language: 'Language', theme: 'Theme', customTheme: 'Custom theme', terminal: 'Terminal', fontSize: 'Font size', scrollback: 'Scrollback lines', reconnectSettings: 'Auto reconnect',
    restart: 'Restart application', restartHint: 'Restart applies language, titlebar and some terminal settings completely.', saved: 'Settings saved.', restarting: 'Restarting…', animations: 'Animations', reduceMotion: 'Reduce motion',
    sftp: 'SFTP file manager', path: 'Path', up: 'Up', refresh: 'Refresh', upload: 'Upload', download: 'Download', mkdir: 'New folder', size: 'Size', modified: 'Modified', type: 'Type',
    support: 'Support', website: 'Website', help: 'Help', copied: 'Copied', passwordRequired: 'Password required', enterPassword: 'Enter password',
    noSessions: 'No saved sessions yet.', welcome: 'Modern SSH client with xterm.js, tabs, split panes, SFTP, themes and command presets.',
    helpText: 'Create sessions on the left, open terminals in tabs, split the workspace into multiple panes, use Files for SFTP and Presets for bulk commands. xterm.js handles nano, vim, htop, tmux and other TUI apps.',
    taskDone: 'Done', taskError: 'Error', dragToReorder: 'Drag cards to reorder'
  },
  ru: {
    home: 'Главная', sessions: 'Подключения', new: '+ Новое', settings: 'Настройки', contacts: 'Справка и контакты', presets: 'Пресеты',
    search: 'Поиск', allGroups: 'Все группы', connect: 'Подключить', open: 'Открыть', duplicate: 'Дубликат', edit: 'Изменить', delete: 'Удалить',
    save: 'Сохранить', saveConnect: 'Сохранить и подключить', cancel: 'Закрыть', name: 'Название', host: 'Хост / IP', port: 'Порт', username: 'Пользователь',
    password: 'Пароль', savePassword: 'Сохранить пароль защищённо', authMode: 'Тип входа', privateKey: 'Приватный ключ', browse: 'Обзор',
    group: 'Группа', groupColor: 'Цвет группы', addGroup: 'Добавить новую группу…', tags: 'Теги', notes: 'Заметки', favorite: 'Избранное',
    startDir: 'Начальная папка', tunnels: 'SSH tunnels / port forwarding', protocol: 'Протокол', serialPort: 'Serial-порт', serialBaud: 'Baud rate',
    files: 'Файлы', splitRight: 'Разделить →', splitDown: 'Разделить ↓', splitGrid: 'Сетка 2×2', reconnect: 'Переподключить', copy: 'Копировать', paste: 'Вставить', clear: 'Очистить', disconnect: 'Отключить',
    run: 'Выполнить', selectPreset: 'Выберите пресет', noPresets: 'Нет пресетов', commandPresets: 'Пресеты команд', presetName: 'Название пресета', commands: 'Команды',
    bulkHint: 'Многострочные пресеты и вставленный текст отправляются одним блоком. Удобно для docker-compose, цепочек mkdir/cd и install-скриптов.',
    dashboard: 'Обзор', quickConnect: 'Быстрое подключение', recent: 'Последние подключения', quickActions: 'Быстрые действия', total: 'Подключений', groups: 'Групп', favorites: 'Избранных',
    language: 'Язык', theme: 'Тема', customTheme: 'Своя тема', terminal: 'Терминал', fontSize: 'Размер шрифта', scrollback: 'Строк scrollback', reconnectSettings: 'Автопереподключение',
    restart: 'Перезапустить приложение', restartHint: 'Перезапуск полностью применяет язык, верхнюю панель и часть настроек терминала.', saved: 'Настройки сохранены.', restarting: 'Перезапуск…', animations: 'Анимации', reduceMotion: 'Уменьшить анимации',
    sftp: 'SFTP-проводник', path: 'Путь', up: 'Вверх', refresh: 'Обновить', upload: 'Загрузить', download: 'Скачать', mkdir: 'Новая папка', size: 'Размер', modified: 'Изменено', type: 'Тип',
    support: 'Поддержка', website: 'Сайт', help: 'Справка', copied: 'Скопировано', passwordRequired: 'Нужен пароль', enterPassword: 'Введите пароль',
    noSessions: 'Пока нет сохранённых подключений.', welcome: 'Современный SSH-клиент на xterm.js с вкладками, split-панелями, SFTP, темами и пресетами команд.',
    helpText: 'Создавайте подключения слева, открывайте терминалы во вкладках, делите рабочую область на панели, используйте «Файлы» для SFTP и «Пресеты» для пакетного выполнения команд. xterm.js корректно обрабатывает nano, vim, htop, tmux и другие TUI-программы.',
    taskDone: 'Готово', taskError: 'Ошибка', dragToReorder: 'Перетащите карточки для изменения порядка'
  }
};
export function makeT(getLang) {
  return key => (dict[getLang()] && dict[getLang()][key]) || dict.en[key] || key;
}
