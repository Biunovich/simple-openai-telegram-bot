import logging
import os
import sys

import openai
from dotenv import load_dotenv
from openai import error
from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

logging.basicConfig(
    filename="logs/bot.log",
    encoding="utf-8",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(message)s",
    datefmt="%m/%d/%Y %H:%M:%S")
logger = logging.getLogger("Bot")
load_dotenv()

telegram_token = os.environ.get("TELEGRAM_TOKEN")
openai_api_key = os.environ.get("OPENAI_API_KEY")

if telegram_token is None or openai_api_key is None:
    logger.error("No environment variables were found")
    sys.exit()

openai.api_key = openai_api_key


def append_message(messages, role, message):
    messages.append({"role": role, "content": message})


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.from_user.first_name
    message = update.message.text
    user_id = str(update.message.from_user.id)

    messages = context.user_data.setdefault("messages", [])
    if (len(messages) == 0):
        append_message(messages, "system", "You are a helpful assistant")
    append_message(messages, "user", message)
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.5,
            user=user_id,
            request_timeout=30
        )
        reply = response.choices[0].message.content
        await update.message.reply_text(reply)
        append_message(messages, "assistant", reply)
        logger.info("name='%s' user_id=%s, history (last 3 messages)=%s",
                    name, user_id, list(
                        map(lambda x: f"{x['role']}:{x['content'][:100]}", messages[-3:]))
                    )
    except error.APIConnectionError as e:
        logger.error(repr(e))
        if (e.code == "context_length_exceeded"):
            context.user_data["messages"] = []
            await update.message.reply_text("Model's maximum context length exceeded, message history was cleaned")
        else:
            context.user_data["messages"].pop()
            await update.message.reply_text("Some error happened, please try to send message again")
    except Exception as e:
        logger.error(repr(e))
        context.user_data["messages"].pop()
        await update.message.reply_text("Some error happened, please try to send message again")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.from_user.first_name
    await update.message.reply_text(f"Welcome {name} to the simple OpenAI chat bot!")


async def clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["messages"] = []
    await update.message.reply_text(f"Message history was cleaned!")

application = Application.builder().token(telegram_token).build()
application.add_handler(MessageHandler(
    filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("clean", clean))
application.run_polling()
