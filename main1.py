import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import json
import os
import time

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

WHITELIST = [5214851916,832295315,810397112]  # Ваши ID пользователей
DB_FILE = 'shared_rental_db.json'

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
    def __init__(self, token):
        self.manager = RentalManager()
        self.updater = Updater(token)
        self.dispatcher = self.updater.dispatcher
        self._register_handlers()

    def _register_handlers(self):
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_message))
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_handler))

    def start(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if user_id not in WHITELIST:
            update.message.reply_text("🚫 Доступ запрещен")
            return

        buttons = [
            [KeyboardButton("Добавить аксессуар"), KeyboardButton("Добавить охранника")],
            [KeyboardButton("Мои аксессуары"), KeyboardButton("Мои охранники")],
            [KeyboardButton("Удалить аксессуар"), KeyboardButton("Удалить охранника")],
            [KeyboardButton("Статистика")]
        ]
        update.message.reply_text("👋 Выберите действие:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))

    def handle_message(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if user_id not in WHITELIST:
            return

        text = update.message.text
        if text == "Добавить аксессуар":
            context.user_data['action'] = {'type': 'add', 'item_type': 'accessory'}
            update.message.reply_text("Введите название аксессуара:")
        elif text == "Добавить охранника":
            context.user_data['action'] = {'type': 'add', 'item_type': 'guard'}
            update.message.reply_text("Введите имя охранника:")
        elif text == "Мои аксессуары":
            self._show_items(update, 'accessory')
        elif text == "Мои охранники":
            self._show_items(update, 'guard')
        elif text == "Удалить аксессуар":
            self._show_items_to_remove(update, 'accessory')
        elif text == "Удалить охранника":
            self._show_items_to_remove(update, 'guard')
        elif text == "Статистика":
            self._show_stats_menu(update)
        elif 'action' in context.user_data:
            self._handle_action(update, context, user_id)

    def _handle_action(self, update: Update, context: CallbackContext, user_id: int):
        action = context.user_data['action']
        text = update.message.text

        if action['type'] == 'add':
            if self.manager.add_item(text, action['item_type']):
                update.message.reply_text(f"✅ {'Охранник' if action['item_type'] == 'guard' else 'Аксессуар'} '{text}' добавлен!")
            else:
                update.message.reply_text("⚠️ Уже существует!")
            context.user_data.pop('action')
        elif action['type'] == 'rent':
            try:
                if 'amount' not in action:
                    action['amount'] = float(text)
                    update.message.reply_text(f"💵 Стоимость: ${action['amount']}/час. На сколько часов?")
                else:
                    hours = float(text)
                    total, fee, earnings = self.manager.add_transaction(
                        action['item'], action['amount'], hours, action['item_type'], user_id)
                    update.message.reply_text(
                        f"📊 Аренда {action['item_type']} {action['item']}:\n"
                        f"⏱ Часов: {hours}\n"
                        f"💰 Итого: ${total:.2f}\n"
                        f"📌 Комиссия: ${fee:.2f}\n"
                        f"💸 Ваш доход: ${earnings:.2f}")
                    context.user_data.pop('action')
            except ValueError:
                update.message.reply_text("❌ Введите число!")

    def _show_items(self, update: Update, item_type: str):
        items = self.manager.data['guards'] if item_type == 'guard' else self.manager.data['accessories']
        if not items:
            update.message.reply_text(f"❌ Нет {'охранников' if item_type == 'guard' else 'аксессуаров'}.")
            return
        update.message.reply_text("\n".join(items))

    def _show_items_to_remove(self, update: Update, item_type: str):
        items = self.manager.data['guards'] if item_type == 'guard' else self.manager.data['accessories']
        if not items:
            update.message.reply_text(f"❌ Нет {'охранников' if item_type == 'guard' else 'аксессуаров'} для удаления.")
            return
        buttons = [[InlineKeyboardButton(item, callback_data=f"remove_{item_type}_{item}")] for item in items]
        update.message.reply_text(f"🗑 Удалить {'охранника' if item_type == 'guard' else 'аксессуар'}:", 
                                reply_markup=InlineKeyboardMarkup(buttons))

    def _show_stats_menu(self, update: Update):
        buttons = [
            [InlineKeyboardButton("Аксессуары", callback_data="stats_accessory"),
             InlineKeyboardButton("Охранники", callback_data="stats_guard")],
            [InlineKeyboardButton("Общая", callback_data="stats_all")]
        ]
        update.message.reply_text("📈 Статистика:", reply_markup=InlineKeyboardMarkup(buttons))

    def button_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        data = query.data.split('_')
        user_id = query.from_user.id

        if data[0] == 'remove':
            item_type, item = data[1], data[2]
            if self.manager.remove_item(item, item_type):
                query.edit_message_text(f"✅ {'Охранник' if item_type == 'guard' else 'Аксессуар'} '{item}' удален!")
            else:
                query.edit_message_text("❌ Ошибка удаления!")
        elif data[0] == 'stats':
            item_type = None if data[1] == 'all' else data[1]
            total, fee, earnings = self.manager.get_stats(item_type, user_id=user_id)
            query.edit_message_text(
                f"📊 Статистика ({'всего' if not item_type else item_type}):\n"
                f"💵 Общий доход: ${total:.2f}\n"
                f"📌 Комиссия: ${fee:.2f}\n"
                f"💸 Ваш заработок: ${earnings:.2f}")
        query.answer()

    def run(self):
        self.updater.start_polling()
        self.updater.idle()

if __name__ == '__main__':
    bot = RentalBot("7529450433:AAE2mfcHYDNS1UUJH-90NFJH7Fdqzxg-UNk")
    bot.run()
