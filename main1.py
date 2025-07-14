import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

# Инициализация бота
bot = telebot.TeleBot("6288603114:AAFvvlzV2oZoojhwMdEyTfRniFNGWdp7bU0")

# Белый список пользователей
whitelist = [810397112, 832295315, 5214851916]
user_states = {}

# Инициализация базы данных
db = sqlite3.connect('rentals.db', check_same_thread=False)
cursor = db.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS rentals
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 type TEXT,
                 name TEXT,
                 amount INTEGER,
                 hours INTEGER,
                 timestamp TEXT)''')
db.commit()

# Проверка доступа пользователя
def check_access(user_id):
    return user_id in whitelist

# Главное меню
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📦 Добавить аксессуар", callback_data="add_accessory"),
        InlineKeyboardButton("🛡️ Добавить охранника", callback_data="add_guard")
    )
    keyboard.add(
        InlineKeyboardButton("📋 Список аксессуаров", callback_data="list_accessories"),
        InlineKeyboardButton("👥 Список охранников", callback_data="list_guards")
    )
    keyboard.add(InlineKeyboardButton("💰 Доходы", callback_data="earnings"))
    return keyboard

# Меню аксессуаров
def accessory_menu():
    keyboard = InlineKeyboardMarkup(row_width=1)
    cursor.execute("SELECT DISTINCT name FROM rentals WHERE type = 'accessory' AND name IS NOT NULL")
    accessories = [row[0] for row in cursor.fetchall()]
    for acc in accessories:
        keyboard.add(InlineKeyboardButton(f"📦 {acc}", callback_data=f"acc_{acc}"))
        keyboard.add(InlineKeyboardButton(f"🗑️ Удалить {acc}", callback_data=f"del_acc_{acc}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

# Меню охранников
def guard_menu():
    keyboard = InlineKeyboardMarkup(row_width=1)
    cursor.execute("SELECT DISTINCT name FROM rentals WHERE type = 'guard' AND name IS NOT NULL")
    guards = [row[0] for row in cursor.fetchall()]
    for guard in guards:
        keyboard.add(InlineKeyboardButton(f"🛡️ {guard}", callback_data=f"guard_{guard}"))
        keyboard.add(InlineKeyboardButton(f"🗑️ Удалить {guard}", callback_data=f"del_guard_{guard}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

# Меню выбора часов
def hours_menu(item_type, name, amount):
    keyboard = InlineKeyboardMarkup(row_width=3)
    hours = [1, 2, 3, 4, 5, 6, 8, 12, 24]
    for h in hours:
        keyboard.add(InlineKeyboardButton(f"{h} ч", callback_data=f"{item_type}_hours_{name}_{amount}_{h}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

# Расчет доходов с учетом времени для всех пользователей
def calculate_earnings(user_id, period):
    cursor.execute("SELECT type, amount, hours, timestamp FROM rentals WHERE amount > 0 AND hours > 0")
    rows = cursor.fetchall()
    total = 0
    now = datetime.now()
    for row in rows:
        amount, hours, item_type, timestamp = row[1], row[2], row[0], datetime.fromisoformat(row[3])
        commission = 0.08 if item_type == "accessory" else 0.12
        net_amount = amount * (1 - commission) * hours
        if period == "day" and now - timestamp <= timedelta(hours=24):
            total += net_amount
        elif period == "week" and now - timestamp <= timedelta(days=7):
            total += net_amount
        elif period == "month" and now - timestamp <= timedelta(days=30):
            total += net_amount
        elif period == "all":
            total += net_amount
    return total

# Форматирование сообщения о доходах
def format_earnings_message(user_id):
    day = calculate_earnings(user_id, "day")
    week = calculate_earnings(user_id, "week")
    month = calculate_earnings(user_id, "month")
    all_time = calculate_earnings(user_id, "all")
    return (f"💸 <b>Доходы</b> 💸\n"
            f"🕒 За 24 часа: {day:.2f}\n"
            f"📅 За неделю: {week:.2f}\n"
            f"🗓️ За месяц: {month:.2f}\n"
            f"📈 За всё время: {all_time:.2f}")

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    if not check_access(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 Доступ запрещён")
        return
    bot.send_message(message.chat.id, "👋 <b>Добро пожаловать в калькулятор аренды!</b>", parse_mode="HTML", reply_markup=main_menu())

# Обработчик callback-запросов
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    if not check_access(user_id):
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "🚫 Доступ запрещён")
        return

    data = call.data.split("_")
    if call.data == "add_accessory":
        bot.edit_message_text("📦 Введите название аксессуара:", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        user_states[user_id] = "waiting_acc_name"
    elif call.data == "add_guard":
        bot.edit_message_text("🛡️ Введите имя охранника:", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML")
        user_states[user_id] = "waiting_guard_name"
    elif call.data == "list_accessories":
        bot.edit_message_text("📋 <b>Список аксессуаров</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=accessory_menu())
    elif call.data == "list_guards":
        bot.edit_message_text("👥 <b>Список охранников</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=guard_menu())
    elif call.data == "earnings":
        bot.edit_message_text(format_earnings_message(user_id), chat_id=call.message.chat.id, message_id=ительными рекомендациями call.message.message_id, parse_mode="HTML", reply_markup=main_menu())
    elif call.data.startswith("acc_") and not call.data.startswith("del_acc_") and not call.data.startswith("acc_hours_"):
        acc_name = call.data[4:]
        bot.edit_message_text(
            f"📦 <b>{acc_name}</b>\nВведите сумму аренды за час:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )
        user_states[user_id] = f"waiting_acc_amount_{acc_name}"
    elif call.data.startswith("guard_") and not call.data.startswith("del_guard_") and not call.data.startswith("guard_hours_"):
        guard_name = call.data[6:]
        bot.edit_message_text(
            f"🛡️ <b>{guard_name}</b>\nВведите сумму аренды за час:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )
        user_states[user_id] = f"waiting_guard_amount_{guard_name}"
    elif call.data.startswith("del_acc_"):
        acc_name = call.data[8:]
        cursor.execute("DELETE FROM rentals WHERE type = 'accessory' AND name = ?", (acc_name,))
        db.commit()
        bot.edit_message_text("📋 <b>Список аксессуаров</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=accessory_menu())
    elif call.data.startswith("del_guard_"):
        guard_name = call.data[10:]
        cursor.execute("DELETE FROM rentals WHERE type = 'guard' AND name = ?", (guard_name,))
        db.commit()
        bot.edit_message_text("👥 <b>Список охранников</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=guard_menu())
    elif call.data.startswith("acc_hours_") or call.data.startswith("guard_hours_"):
        item_type = "accessory" if call.data.startswith("acc_") else "guard"
        name, amount, hours = data[2], int(data[3]), int(data[4])
        cursor.execute(
            "INSERT INTO rentals (user_id, type, name, amount, hours, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, item_type, name, amount, hours, datetime.now().isoformat())
        )
        db.commit()
        bot.edit_message_text(
            f"✅ Добавлена аренда: <b>{name}</b> на {hours} часов за {amount}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=main_menu()
        )
    elif call.data == "back":
        bot.edit_message_text("👋 <b>Главное меню</b>", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=main_menu())
    bot.answer_callback_query(call.id)

# Обработчик текстовых сообщений
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    if not check_access(user_id):
        bot.send_message(message.chat.id, "🚫 Доступ запрещён")
        return

    state = user_states.get(user_id)
    if state == "waiting_acc_name":
        cursor.execute("SELECT name FROM rentals WHERE type = 'accessory' AND name = ?", (message.text,))
        if cursor.fetchone():
            bot.send_message(message.chat.id, "⚠️ Аксессуар с таким названием уже существует", parse_mode="HTML", reply_markup=main_menu())
        else:
            cursor.execute("INSERT INTO rentals (user_id, type, name, amount, hours, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                          (user_id, "accessory", message.text, 0, 0, datetime.now().isoformat()))
            db.commit()
            bot.send_message(message.chat.id, f"✅ Аксессуар <b>{message.text}</b> добавлен", parse_mode="HTML", reply_markup=main_menu())
        user_states.pop(user_id, None)
    elif state == "waiting_guard_name":
        cursor.execute("SELECT name FROM rentals WHERE type = 'guard' AND name = ?", (message.text,))
        if cursor.fetchone():
            bot.send_message(message.chat.id, "⚠️ Охранник с таким именем уже существует", parse_mode="HTML", reply_markup=main_menu())
        else:
            cursor.execute("INSERT INTO rentals (user_id, type, name, amount, hours, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                          (user_id, "guard", message.text, 0, 0, datetime.now().isoformat()))
            db.commit()
            bot.send_message(message.chat.id, f"✅ Охранник <b>{message.text}</b> добавлен", parse_mode="HTML", reply_markup=main_menu())
        user_states.pop(user_id, None)
    elif state and state.startswith("waiting_acc_amount_"):
        try:
            amount = int(message.text)
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
            acc_name = state[19:]
            bot.send_message(
                message.chat.id,
                f"📦 <b>{acc_name}</b>\nСумма: {amount}\nВыберите количество часов:",
                parse_mode="HTML",
                reply_markup=hours_menu("acc", acc_name, amount)
            )
            user_states.pop(user_id, None)
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ Пожалуйста, введите корректную сумму (положительное число)")
    elif state and state.startswith("waiting_guard_amount_"):
        try:
            amount = int(message.text)
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
            guard_name = state[21:]
            bot.send_message(
                message.chat.id,
                f"🛡️ <b>{guard_name}</b>\nСумма: {amount}\nВыберите количество часов:",
                parse_mode="HTML",
                reply_markup=hours_menu("guard", guard_name, amount)
            )
            user_states.pop(user_id, None)
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ Пожалуйста, введите корректную сумму (положительное число)")

# Запуск бота
bot.polling()
