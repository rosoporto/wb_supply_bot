import os
import ast
from dotenv import load_dotenv
from wb_zero_supply.get_stock_wb_from_domen import check_stock_wb
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Job


load_dotenv()
AUTHORIZED_USERS = ast.literal_eval(os.getenv('AUTHORIZED_USERS'))


def is_authorized(update):
    user_id = update.effective_user.id
    return user_id in AUTHORIZED_USERS


def start(update, context):
    if is_authorized(update):
        update.message.reply_text('Привет! Я бот для проверки складов.')
    else:
        update.message.reply_text('Извините, у вас нет доступа к этой команде.')


def check_store_limit(update, context):
    if is_authorized(update):
        # Логика проверки складов
        update.message.reply_text('Проверка складов выполнена.')
    else:
        update.message.reply_text('Извините, у вас нет доступа к этой команде.')


def main():
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('check_store_limit', check_store_limit))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
