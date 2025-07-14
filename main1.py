import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import json
import os
import time

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "7529450433:AAE2mfcHYDNS1UUJH-90NFJH7Fdqzxg-UNk"
WHITELIST = [810397112, 832295315, 5214851916]  # Ваши ID пользователей
DB_FILE = 'rental_db.json'

class RentalManager:
    def __init__(self):
        self.commissions = {'accessory': 0.08, 'guard': 0.12}
        self.data = self._load_data()
    
    def _load_data(self):
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                return json.load(f)
        return {"accessories": [], "guards": [], "transactions": []}
    
    def _save_data(self):
        with open(DB_FILE, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def add_item(self, name, item_type):
        item_list = 'guards' if item_type == 'guard' else 'accessories'
        if name not in self.data[item_list]:
            self.data[item_list].append(name)
            self._save_data()
            return True
        return False
    
    def remove_item(self, name, item_type):
        item_list = 'guards' if item_type == 'guard' else 'accessories'
        if name in self.data[item_list]:
            self.data[item_list].remove(name)
            self._save_data()
            return True
        return False
    
    def add_transaction(self, item, amount, hours, item_type, user_id):
        commission = self.commissions[item_type]
        total = amount * hours
        fee = total * commission
        earnings = total - fee
        transaction = {
            'item': item,
            'amount': amount,
            'hours': hours,
            'total': total,
            'fee': fee,
            'earnings': earnings,
            'type': item_type,
            'timestamp': time.time(),
            'user_id': user_id
        }
        self.data['transactions'].append(transaction)
        self._save_data()
        return total, fee, earnings
    
    def get_stats(self, item_type=None, period=None, user_id=None):
        transactions = self.data['transactions']
        if item_type:
            transactions = [t for t in transactions if t['type'] == item_type]
        if user_id:
            transactions = [t for t in transactions if t['user_id'] == user_id]
        if period:
            cutoff = time.time() - {'24h': 86400, 'week': 604800, 'month': 2592000}[period]
            transactions = [t for t in transactions if t['timestamp'] >= cutoff]
        total = sum(t['total'] for t in transactions)
        fee = sum(t['fee'] for t in transactions)
        earnings = sum(t['earnings'] for t in transactions)
        return total, fee, earnings

class RentalBot:
    def __init__(self):
        self.manager = RentalManager()
        self.application = Application.builder().token(BOT_TOKEN).build()
        self._register_handlers()
    
    def _register_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in WHITELIST:
            await update.message.reply_text("🚫 Доступ запрещен")
            return

        buttons = [
            [KeyboardButton("Добавить аксессуар"), KeyboardButton("Добавить охранника")],
            [KeyboardButton("Мои аксессуары"), KeyboardButton("Мои охранники")],
            [KeyboardButton("Удалить аксессуар"), KeyboardButton("Удалить охранника")],
            [KeyboardButton("Статистика")]
        ]
        await update.message.reply_text(
            "👋 Выберите действие:",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in WHITELIST:
            return

        text = update.message.text
        
        # Обработка ввода стоимости аренды
        if 'rent_item' in context.user_data:
            try:
                amount = float(text)
                context.user_data['rent_amount'] = amount
                await update.message.reply_text(f"⏱ Введите количество часов для аренды {context.user_data['rent_item']}:")
                return
            except ValueError:
                await update.message.reply_text("❌ Пожалуйста, введите число!")
                return
        
        # Обработка ввода времени аренды
        if 'rent_amount' in context.user_data:
            try:
                hours = float(text)
                item = context.user_data['rent_item']
                item_type = context.user_data['rent_type']
                amount = context.user_data['rent_amount']
                
                total, fee, earnings = self.manager.add_transaction(
                    item, amount, hours, item_type, user_id)
                
                await update.message.reply_text(
                    f"✅ Аренда оформлена:\n\n"
                    f"🔹 Предмет: {item}\n"
                    f"💵 Ставка: ${amount}/час\n"
                    f"⏱ Часов: {hours}\n"
                    f"💰 Итого: ${total:.2f}\n"
                    f"📌 Комиссия: ${fee:.2f}\n"
                    f"💸 Ваш доход: ${earnings:.2f}")
                
                # Очищаем временные данные
                for key in ['rent_item', 'rent_type', 'rent_amount']:
                    context.user_data.pop(key, None)
                
                # Возвращаем в главное меню
                await self.start(update, context)
                return
                
            except ValueError:
                await update.message.reply_text("❌ Пожалуйста, введите число!")
                return
        
        # Остальная обработка команд
        if text == "Добавить аксессуар":
            context.user_data['action'] = {'type': 'add', 'item_type': 'accessory'}
            await update.message.reply_text("Введите название аксессуара:")
        elif text == "Добавить охранника":
            context.user_data['action'] = {'type': 'add', 'item_type': 'guard'}
            await update.message.reply_text("Введите имя охранника:")
        elif text == "Мои аксессуары":
            await self._show_items(update, 'accessory')
        elif text == "Мои охранники":
            await self._show_items(update, 'guard')
        elif text == "Удалить аксессуар":
            await self._show_items_to_remove(update, 'accessory')
        elif text == "Удалить охранника":
            await self._show_items_to_remove(update, 'guard')
        elif text == "Статистика":
            await self._show_stats_menu(update)
        elif 'action' in context.user_data:
            await self._handle_action(update, context, user_id)
    
    async def _handle_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        action = context.user_data['action']
        text = update.message.text

        if action['type'] == 'add':
            if self.manager.add_item(text, action['item_type']):
                await update.message.reply_text(f"✅ {'Охранник' if action['item_type'] == 'guard' else 'Аксессуар'} '{text}' добавлен!")
            else:
                await update.message.reply_text("⚠️ Уже существует!")
            context.user_data.pop('action')
        elif action['type'] == 'rent':
            try:
                if 'amount' not in action:
                    action['amount'] = float(text)
                    await update.message.reply_text(f"💵 Стоимость: ${action['amount']}/час. На сколько часов?")
                else:
                    hours = float(text)
                    total, fee, earnings = self.manager.add_transaction(
                        action['item'], action['amount'], hours, action['item_type'], user_id)
                    await update.message.reply_text(
                        f"📊 Аренда {action['item_type']} {action['item']}:\n"
                        f"⏱ Часов: {hours}\n"
                        f"💰 Итого: ${total:.2f}\n"
                        f"📌 Комиссия: ${fee:.2f}\n"
                        f"💸 Ваш доход: ${earnings:.2f}")
                    context.user_data.pop('action')
            except ValueError:
                await update.message.reply_text("❌ Введите число!")
    
    async def _show_items(self, update: Update, item_type: str):
        items = self.manager.data['guards'] if item_type == 'guard' else self.manager.data['accessories']
        if not items:
            await update.message.reply_text(f"❌ Нет {'охранников' if item_type == 'guard' else 'аксессуаров'}.")
            return
        
        # Создаем инлайн-кнопки для каждого предмета
        keyboard = []
        for item in items:
            keyboard.append([InlineKeyboardButton(
                text=f"Арендовать {item}",
                callback_data=f"rent_{item_type}_{item}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        item_type_name = "охранников" if item_type == 'guard' else "аксессуаров"
        await update.message.reply_text(
            f"Выберите {item_type_name} для аренды:",
            reply_markup=reply_markup
        )
    
    async def _show_items_to_remove(self, update: Update, item_type: str):
        items = self.manager.data['guards'] if item_type == 'guard' else self.manager.data['accessories']
        if not items:
            await update.message.reply_text(f"❌ Нет {'охранников' if item_type == 'guard' else 'аксессуаров'} для удаления.")
            return
        buttons = [[InlineKeyboardButton(item, callback_data=f"remove_{item_type}_{item}")] for item in items]
        await update.message.reply_text(
            f"🗑 Удалить {'охранника' if item_type == 'guard' else 'аксессуар'}:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def _show_stats_menu(self, update: Update):
        buttons = [
            [InlineKeyboardButton("Аксессуары", callback_data="stats_accessory"),
             InlineKeyboardButton("Охранники", callback_data="stats_guard")],
            [InlineKeyboardButton("Общая", callback_data="stats_all")]
        ]
        await update.message.reply_text(
            "📈 Статистика:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data.split('_')
        user_id = query.from_user.id

        if data[0] == 'remove':
            item_type, item = data[1], data[2]
            if self.manager.remove_item(item, item_type):
                await query.edit_message_text(f"✅ {'Охранник' if item_type == 'guard' else 'Аксессуар'} '{item}' удален!")
            else:
                await query.edit_message_text("❌ Ошибка удаления!")
        
        elif data[0] == 'rent':
            item_type, item = data[1], data[2]
            context.user_data['rent_item'] = item
            context.user_data['rent_type'] = item_type
            await query.edit_message_text(f"💵 Введите стоимость аренды в час для {item}:")
            return
        
        elif data[0] == 'stats':
            item_type = None if data[1] == 'all' else data[1]
            total, fee, earnings = self.manager.get_stats(item_type, user_id=user_id)
            await query.edit_message_text(
                f"📊 Статистика ({'всего' if not item_type else item_type}):\n"
                f"💵 Общий доход: ${total:.2f}\n"
                f"📌 Комиссия: ${fee:.2f}\n"
                f"💸 Ваш заработок: ${earnings:.2f}")
        
        await query.answer()
    
    def run(self):
        self.application.run_polling()

if __name__ == '__main__':
    bot = RentalBot()
    bot.run()
