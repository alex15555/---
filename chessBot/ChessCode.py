import telebot
from telebot import types
import datetime as dt
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ChessToken import TOKEN  # Импортируем токен для Telegram бота

bot = telebot.TeleBot(TOKEN)

# Настройки для Google API
SCOPES = ['https://www.googleapis.com/auth/calendar']


# Функция для создания службы API
def create_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


# Создание службы для работы с Google Calendar
service = create_service()


# Получение ID календаря "Шахматы"
def get_chess_calendar_id():
    try:
        calendars_result = service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])
        for calendar in calendars:
            if calendar['summary'] == 'Шахматы':
                return calendar['id']
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


calendar_id = get_chess_calendar_id()

# Проверка, что календарь "Шахматы" был найден
if not calendar_id:
    print("Календарь 'Шахматы' не найден!")
    exit()

user_data = {}


# Создание меню для выбора игрового дня (только вторник)
def days_menu():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton('вторник'))
    markup.add(types.KeyboardButton('Назад'))
    return markup


# Функция для получения ближайшей даты для выбранного дня недели
def get_next_weekday(weekday):
    today = dt.date.today()
    days_ahead = weekday - today.weekday()
    if days_ahead < 0:  # Для получения даты только на текущей неделе, даже если день уже прошел
        days_ahead += 7
    return today + dt.timedelta(days=days_ahead)


# Меню подтверждения заявки
def accept_menu():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton('Принять'))
    markup.add(types.KeyboardButton('Назад'))
    return markup


# Меню для начала регистрации
def start_menu():
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton('Хочу участвовать в Лиге шахмат ВШБ'))
    markup.add(types.KeyboardButton('Отмена брони'))
    return markup


# Проверка, зарегистрирован ли пользователь уже на текущей неделе
def is_registered_this_week(chat_id):
    today = dt.date.today()
    week_start = today - dt.timedelta(days=today.weekday())  # Начало текущей недели (понедельник)
    week_end = week_start + dt.timedelta(days=6)  # Конец текущей недели (воскресенье)

    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=week_start.isoformat() + 'T00:00:00Z',
            timeMax=week_end.isoformat() + 'T23:59:59Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        for event in events:
            if 'description' in event and str(chat_id) in event['description']:
                return True
        return False
    except HttpError as error:
        print(f"An error occurred: {error}")
        return False


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id,
                     "Привет ✌️\nПриветствую в чат-боте Лиги шахмат ВШБ! Прошу заметить, что бронирование необходимо для участия в мини-турнире. Заполните заявку на участие!\n\n"
                     "Просьба регистрироваться только 1 раз",
                     reply_markup=start_menu())


# Обработчик для выбора участия
@bot.message_handler(func=lambda message: message.text == 'Хочу участвовать в Лиге шахмат ВШБ')
def handle_start(message):
    if is_registered_this_week(message.chat.id):
        bot.send_message(message.chat.id,
                         "Вы уже зарегистрированы!\nЕсли хотите зарегистрироваться на другое время, отмените предыдущую бронь и выберите удобное для вас время.",
                         reply_markup=start_menu())
    else:
        bot.send_message(message.chat.id, "Ознакомился", reply_markup=start_menu())
        ask_fio(message)


# Функция для запроса ФИО
def ask_fio(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton('Назад'))
    bot.send_message(message.chat.id, "Введите ФИО:", reply_markup=markup)
    user_data[message.chat.id] = {'state': 'FIO'}


# Обработчик для ввода ФИО
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'FIO')
def get_fio(message):
    if message.text == 'Назад':
        start_message(message)
    else:
        user_data[message.chat.id]['fio'] = message.text
        ask_op(message)


# Функция для запроса ОП
def ask_op(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton('Назад'))
    bot.send_message(message.chat.id, "Введите ОП:", reply_markup=markup)
    user_data[message.chat.id]['state'] = 'OP'


# Обработчик для ввода ОП
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'OP')
def get_op(message):
    if message.text == 'Назад':
        del user_data[message.chat.id]['fio']  # Удаляем предыдущий ответ
        ask_fio(message)
    else:
        user_data[message.chat.id]['op'] = message.text
        ask_course(message)


# Функция для запроса курса обучения
def ask_course(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton('Назад'))
    bot.send_message(message.chat.id, "Введите курс обучения:", reply_markup=markup)
    user_data[message.chat.id]['state'] = 'COURSE'


