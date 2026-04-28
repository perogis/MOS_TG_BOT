import telebot
import psycopg2
import os

# --- НАСТРОЙКИ ---
BOT_TOKEN = '8275387371:AAFiXbiW1d4ZWgg1g3AMcgx_gj6IgdwZU1k'

DB_URL = "postgresql://mos_team_postgres_user:3qW96sv2XZpjv9cRO7eo9n1P2FlhOz8u@dpg-d7m8m8tckfvc73ebbh0g-a.oregon-postgres.render.com/mos_team_postgres"

bot = telebot.TeleBot(BOT_TOKEN)
b=0

# --- ПОДКЛЮЧЕНИЕ К БД ---
def get_connection():
    return psycopg2.connect(DB_URL)


# --- КНОПКИ ---
def buttons():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    btn1 = telebot.types.KeyboardButton("📦 Показать заказы")
    btn2 = telebot.types.KeyboardButton("📅 По дате")

    markup.add(btn1, btn2)
    return markup


# --- СОСТОЯНИЕ ---
user_state = {}
user_dates = {}


# --- ПОЛУЧИТЬ ВСЕ ЗАКАЗЫ ---
def get_orders():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, description, expected_budget, deadline,
            email, image, tg, created_at, viewed
        FROM orders_order
        ORDER BY created_at DESC
    """)

    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


# --- ПОЛУЧИТЬ ПО ДАТЕ ---
def get_orders_by_date(date1, date2):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, title, description, expected_budget, deadline,
               email, image, tg, created_at, viewed
        FROM orders_order
        WHERE created_at::date BETWEEN %s AND %s
        ORDER BY created_at DESC
    """, (date1, date2))

    data = cur.fetchall()
    cur.close()
    conn.close()
    return data


# --- ОБНОВИТЬ viewed ---
def set_viewed(order_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE orders_order SET viewed = TRUE WHERE id = %s",
        (order_id,)
    )

    conn.commit()
    cur.close()
    conn.close()


# --- ФОРМАТ ---
def format_order(o):
    return (
        f"<b>📦 Заказ №:</b> {o[0]}\n"
        f"-------------------------\n"
        f"<b>📝 Название:</b> {o[1]}\n"
        f"-------------------------\n"
        f"<b>📄 Описание:</b> {o[2]}\n"
        f"-------------------------\n"
        f"<b>💰 Бюджет:</b> {o[3]} $\n"
        f"-------------------------\n"
        f"<b>📅 Дедлайн:</b> {o[4]}\n"
        f"-------------------------\n"
        f"<b>📧 Email:</b> {o[5]}\n"
        f"-------------------------\n"
        f"<b>🖼 Фото:</b> {o[6] if o[6] else 'Нет'}\n"
        f"-------------------------\n"
        f"<b>💬 Telegram:</b> {o[7] if o[7] else 'Нет'}\n"
        f"-------------------------\n"
        f"<b>🕒 Создан:</b> {o[8]}\n"
        f"=========================\n"
    )


# --- START ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "Выбери действие 👇",
        reply_markup=buttons()
    )


# --- ВСЕ ЗАКАЗЫ ---
@bot.message_handler(func=lambda m: m.text == "📦 Показать заказы")
def show_btn(message):
    orders = get_orders()
    filtered = [o for o in orders if not o[9]]

    if not filtered:
        bot.send_message(message.chat.id, "❌ Нет непросмотренных заказов")
        return

    for o in filtered:
        markup = telebot.types.InlineKeyboardMarkup()

        btn = telebot.types.InlineKeyboardButton(
            "✅ Просмотрено",
            callback_data=f"viewed_{o[0]}"
        )
        markup.add(btn)

        bot.send_message(
            message.chat.id,
            format_order(o),
            parse_mode="HTML",
            reply_markup=markup
        )


# --- ПО ДАТЕ ---
@bot.message_handler(func=lambda m: m.text == "📅 По дате")
def date_btn(message):
    user_state[message.chat.id] = "waiting_date_from"

    bot.send_message(
        message.chat.id,
        "📅 Введи начальную дату (YYYY-MM-DD):"
    )


# --- ДАТА ОТ ---
@bot.message_handler(func=lambda message: user_state.get(message.chat.id) == "waiting_date_from")
def get_date_from(message):
    user_dates[message.chat.id] = {"from": message.text.strip()}
    user_state[message.chat.id] = "waiting_date_to"

    bot.send_message(
        message.chat.id,
        "📅 Теперь введи конечную дату (YYYY-MM-DD):"
    )


# --- ДАТА ДО ---
@bot.message_handler(func=lambda message: user_state.get(message.chat.id) == "waiting_date_to")
def get_date_to(message):
    try:
        date1 = user_dates[message.chat.id]["from"]
        date2 = message.text.strip()

        orders = get_orders_by_date(date1, date2)

        if not orders:
            bot.send_message(message.chat.id, "❌ Нет заказов за этот период")
        else:
            for o in orders:
                markup = None

                if not o[9]:
                    markup = telebot.types.InlineKeyboardMarkup()
                    btn = telebot.types.InlineKeyboardButton(
                        "✅ Просмотрено",
                        callback_data=f"viewed_{o[0]}"
                    )
                    markup.add(btn)

                bot.send_message(
                    message.chat.id,
                    format_order(o),
                    parse_mode="HTML",
                    reply_markup=markup
                )

    except Exception as e:
        print(e)
        bot.send_message(
            message.chat.id,
            "❌ Ошибка. Используй формат YYYY-MM-DD"
        )

    user_state.pop(message.chat.id, None)
    user_dates.pop(message.chat.id, None)


# --- CALLBACK ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("viewed_"))
def mark_viewed(call):
    order_id = int(call.data.split("_")[1])

    set_viewed(order_id)

    bot.answer_callback_query(call.id, "Отмечено как просмотрено ✅")

    bot.edit_message_reply_markup(
        call.message.chat.id,
        call.message.message_id,
        reply_markup=None
    )


# --- ЗАПУСК ---
bot.polling(none_stop=True)
