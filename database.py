import aiosqlite
from datetime import datetime
from passlib.context import CryptContext

# Настройка контекста шифрования
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DB_PATH = "data.db"

# Вспомогательная функция для создания хеша
def get_password_hash(password: str) -> str:
    # Кодируем в байты, обрезаем и только потом хешируем
    password_bytes = password.encode('utf-8')
    return pwd_context.hash(password_bytes[:72])

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # То же самое при проверке
    password_bytes = plain_password.encode('utf-8')
    return pwd_context.verify(password_bytes[:72], hashed_password)

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

        # 2. Создание ИНДЕКСОВ
        await db.execute("CREATE INDEX IF NOT EXISTS idx_site_id ON requests(site_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_surname ON requests(surname)")
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

        # Дефолтные пользователи с ХЕШИРОВАННЫМИ паролями
        # ВАЖНО: Мы заменяем "admin" на результат работы get_password_hash
        admin_hash = get_password_hash("scuitadmin")
        user_hash = get_password_hash("scuituser")

        try:
            await db.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ("admin", admin_hash, "admin")
            )
            await db.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ("user", user_hash, "user")
            )


        except aiosqlite.IntegrityError:
            # Если пользователи уже есть, но вы хотите обновить им пароли на хешированные,
            # можно выполнить UPDATE, либо вручную удалить файл data.db для полной пересоздания
            pass

        await db.commit()

async def add_request(site_id, surname, phone, status, user_id):
    now = datetime.now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO requests (site_id, surname, phone, status, date, time, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (site_id, surname, phone, status, now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), user_id)
        )
        await db.commit()
