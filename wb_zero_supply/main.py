import os
import redis
from dotenv import load_dotenv
from functools import partial
from wb_zero_supply.get_stock_wb_from_api import get_stock_wb_from_api, check_zero_coefficients
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Job


# Подключение к Redis
r = redis.Redis(host='localhost', port=6379, db=0)


def check_store_limit(context):
    pass


def start(context):
    pass


def main():
    load_dotenv()
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    CHAT_ID = os.getenv('CHAT_ID')
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start))
    check_store_limit_with_chat_id = partial(check_store_limit, context=CHAT_ID)
    dp.add_handler(CommandHandler('check_store_limit', check_store_limit_with_chat_id))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
