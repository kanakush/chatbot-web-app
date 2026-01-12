import asyncio
import io
import csv
import re
import pandas as pd
from datetime import datetime

import uvicorn
import aiosqlite
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from database import init_db, add_request, DB_PATH

import os
from dotenv import load_dotenv

# --- КОНФИГУРАЦИЯ ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-if-env-fails")

# --- ИНИЦИАЛИЗАЦИЯ ---
app = FastAPI()
# Секретный ключ для сессий (авторизация)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
templates = Jinja2Templates(directory="templates")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# --- ЛОГИКА ТЕЛЕГРАМ-БОТА ---
class Registration(StatesGroup):
    site_id = State()
    surname = State()
    phone = State()
    status = State()


# Срабатывает на любое сообщение, если пользователь не в процессе опроса
@dp.message(StateFilter(None))
async def cmd_start_any(message: types.Message, state: FSMContext):
    await message.answer("👋 Я Door_Openbot\nВведите SITEID ровно 5 цифр:")
    await state.set_state(Registration.site_id)


@dp.message(Registration.site_id)
async def process_site_id(message: types.Message, state: FSMContext):
    if not re.fullmatch(r'\d{5}', message.text):
        return await message.answer("❌ Ошибка! Нужно ровно 5 цифр:")
    await state.update_data(site_id=message.text)
    await message.answer("Введите вашу фамилию:")
    await state.set_state(Registration.surname)


@dp.message(Registration.surname)
async def process_surname(message: types.Message, state: FSMContext):
    await state.update_data(surname=message.text)
    await message.answer("Введите номер телефона c 8 или +7")
    await state.set_state(Registration.phone)


@dp.message(Registration.phone)
async def process_phone(message: types.Message, state: FSMContext):
    # Валидация: 8 или +7 и еще 10 цифр
    if not re.fullmatch(r'(\+7|8)\d{10}', message.text):
        return await message.answer("❌ Неверный формат телефона\n Пример: +77001234567 или 87001234567")
    await state.update_data(phone=message.text)

    kb = ReplyKeyboardBuilder()
    kb.button(text="open")
    kb.button(text="close")
    await message.answer("✅Нажмите кнопку:\nopen - дверь открыта\nclose - дверь закрыта", reply_markup=kb.as_markup(resize_keyboard=True))
    await state.set_state(Registration.status)


@dp.message(Registration.status, F.text.in_(["open", "close"]))
async def process_status(message: types.Message, state: FSMContext):
    data = await state.get_data()
    # Сохраняем в БД
    await add_request(data['site_id'], data['surname'], data['phone'], message.text, message.from_user.id)

    await message.answer(f"✅Заявка сохранена!\nSITEID: {data['site_id']}\nФамилия: {data['surname']}\nТелефон: {data['phone']}\nСтатус: {message.text}",
                         reply_markup=types.ReplyKeyboardRemove())
    await state.clear()


# --- WEB ПРИЛОЖЕНИЕ (FastAPI) ---

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
        user = await cursor.fetchone()
        if user:
            request.session["user"] = username
            request.session["role"] = user[0]
            return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Неверные данные"})


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, site_id: str = None, status: str = None, date_from: str = None,
                    date_to: str = None):
    if "user" not in request.session: return RedirectResponse(url="/", status_code=303)

    role = request.session["role"]
    username = request.session["user"]

    async with aiosqlite.connect(DB_PATH) as db:
        query = "SELECT id, site_id, surname, phone, status, date, time, user_id FROM requests WHERE 1=1"
        params = []

        # Обычный пользователь видит только записи со своей фамилией
        if role == "user":
            query += " AND surname = ?"
            params.append(username)

        # Фильтры
        if site_id:
            query += " AND site_id = ?";
            params.append(site_id)
        if status:
            query += " AND status = ?";
            params.append(status)
        if date_from:
            query += " AND date >= ?";
            params.append(date_from)
        if date_to:
            query += " AND date <= ?";
            params.append(date_to)

        query += " ORDER BY id DESC"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "rows": rows, "role": role,
        "filters": {"site_id": site_id, "status": status, "date_from": date_from, "date_to": date_to}
    })


@app.post("/edit/{entry_id}")
async def edit_entry(entry_id: int, request: Request, site_id: str = Form(...), surname: str = Form(...),
                     phone: str = Form(...), status: str = Form(...)):
    if request.session.get("role") != "admin": raise HTTPException(status_code=403)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE requests SET site_id=?, surname=?, phone=?, status=? WHERE id=?",
                         (site_id, surname, phone, status, entry_id))
        await db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/delete/{entry_id}")
async def delete_entry(entry_id: int, request: Request):
    if request.session.get("role") != "admin": raise HTTPException(status_code=403)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM requests WHERE id=?", (entry_id,))
        await db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/export")
async def export_csv(request: Request):
    if request.session.get("role") != "admin": return Response("Access Denied", status_code=403)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM requests")
        rows = await cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "SITEID", "SURNAME", "PHONE", "STATUS", "DATE", "TIME", "USER_ID"])
    writer.writerows(rows)

    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=export.csv"})


@app.get("/export-excel")
async def export_excel(request: Request):
    if request.session.get("role") != "admin": return Response("Access Denied", status_code=403)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT site_id, surname, phone, status, date, time FROM requests")
        rows = await cursor.fetchall()

    df = pd.DataFrame(rows, columns=["SITEID", "Фамилия", "Телефон", "Статус", "Дата", "Время"])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)

    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=requests.xlsx"})


# --- ЗАПУСК ---
async def main():
    # Создаем таблицы и индексы
    await init_db()

    # Конфигурация веб-сервера
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)

    # Запускаем бота и веб-сервер одновременно
    print("🚀 Система запущена! Web: http://localhost:8000")
    await asyncio.gather(
        dp.start_polling(bot),
        server.serve()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Система остановлена")