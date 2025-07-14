import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

bot = telebot.TeleBot("8117016919:AAGwBSoaU0i2cctpaeEu_P14xnTJB_uvXjw")

whitelist = [810397112, 832295315, 5214851916]
user_states = {}
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

def check_access(user_id):
    return user_id in whitelist

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

def accessory_menu():
    keyboard = InlineKeyboardMarkup(row_width=1)
    cursor.execute("SELECT DISTINCT name FROM rentals WHERE type = 'accessory' AND name IS NOT NULL")
    accessories = [row[0] for row in cursor.fetchall()]
    for acc in accessories:
        keyboard.add(InlineKeyboardButton(f"📦 {acc}", callback_data=f"acc_{acc}"))
        keyboard.add(InlineKeyboardButton(f"🗑️ Удалить {acc}", callback_data=f"del_acc_{acc}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

def guard_menu():
    keyboard = InlineKeyboardMarkup(row_width=1)
    cursor.execute("SELECT DISTINCT name FROM rentals WHERE type = 'guard' AND name IS NOT NULL")
    guards = [row[0] for row in cursor.fetchall()]
    for guard in guards:
        keyboard.add(InlineKeyboardButton(f"🛡️ {guard}", callback_data=f"guard_{guard}"))
        keyboard.add(InlineKeyboardButton(f"🗑️ Удалить {guard}", callback_data=f"del_guard_{guard}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

def amount_menu(item_type, name):
    keyboard = InlineKeyboardMarkup(row_width=3)
    amounts = [1000, 5000, 10000, 20000, 50000]
    for amount in amounts:
        keyboard.add(InlineKeyboardButton(f"{amount}", callback_data=f"{item_type}_amount_{name}_{amount}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

def hours_menu(item_type, name, amount):
    keyboard = InlineKeyboardMarkup(row_width=3)
    hours = [1, 2, 3, 4, 5, 6, 8, 12, 24]
    for h in hours:
        keyboard.add(InlineKeyboardButton(f"{h} ч", callback_data=f"{item_type}_hours_{name}_{amount}_{h}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard

def calculate_earnings(user_id, period):
    cursor.execute("SELECT type, amount, hours FROM rentals WHERE user_id = ? AND amount > 0 AND hours > 0", (user_id,))
    rows = cursor.fetchall()
    total = 0
    for row in rows:
        amount, hours, item_type = row[1], row[2], row[0]
        commission = 0.08 if item_type == "accessory" else 0.12
        net_amount = amount * (1 - commission)
        if period == "day":
            total += net_amount * hours
        elif period == "week":
            total += net_amount * hours * 7
        elif period == "month":
            total += net_amount * hours * 30
        elif period == "all":
            total += net_amount * hours
    return total

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

@bot.message_handler(commands=['start'])
def start(message):
    if not check_access(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 Доступ запрещён")
        return
    bot.send_message(message.chat.id, "👋 <b>Добро пожаловать в калькулятор аренды!</b>", parse_mode="HTML", reply_markup=main_menu())

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
        bot.edit_message_text(format_earnings_message(user_id), chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=main_menu())
    elif call.data.startswith("acc_") and not call.data.startswith("del_acc_"):
        acc_name = call.data[4:]
        bot.edit_message_text(
            f"📦 <b>{acc_name}</b>\nВыберите сумму аренды за час:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=amount_menu("acc", acc_name)
        )
    elif call.data.startswith("guard_") and not call.data.startswith("del_guard_"):
        guard_name = call.data[6:]
        bot.edit_message_text(
            f"🛡️ <b>{guard_name}</b>\nВыберите сумму аренды за час:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=amount_menu("guard", guard_name)
        )
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
    elif data[0] in ["acc", "guard"] and data[1] == "amount":
        item_type, name, amount = data[0], data[2], int(data[3])
        bot.edit_message_text(
            f"{('📦' if item_type == 'acc' else '🛡️')} <b>{name}</b>\nСумма: {amount}\nВыберите количество часов:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=hours_menu(item_type, name, amount)
        )
    elif data[0] in ["acc", "guard"] and data[1] == "hours":
        item_type, name, amount, hours = data[0], data[2], int(data[3]), int(data[4])
        cursor.execute("INSERT INTO rentals (user_id, type, name, amount, hours, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                      (user_id, "accessory" if item_type == "acc" else "guard", name, amount, hours, datetime.now().isoformat()))
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
                          (user_id, "guard", message.text, five, 0, datetime.now().isoformat()))
            db.commit()
            bot.send_message(message.chat.id, f"✅ Охранник <b>{message.text}</b> добавлен", parse_mode="HTML", reply_markup=main_menu())
        user_states.pop(user_id, None)

bot.polling()
