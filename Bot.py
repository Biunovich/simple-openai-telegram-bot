import logging
import os
import sys

import openai
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

logging.basicConfig(
    filename='bot.log',
    encoding='utf-8',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s',
    datefmt='%m/%d/%Y %H:%M:%S')
logger = logging.getLogger("Bot")
load_dotenv()

telegram_token = os.environ.get("TELEGRAM_TOKEN")
openai_api_key = os.environ.get("OPENAI_API_KEY")

if telegram_token is None or openai_api_key is None:
    print("No environment variables were found")
    sys.exit()

openai.api_key = openai_api_key


def append_message(messages, role, message):
    messages.append({"role": role, "content": message})


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username
    message = update.message.text

    messages = context.user_data.setdefault("messages", [])
    if (len(messages) == 0):
        append_message(messages, "system", "You are a helpful assistant")
    append_message(messages, "user", message)
    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.5,
        user=username
    )
    reply = response.choices[0].message.content
    await update.message.reply_text(reply)
    append_message(messages, "assistant", reply)
    logger.info("username=%s, history (last 3 messages)=%s",
                username, list(map(lambda x: "{}:{}".format(
                    x["role"], x["content"][:100]), messages[-3:]))
                )

application = Application.builder().token(telegram_token).build()
application.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND, handle_message))
application.run_polling()
