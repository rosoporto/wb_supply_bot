import os
import logging
import requests
import signal
from typing import Dict, Any
from datetime import datetime
from functools import lru_cache
from dotenv import load_dotenv
from threading import Lock
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

CHOOSING, TYPING_WAREHOUSE, TYPING_BOX_TYPE, CHOOSING_COEFFICIENT = range(4)


class Bot:
    def __init__(self, token: str, api_key: str, admin_channel_id: str):
        self.updater = Updater(token, use_context=True)
        self.api_key = api_key
        self.admin_channel_id = admin_channel_id
        self.dp = self.updater.dispatcher
        self.user_data_lock: Lock = Lock()
        self.user_data: Dict[int, Dict[str, Any]] = {}
        self.warehouses: Dict[str, str] = self.load_warehouses(api_key)

        self.dp.bot_data['API_KEY'] = api_key
        self.dp.bot_data['ADMIN_CHANNEL_ID'] = admin_channel_id

        self.register_handlers()

    def register_handlers(self) -> None:
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                CHOOSING: [MessageHandler(Filters.regex('^Ввести название склада$'), self.choose_action)],
                TYPING_WAREHOUSE: [MessageHandler(Filters.text & ~Filters.command, self.receive_warehouse)],
                TYPING_BOX_TYPE: [MessageHandler(Filters.regex('^[0-9]{1,2}$'), self.select_delivery_type)],
                CHOOSING_COEFFICIENT: [MessageHandler(Filters.text & ~Filters.command, self.receive_coefficient)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )

        self.dp.add_handler(conv_handler)
        self.dp.add_handler(CommandHandler('cancel', self.cancel))

    def start(self, update: Update, context: CallbackContext) -> int:
        user_id = update.effective_user.id
        with self.user_data_lock:
            if user_id in self.user_data:
                update.message.reply_text('У вас уже есть активный мониторинг. Используйте /cancel, чтобы остановить его и начать заново.')
                return ConversationHandler.END

        reply_keyboard = [['Ввести название склада']]
        update.message.reply_text(
            'Привет! Давайте начнем мониторинг. Выберите действие:',
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
        return CHOOSING

    def choose_action(self, update: Update, context: CallbackContext) -> int:
        update.message.reply_text('Введите название склада для мониторинга (например, Тула или Коледино):')
        return TYPING_WAREHOUSE

    def receive_warehouse(self, update: Update, context: CallbackContext) -> int:
        warehouse_name = update.message.text.strip().lower()
        matching_warehouses = [w for w in self.warehouses.items() if warehouse_name in w[1].lower()]

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
            context.user_data['warehouse_id'] = warehouse_id
            context.user_data['warehouse_name'] = warehouse_name

            reply_keyboard = [[str(i) for i in range(11)]]
            update.message.reply_text(
                'Выберите максимальный коэффициент для отслеживания (0-10):',
                reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
            )
            return TYPING_BOX_TYPE

    def select_delivery_type(self, update: Update, context: CallbackContext) -> int:
        context.user_data['max_coefficient'] = int(update.message.text)

        reply_keyboard = [['Короба', 'Монопаллеты', 'Суперсейф'], ['QR-поставка с коробами']]
        update.message.reply_text(
            'Выберите тип поставки:',
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
        )

        return CHOOSING_COEFFICIENT

    def receive_coefficient(self, update: Update, context: CallbackContext) -> int:
        user_id = update.effective_user.id
        box_type_name = update.message.text

        max_coefficient = context.user_data['max_coefficient']
        warehouse_id = context.user_data['warehouse_id']
        warehouse_name = context.user_data['warehouse_name']

        self.start_monitoring(update, context, user_id, warehouse_id, warehouse_name, max_coefficient, box_type_name)
        return ConversationHandler.END

    def start_monitoring(self, update: Update, context: CallbackContext, user_id: int, warehouse_id: str, warehouse_name: str, max_coefficient: int, box_type_name: str) -> None:
        with self.user_data_lock:
            self.user_data[user_id] = {
                'warehouse_id': warehouse_id,
                'warehouse_name': warehouse_name,
                'max_coefficient': max_coefficient,
                'box_type_name': box_type_name,
                'last_coefficients': {}
            }
        message = f'Мониторинг начат для склада {warehouse_name}. Вы будете получать уведомления о коэффициентах от 0 до {max_coefficient} с типом поставки {box_type_name}.'
        update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
        context.job_queue.run_repeating(self.check_coefficient, interval=15, first=0, context=user_id)

    def check_coefficient(self, context: CallbackContext) -> None:
        user_id = context.job.context
        with self.user_data_lock:
            if user_id not in self.user_data:
                return
            warehouse_id = self.user_data[user_id]['warehouse_id']
            warehouse_name = self.user_data[user_id]['warehouse_name']
            max_coefficient = self.user_data[user_id]['max_coefficient']
            box_type_name = self.user_data[user_id]['box_type_name']

        url = 'https://supplies-api.wildberries.ru/api/v1/acceptance/coefficients'
        api_key = context.bot_data['API_KEY']
        headers = {
            'Authorization': f'Bearer {api_key}'
        }
        params = {
            'warehouseIDs': warehouse_id,
            'boxTypeName': box_type_name
        }

        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data:
                # Фильтруем по типу поставки: короб, монопалет и т.п.
                box_types = [item for item in data if item['boxTypeName'] == box_type_name]

                if not box_types:  # Проверка на наличие данных
                    self.send_error_message(context, user_id, f'Нет данных для типа поставки: {box_type_name}.')
                    return

                # Фильтруем коэффициенты, исключая -1 и те, что больше max_coefficient
                coefficients = {
                    int(item['coefficient']): item['date']
                    for item in box_types
                    if int(item['coefficient']) != -1 and 0 <= int(item['coefficient']) <= max_coefficient
                }

                with self.user_data_lock:
                    last_coefficients = self.user_data[user_id]['last_coefficients']
                    for coef, date in coefficients.items():
                        if coef not in last_coefficients or date != last_coefficients[coef]:
                            formatted_date = datetime.fromisoformat(date.replace('Z', '+00:00')).strftime('%d.%m.%Y')
                            message = f'Обновление:\nСклад: {warehouse_name}\nДата: {formatted_date}\nКоэффициент: {coef}\nТип поставки: {box_type_name}'
                            context.bot.send_message(chat_id=user_id, text=message)

                    self.user_data[user_id]['last_coefficients'] = coefficients
            else:
                self.send_error_message(context, user_id, f'Данные для склада {warehouse_name} не найдены.')
        except requests.HTTPError as http_err:
            error_message = f'Ошибка HTTP: {http_err}'
            if response.status_code == 401:
                error_message = 'Ошибка авторизации. Проверьте API ключ.'
            elif response.status_code == 404:
                error_message = f'Склад {warehouse_name} не найден.'
            self.send_error_message(context, user_id, error_message)
        except requests.RequestException as req_err:
            self.send_error_message(context, user_id, f'Ошибка запроса: {req_err}')
        except Exception as e:
            self.send_error_message(context, user_id, f'Неизвестная ошибка: {str(e)}')

    def send_error_message(self, context: CallbackContext, user_id: int, error_message: str) -> None:
        """Отправка сообщения об ошибке пользователю и администратору."""
        context.bot.send_message(chat_id=user_id, text=error_message)
        self.send_error_to_admin(error_message, context)

    def send_error_to_admin(self, error_message: str, context: CallbackContext) -> None:
        """Отправка сообщения об ошибке администратору."""
        admin_channel_id = context.bot_data['ADMIN_CHANNEL_ID']
        context.bot.send_message(chat_id=admin_channel_id, text=f"Ошибка бота: {error_message}")

    @lru_cache(maxsize=1)
    def get_warehouses(self, api_key: str) -> Dict[str, str]:
        """Получение списка складов с кэшированием."""
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
        """Загрузка списка складов."""
        return self.get_warehouses(api_key)

    def cancel(self, update: Update, context: CallbackContext) -> int:
        """Обработчик команды /cancel."""
        user_id = update.effective_user.id
        with self.user_data_lock:
            if user_id in self.user_data:
                del self.user_data[user_id]
                for job in context.job_queue.get_jobs_by_name(str(user_id)):
                    job.schedule_removal()
                update.message.reply_text('Мониторинг остановлен и данные удалены.')
            else:
                update.message.reply_text('У вас нет активного мониторинга.')
        return ConversationHandler.END

    def signal_handler(self, signum, frame) -> None:
        """Обработчик сигналов завершения."""
        logger.info("Получен сигнал завершения. Завершение работы бота...")
        self.updater.stop()
        self.updater.is_idle = False

    def run(self) -> None:
        """Запуск бота."""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.updater.start_polling()
        logger.info("Бот запущен и готов к работе.")
        self.updater.idle()


def main() -> None:
    load_dotenv()

    TG_TOKEN = os.getenv('TELEGRAM_TOKEN')
    WB_API_SUPPLY = os.getenv('WB_API_SUPPLY')
    ADMIN_CHANNEL_ID = os.getenv('ADMIN_CHANNEL_ID')

    if not TG_TOKEN or not WB_API_SUPPLY or not ADMIN_CHANNEL_ID:
        logger.error("Ошибка: TG_TOKEN или API_KEY или ADMIN_CHANNEL_ID не найдены в файле .env")
        return

    bot = Bot(TG_TOKEN, WB_API_SUPPLY, ADMIN_CHANNEL_ID)
    bot.run()


if __name__ == '__main__':
    main()
