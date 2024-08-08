import os
import logging
import requests
import signal
from typing import Dict, Any
from datetime import datetime
from functools import lru_cache
from dotenv import load_dotenv
from threading import Lock
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

CHOOSING, TYPING_WAREHOUSE = range(2)

user_data_lock: Lock = Lock()
user_data: Dict[int, Dict[str, Any]] = {}
warehouses: Dict[str, str] = {}


class Bot:
    def __init__(self, token: str, api_key: str, admin_channel_id: str):
        self.updater = Updater(token, use_context=True)
        self.api_key = api_key
        self.admin_channel_id = admin_channel_id
        self.dp = self.updater.dispatcher

        # Сохраняем в bot_data для доступа из других функций
        self.dp.bot_data['API_KEY'] = api_key
        self.dp.bot_data['ADMIN_CHANNEL_ID'] = admin_channel_id

        # Регистрация обработчиков
        self.register_handlers()

    def register_handlers(self):
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                CHOOSING: [MessageHandler(Filters.regex('^Ввести название склада$'), self.choose_action)],
                TYPING_WAREHOUSE: [MessageHandler(Filters.text & ~Filters.command, self.receive_warehouse)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )

        self.dp.add_handler(conv_handler)
        self.dp.add_handler(CommandHandler('cancel', self.cancel))

    def start(self, update: Any, context: Any) -> int:
        user_id = update.effective_user.id
        if user_id in user_data:
            update.message.reply_text('У вас уже есть активный мониторинг. Используйте /cancel, чтобы остановить его и начать заново.')
            return ConversationHandler.END

        reply_keyboard = [['Ввести название склада']]
        update.message.reply_text(
            'Привет! Давайте начнем мониторинг. Выберите действие:',
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return CHOOSING

    def choose_action(self, update: Any, context: Any) -> int:
        update.message.reply_text('Введите название склада для мониторинга (например, Тула или Коледино):')
        return TYPING_WAREHOUSE

    def receive_warehouse(self, update: Any, context: Any) -> int:
        user_id = update.effective_user.id
        warehouse_name = update.message.text.strip().lower()

        matching_warehouses = [w for w in warehouses.items() if warehouse_name in w[1].lower()]

        if not matching_warehouses:
            update.message.reply_text('Склад с таким названием не найден. Попробуйте еще раз.')
            return TYPING_WAREHOUSE
        elif len(matching_warehouses) > 1:
            keyboard = [[f"{name} (ID: {id})" for id, name in matching_warehouses]]
            update.message.reply_text(
                'Найдено несколько складов. Выберите нужный:',
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            )
            return TYPING_WAREHOUSE
        else:
            warehouse_id, warehouse_name = matching_warehouses[0]
            self.start_monitoring(update, context, user_id, warehouse_id, warehouse_name)
            return ConversationHandler.END

    def start_monitoring(self, update: Any, context: Any, user_id: int, warehouse_id: str, warehouse_name: str) -> None:
        with user_data_lock:
            user_data[user_id] = {
                'warehouse_id': warehouse_id,
                'warehouse_name': warehouse_name,
                'last_coefficient': None,
                'last_date': None
            }
        message = f'Мониторинг начат для склада {warehouse_name} (ID: {warehouse_id}). Вы будете получать уведомления о изменениях.'
        update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
        context.job_queue.run_repeating(self.check_coefficient, interval=15, first=0, context=user_id)

    def check_coefficient(self, context: Any) -> None:
        user_id = context.job.context
        with user_data_lock:
            if user_id not in user_data:
                return
            warehouse_id = user_data[user_id]['warehouse_id']
            warehouse_name = user_data[user_id]['warehouse_name']

        url = 'https://supplies-api.wildberries.ru/api/v1/acceptance/coefficients'
        api_key = context.bot_data['API_KEY']
        headers = {
            'Authorization': f'Bearer {api_key}'
        }
        params = {
            'warehouseIDs': warehouse_id
        }

        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data:
                coefficient = data[0]['coefficient']
                date = datetime.fromisoformat(data[0]['date'].replace('Z', '+00:00')).strftime('%d.%m.%Y')

                last_coefficient = user_data[user_id]['last_coefficient']
                last_date = user_data[user_id]['last_date']
                if (coefficient != last_coefficient or date != last_date):
                    user_data[user_id]['last_coefficient'] = coefficient
                    user_data[user_id]['last_date'] = date

                    message = f'Обновление:\nСклад: {warehouse_name}\nID: {warehouse_id}\nДата: {date}\nКоэффициент: {coefficient}'
                    context.bot.send_message(chat_id=user_id, text=message)
            else:
                error_message = f'Данные для склада {warehouse_name} не найдены.'
                context.bot.send_message(chat_id=user_id, text=error_message)
                self.send_error_to_admin(error_message, context)
        except requests.HTTPError as http_err:
            error_message = f'Ошибка HTTP: {http_err}'
            if response.status_code == 401:
                error_message = 'Ошибка авторизации. Проверьте API ключ.'
            elif response.status_code == 404:
                error_message = f'Склад {warehouse_name} не найден.'
            context.bot.send_message(chat_id=user_id, text=error_message)
            self.send_error_to_admin(error_message, context)
        except requests.RequestException as req_err:
            error_message = f'Ошибка запроса: {req_err}'
            context.bot.send_message(chat_id=user_id, text=error_message)
            self.send_error_to_admin(error_message, context)
        except Exception as e:
            error_message = f'Неизвестная ошибка: {str(e)}'
            context.bot.send_message(chat_id=user_id, text=error_message)
            self.send_error_to_admin(error_message, context)

    @lru_cache(maxsize=128)
    def get_warehouses(self, api_key: str) -> Dict[str, str]:
        url = 'https://supplies-api.wildberries.ru/api/v1/warehouses'
        headers = {'Authorization': f'Bearer {api_key}'}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            return {warehouse['ID']: warehouse['name'] for warehouse in data}
        except requests.RequestException as e:
            logger.warning(f'Ошибка при загрузке списка складов: {str(e)}')
            return {}

    def load_warehouses(self, api_key: str) -> Dict[str, str]:
        return self.get_warehouses(api_key)

    def cancel(self, update: Any, context: Any) -> int:
        user_id = update.effective_user.id
        if user_id in user_data:
            del user_data[user_id]
            for job in context.job_queue.get_jobs_by_name(str(user_id)):
                job.schedule_removal()
            update.message.reply_text('Мониторинг остановлен и данные удалены.')
        else:
            update.message.reply_text('У вас нет активного мониторинга.')
        return ConversationHandler.END

    def signal_handler(self, signum, frame) -> None:
        logger.info("Получен сигнал завершения. Завершение работы бота...")
        self.updater.stop()
        exit(0)

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.updater.start_polling()
        self.updater.idle()


def main() -> None:
    load_dotenv()

    TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
    WB_API_SUPPLY = os.getenv('WB_API_SUPPLY')
    ADMIN_CHANNEL_ID = os.getenv('ADMIN_CHANNEL_ID')

    if not TG_TOKEN or not WB_API_SUPPLY or not ADMIN_CHANNEL_ID:
        print("Ошибка: TG_TOKEN или API_KEY или ADMIN_CHANNEL_ID не найдены в файле .env")
        return

    bot = Bot(TG_TOKEN, WB_API_SUPPLY, ADMIN_CHANNEL_ID)
    bot.run()


if __name__ == '__main__':
    main()