# Обработчик для ввода курса обучения
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'COURSE')
def get_course(message):
    if message.text == 'Назад':
        del user_data[message.chat.id]['op']  # Удаляем предыдущий ответ
        ask_op(message)
    else:
        user_data[message.chat.id]['course'] = message.text
        ask_nickname(message)


# Функция для запроса ника в ТГ
def ask_nickname(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton('Назад'))
    bot.send_message(message.chat.id, "Введите ник в ТГ для связи:", reply_markup=markup)
    user_data[message.chat.id]['state'] = 'NICKNAME'


# Обработчик для ввода ника в ТГ
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'NICKNAME')
def get_nickname(message):
    if message.text == 'Назад':
        del user_data[message.chat.id]['course']  # Удаляем предыдущий ответ
        ask_course(message)
    else:
        user_data[message.chat.id]['nickname'] = message.text
        ask_day(message)


# Функция для выбора дня недели (только вторник)
def ask_day(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton('вторник'))
    markup.add(types.KeyboardButton('Назад'))
    bot.send_message(message.chat.id, "Выберите день недели (только вторник):", reply_markup=markup)
    user_data[message.chat.id]['state'] = 'DAY'


# Обработчик для выбора дня недели (только вторник)
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'DAY')
def get_day(message):
    if message.text == 'Назад':
        del user_data[message.chat.id]['nickname']  # Удаляем предыдущий ответ
        ask_nickname(message)
    else:
        selected_date = get_next_weekday(1)  # Вторник = 1
        user_data[message.chat.id]['date'] = selected_date
        ask_accept(message)


# Функция для подтверждения заявки
def ask_accept(message):
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add(types.KeyboardButton('Принять'))
    markup.add(types.KeyboardButton('Назад'))
    bot.send_message(message.chat.id,
                     f"Оставляя заявку на участие, вы подтверждаете свою явку на {user_data[message.chat.id]['date'].strftime('%A, %d %B %Y')}, а также обещаете бережно относиться к имуществу Спортивного клуба ВШБ.",
                     reply_markup=markup)
    user_data[message.chat.id]['state'] = 'ACCEPT'


# Обработчик для подтверждения заявки
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'ACCEPT')
def accept_booking(message):
    if message.text == 'Назад':
        del user_data[message.chat.id]['date']  # Удаляем предыдущий ответ
        ask_day(message)
    elif message.text == 'Принять':
        user_data[message.chat.id]['state'] = 'COMPLETE'
        booking_info = user_data[message.chat.id]

        # Отправка данных в Google Calendar
        event = {
            'summary': 'Регистрация: Лига шахмат ВШБ',
            'description': (
                f"ФИО: {booking_info['fio']}\n"
                f"ОП: {booking_info['op']}\n"
                f"Курс: {booking_info['course']}\n"
                f"Ник в ТГ: {booking_info['nickname']}\n"
                f"Дата: {booking_info['date'].strftime('%A, %d %B %Y')}\n"
                f"Telegram ID: {message.chat.id}"  # Добавляем ID пользователя для проверки регистрации
            ),
            'start': {
                'dateTime': f"{booking_info['date']}T12:00:00",
                'timeZone': 'Europe/Moscow',
            },
            'end': {
                'dateTime': f"{booking_info['date']}T14:00:00",
                'timeZone': 'Europe/Moscow',
            },
        }

        try:
            event = service.events().insert(calendarId=calendar_id, body=event).execute()
            # Сохраняем ID созданного события для последующей отмены
            user_data[message.chat.id]['booking_id'] = event.get('id')
            bot.send_message(message.chat.id,
                             "Отлично, твоя заявка зарегистрирована! По подробностям можешь написать Менеджеру Отдела по работе со студентами ВШБ Покидову Егору Сергеевичу @egorchpok",
                             reply_markup=start_menu())
        except HttpError as error:
            bot.send_message(message.chat.id, f"Произошла ошибка при регистрации заявки: {error}")


# Функция для удаления события из календаря
def delete_event(event_id):
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        print("Event deleted successfully.")
    except HttpError as error:
        print(f"An error occurred: {error}")


# Обработчик для отмены брони
@bot.message_handler(func=lambda message: message.text == 'Отмена брони')
def cancel_booking(message):
    chat_id = message.chat.id
    if 'booking_id' in user_data.get(chat_id, {}):
        delete_event(user_data[chat_id]['booking_id'])
        del user_data[chat_id]['booking_id']
        bot.send_message(chat_id, "Ваша заявка отменена.", reply_markup=start_menu())
    else:
        bot.send_message(chat_id, "У вас нет активных заявок.", reply_markup=start_menu())


# Запуск бота
bot.polling(none_stop=True)
