import json
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
import config

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка материалов
with open('data.json', 'r', encoding='utf-8') as f:
    MATERIALS = json.load(f)

# Состояния для диалога
WORK_TYPE, LENGTH, WIDTH, HEIGHT, CONFIRM = range(5)

# Клавиатуры
work_type_keyboard = ReplyKeyboardMarkup(
    [
        ["🧱 Штукатурка стен"],
        ["📐 Укладка плитки"],
        ["🏗️ Стяжка пола"],
        ["❌ Отмена"]
    ],
    resize_keyboard=True
)

confirm_keyboard = ReplyKeyboardMarkup(
    [
        ["✅ Да, рассчитать"],
        ["🔄 Ввести заново"],
        ["❌ Отмена"]
    ],
    resize_keyboard=True
)


def calculate_materials(work_type, length, width, height):
    """Расчет материалов"""
    result = {
        'materials': [],
        'total_cost': 0,
        'advice': ""
    }

    if work_type == "🧱 Штукатурка стен":
        perimeter = 2 * (length + width)
        area = perimeter * height
        material = MATERIALS['штукатурка']

        consumption_kg = area * material['consumption_per_sqm']
        bags = int(consumption_kg // 30 + (1 if consumption_kg % 30 > 0 else 0))
        cost = bags * material['price_per_unit']

        result['materials'].append({
            'name': material['name'],
            'quantity': bags,
            'unit': material['unit'],
            'price': material['price_per_unit'],
            'subtotal': cost
        })
        result['total_cost'] += cost
        result['advice'] = f"💡 Совет: Добавьте запас 10% на неровности стен (+{int(bags * 0.1)} мешков)"

    elif work_type == "📐 Укладка плитки":
        area = length * width
        material = MATERIALS['плитка']

        sqm_with_reserve = area * 1.1
        cost = sqm_with_reserve * material['price_per_unit']

        result['materials'].append({
            'name': material['name'],
            'quantity': round(sqm_with_reserve, 2),
            'unit': material['unit'],
            'price': material['price_per_unit'],
            'subtotal': round(cost, 2)
        })
        result['total_cost'] += cost
        result['advice'] = "💡 Совет: Обязательно берите запас 10-15% на подрезку плитки"

    elif work_type == "🏗️ Стяжка пола":
        area = length * width
        thickness_cm = 5
        material = MATERIALS['стяжка']

        consumption_kg = material['consumption_per_sqm_per_cm'] * area * thickness_cm
        bags = int(consumption_kg // 40 + (1 if consumption_kg % 40 > 0 else 0))
        cost = bags * material['price_per_unit']

        result['materials'].append({
            'name': material['name'],
            'quantity': bags,
            'unit': material['unit'],
            'price': material['price_per_unit'],
            'subtotal': cost
        })
        result['total_cost'] += cost
        result['advice'] = f"💡 Совет: Для стяжки лучше брать запас 5-10% (+{int(bags * 0.1)} мешков)"

    return result


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога"""
    await update.message.reply_text(
        "👋 Привет! Я бот-сметчик. Помогу быстро рассчитать материалы для ремонта.\n\n"
        "Выберите тип работ:",
        reply_markup=work_type_keyboard
    )
    return WORK_TYPE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена"""
    await update.message.reply_text(
        "❌ Действие отменено. Чтобы начать заново, нажмите /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def work_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора типа работ"""
    text = update.message.text

    if text == "❌ Отмена":
        return await cancel(update, context)

    if text not in ["🧱 Штукатурка стен", "📐 Укладка плитки", "🏗️ Стяжка пола"]:
        await update.message.reply_text("Пожалуйста, выберите тип работ из меню 👇")
        return WORK_TYPE

    context.user_data['work_type'] = text
    await update.message.reply_text(
        f"Выбрано: {text}\n\n"
        "📏 Введите длину комнаты (в метрах):\n"
        "Пример: 4.5",
        reply_markup=ReplyKeyboardRemove()
    )
    return LENGTH


async def length(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка длины"""
    try:
        length = float(update.message.text.replace(',', '.'))
        if length <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите положительное число (например: 4.5)")
        return LENGTH

    context.user_data['length'] = length
    await update.message.reply_text("📏 Введите ширину комнаты (в метрах):")
    return WIDTH


async def width(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ширины"""
    try:
        width = float(update.message.text.replace(',', '.'))
        if width <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите положительное число")
        return WIDTH

    context.user_data['width'] = width

    # Для стяжки высота не нужна
    if context.user_data['work_type'] == "🏗️ Стяжка пола":
        context.user_data['height'] = 5.0
        return await show_confirmation(update, context)
    else:
        await update.message.reply_text("📏 Введите высоту потолков (в метрах):")
        return HEIGHT


async def height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка высоты"""
    try:
        height = float(update.message.text.replace(',', '.'))
        if height <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите положительное число")
        return HEIGHT

    context.user_data['height'] = height
    return await show_confirmation(update, context)


async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показ данных для подтверждения"""
    data = context.user_data

    text = (
        f"📋 Проверьте введенные данные:\n\n"
        f"🧱 Тип работ: {data['work_type']}\n"
        f"📏 Длина: {data['length']} м\n"
        f"📐 Ширина: {data['width']} м\n"
    )

    if 'height' in data:
        text += f"📏 Высота: {data['height']} м\n"

    text += "\nВсё верно?"

    await update.message.reply_text(text, reply_markup=confirm_keyboard)
    return CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Подтверждение и расчет"""
    text = update.message.text

    if text == "❌ Отмена":
        return await cancel(update, context)

    if text == "🔄 Ввести заново":
        await update.message.reply_text(
            "📏 Введите длину комнаты заново:",
            reply_markup=ReplyKeyboardRemove()
        )
        return LENGTH

    if text == "✅ Да, рассчитать":
        data = context.user_data

        await update.message.reply_text("⏳ Считаю...", reply_markup=ReplyKeyboardRemove())

        result = calculate_materials(
            data['work_type'],
            data['length'],
            data['width'],
            data.get('height', 2.5)
        )

        response = f"✅ **Результаты расчета:**\n\n"
        response += f"**Тип работ:** {data['work_type']}\n"
        response += f"**Помещение:** {data['length']} x {data['width']} м"
        if 'height' in data:
            response += f" x {data['height']} м"
        response += f"\n\n**Необходимые материалы:**\n"

        for item in result['materials']:
            response += f"• {item['name']}: {item['quantity']} {item['unit']}\n"

        response += f"\n💰 **Примерная стоимость:** {result['total_cost']:,.0f} руб.\n\n"
        response += f"{result['advice']}\n\n"
        response += "Для нового расчета нажмите /start"

        await update.message.reply_text(response)

        context.user_data.clear()
        return ConversationHandler.END

    return CONFIRM


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Помощь"""
    await update.message.reply_text("Используйте /start для начала расчета")


def main() -> None:
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(config.BOT_TOKEN).build()

    # Создаем обработчик диалога
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            WORK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, work_type)],
            LENGTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, length)],
            WIDTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, width)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, height)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))

    # Запускаем бота
    print("Бот запущен! Нажми Ctrl+C для остановки")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()