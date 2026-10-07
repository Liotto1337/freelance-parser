"""Настройки парсера: категории площадок, навыки и ключевые слова.

Категории подобраны по результатам анализа сайтов (октябрь 2026).
Каждой категории приписан навык (skill). Если категория узкая (например,
FL.ru «python»), заказ сразу считается подходящим. Если широкая
(skill=None), заказ сохраняется, а навыки определяются по ключевым словам.
"""
import os

# Навыки: ключ -> (название в дашборде, регулярные выражения для поиска в тексте)
SKILLS = {
    "sites": ("Сайты / fullstack", [
        r"сайт", r"лендинг", r"landing", r"full[- ]?stack", r"фулл?стек",
        r"\breact\b", r"\bvue\b", r"next\.?js", r"node\.?js", r"laravel",
        r"django", r"веб[- ]?прилож", r"web[- ]?app", r"wordpress",
    ]),
    "python": ("Python", [
        r"python", r"питон", r"django", r"fastapi", r"flask", r"aiogram",
        r"pandas", r"selenium", r"playwright",
    ]),
    "golang": ("Go", [r"golang", r"\bgo\b"]),
    "csharp": ("C# / .NET", [
        r"c#", r"c sharp", r"\.net\b", r"asp\.net", r"\bwpf\b", r"winforms",
        r"blazor",
    ]),
    "gamedev": ("Разработка игр", [
        r"unity", r"unreal", r"godot", r"roblox", r"gamedev", r"геймдев",
        r"\bигр[аыуеой]", r"игров",
    ]),
    "presentations": ("Презентации", [
        r"презентац", r"powerpoint", r"\bpptx?\b", r"google slides",
        r"keynote",
    ]),
    "bots": ("Боты и скрипты", [
        r"\bбот", r"telegram", r"телеграм", r"парс", r"скрипт",
        r"автоматизац", r"mini ?app",
    ]),
    "layout": ("Вёрстка", [r"вёрстк", r"верстк", r"\bhtml\b", r"\bcss\b"]),
    "ts_api": ("TypeScript / API", [
        r"typescript", r"\bts\b", r"\bapi\b", r"интеграц",
    ]),
    "infographics": ("Инфографика", [r"инфограф"]),
}

# --- Kwork: https://kwork.ru/projects?c=<id>
KWORK_CATEGORIES = [
    # (id, название, навык или None для широкой категории)
    (37, "Создание сайта", "sites"),
    (38, "Доработка и настройка сайта", "sites"),
    (79, "Вёрстка", "layout"),
    (41, "Скрипты, боты и mini apps", None),
    (80, "Десктоп программирование", None),
    (40, "Игры", "gamedev"),
    (270, "Презентации и инфографика", None),
]

# --- FL.ru: https://www.fl.ru/projects/category/<slug>/
FL_CATEGORIES = [
    ("programmirovanie/fullstack", "Fullstack", "sites"),
    ("saity/web-programmist-razrabotka-sajtov", "Веб-программист", "sites"),
    ("saity/sajt-pod-kljuch", "Сайт под ключ", "sites"),
    ("saity/react", "React", "sites"),
    ("saity/vue", "Vue", "sites"),
    ("saity/nextjs", "Next.js", "sites"),
    ("saity/node", "Node", "sites"),
    ("saity/dorabotka-saytov", "Доработка сайтов", "sites"),
    ("saity/html-verstalschik", "HTML-верстальщик", "layout"),
    ("programmirovanie/python", "Python", "python"),
    ("programmirovanie/go-golang", "Go", "golang"),
    ("programmirovanie/c-sharp", "C#", "csharp"),
    ("programmirovanie/typescript", "TypeScript", "ts_api"),
    ("programmirovanie/integraciya-po-api", "Интеграция по API", "ts_api"),
    ("programmirovanie/razrabotka-chat-botov", "Чат-боты", "bots"),
    ("programmirovanie/sozdanie-skriptov", "Скрипты", "bots"),
    ("programmirovanie/parsing-dannyih", "Парсинг данных", "bots"),
    ("games/programmist-igr-programmirovanie", "Программист игр", "gamedev"),
    ("games/unity", "Unity", "gamedev"),
    ("games/unreal-engine", "Unreal Engine", "gamedev"),
    ("games/igry-dlya-android", "Игры для Android", "gamedev"),
    ("games/igry-dlya-ios", "Игры для iOS", "gamedev"),
    ("dizajn/dizajner-prezentacij", "Презентации", "presentations"),
    ("dizajn/infografika", "Инфографика", "infographics"),
]

# --- freelance.ru: https://freelance.ru/task?c[]=<id>
FREELANCERU_CATEGORIES = [
    (4, "Веб-разработка и IT", None),
    (40, "Дизайн и Брендинг", None),
]

# --- Сбор
POLL_INTERVAL_SEC = int(os.environ.get("POLL_INTERVAL_SEC", 600))  # раз в 10 минут
REQUEST_DELAY_SEC = float(os.environ.get("REQUEST_DELAY_SEC", 3))   # пауза между запросами
PAGES_PER_CATEGORY = int(os.environ.get("PAGES_PER_CATEGORY", 1))   # первый запуск: --pages 3
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)

# --- Хранилище и дашборд
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "orders.db"))
DASHBOARD_HOST = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", 8080))
# Если задан, дашборд спрашивает логин/пароль (HTTP Basic). На сервере обязательно.
DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "admin")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")

# Шаблон отклика, который дашборд копирует в буфер обмена
REPLY_TEMPLATE = os.environ.get(
    "REPLY_TEMPLATE", "Здравствуйте! Готов выполнить этот заказ."
)
