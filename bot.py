import logging
import os
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.environ['BOT_TOKEN']
CHANNEL_ID = os.environ['CHANNEL_ID']
TIMEZONE = ZoneInfo('America/Sao_Paulo')
CATEGORIES = {'dispensacao': 'Dispensação', 'renovacao': 'Renovação', 'outros': 'Outros'}
COOLDOWN_SECONDS = 60
last_submission = {}
last_by_category = {}
logging.basicConfig(level=logging.INFO)


def keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=f'type:{key}')] for key, label in CATEGORIES.items()])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('category', None)
    await update.effective_message.reply_text(
        '📍 Cadê Minha Vez? — Farmácia de Alto Custo (Asa Sul)\n\n'
        'Informe somente o horário agendado da última pessoa chamada no telão. '
        'Não envie nomes nem dados pessoais.\n\nSelecione o tipo de atendimento:',
        reply_markup=keyboard(),
    )


async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.removeprefix('type:')
    if category not in CATEGORIES:
        return
    context.user_data['category'] = category
    await query.edit_message_text(
        f'Atendimento: {CATEGORIES[category]}\n\n'
        'Qual é o horário de agendamento da última pessoa chamada?\n'
        'Envie somente no formato HH:MM (exemplo: 14:30).'
    )


async def receive_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = context.user_data.get('category')
    if not category:
        await update.message.reply_text('Para informar uma chamada, use /start e escolha o atendimento.')
        return

    raw = update.message.text.strip()
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', raw):
        await update.message.reply_text('Horário inválido. Envie apenas HH:MM, por exemplo 14:30. Não inclua nomes ou outros dados.')
        return

    now = time.monotonic()
    user_id = update.effective_user.id
    if now - last_submission.get(user_id, -float('inf')) < COOLDOWN_SECONDS:
        await update.message.reply_text('Aguarde um minuto antes de enviar outra atualização.')
        return
    if last_by_category.get(category) == raw:
        context.user_data.pop('category', None)
        await update.message.reply_text('Esse horário já é a última atualização recebida para esse atendimento. Use /start para outra informação.')
        return

    timestamp = datetime.now(TIMEZONE).strftime('%d/%m/%Y às %H:%M')
    message = (
        '📢 Última chamada informada — Farmácia de Alto Custo (Asa Sul)\n\n'
        f'🏷 Atendimento: {CATEGORIES[category]}\n'
        f'🕒 Horário agendado da pessoa chamada: {raw}\n'
        f'📅 Informação recebida em: {timestamp}\n\n'
        '⚠️ Informação colaborativa, não confirmada pela farmácia.'
    )
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=message)
    except Exception:
        logging.exception('Não foi possível publicar no canal')
        await update.message.reply_text('Não foi possível publicar agora. Tente novamente mais tarde.')
        return

    last_submission[user_id] = now
    last_by_category[category] = raw
    context.user_data.pop('category', None)
    await update.message.reply_text('✅ Atualização publicada no canal. Obrigado! Para enviar outra, use /start.')


async def reject_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text('Este bot recebe apenas tipo de atendimento e horário. Use /start para começar.')


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(select_category, pattern=r'^type:(dispensacao|renovacao|outros)$'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time))
    app.add_handler(MessageHandler(filters.ALL, reject_other))
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
