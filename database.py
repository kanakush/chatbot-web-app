import aiosqlite
from datetime import datetime

DB_PATH = "data.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Создание основной таблицы заявок
        await db.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT,
                surname TEXT,
                phone TEXT,
                status TEXT,
                date TEXT,
                time TEXT,
                user_id INTEGER
            )
        ''')

        # 2. Создание ИНДЕКСОВ для ускорения поиска
        # Индекс на site_id (частый фильтр)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_site_id ON requests(site_id)")

        # Индекс на фамилию (поиск юзеров)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_surname ON requests(surname)")

        # Составной индекс для фильтрации по датам и статусу одновременно
        await db.execute("CREATE INDEX IF NOT EXISTS idx_date_status ON requests(date, status)")

        # 3. Таблица пользователей для Web
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT
            )
        ''')

        # Дефолтные пользователи
        try:
            await db.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                             ("admin", "admin", "admin"))
            await db.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("user", "user", "user"))
        except aiosqlite.IntegrityError:
            pass  # Пользователи уже существуют

        await db.commit()


async def add_request(site_id, surname, phone, status, user_id):
    now = datetime.now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO requests (site_id, surname, phone, status, date, time, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (site_id, surname, phone, status, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), user_id)
        )
        await db.commit()