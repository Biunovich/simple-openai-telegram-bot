import logging
import os
import sys

import openai
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters, AIORateLimiter)

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
allowed_users = os.environ.get("ALLOWED_USERS")

if allowed_users is None:
    logger.warning("Any user can send messages to this bot")
else:
    allowed_users = list(map(int, allowed_users.split(",")))

if telegram_token is None or openai_api_key is None:
    logger.error("No environment variables were found")
    sys.exit()

openai_client = openai.AsyncOpenAI(api_key=openai_api_key, timeout=30)


def append_message(messages: list, role: str, message: str):
    messages.append({"role": role, "content": message})


async def process_message(context: ContextTypes.DEFAULT_TYPE):
    update: Update = context.job.data
    user_id = str(context.job.user_id)
    name = update.message.from_user.first_name
    message = update.message.text

    messages = context.user_data.setdefault("messages", [])
    if (len(messages) == 0):
        append_message(messages, "system", "You are a helpful assistant")
    append_message(messages, "user", message)
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            user=user_id
        )
        reply = response.choices[0].message.content
        await update.message.reply_text(reply)
        append_message(messages, "assistant", reply)
        logger.info("name='%s' user_id=%s, history (last 3 messages)=%s",
                    name, user_id, list(
                        map(lambda x: f"{x['role']}:{x['content'][:100]}", messages[-3:]))
                    )
    except openai.APIConnectionError as e:
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
    finally:
        context.user_data["processing"] = False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    try:
        if context.user_data.setdefault("processing", False):
            await update.message.reply_text("The bot has not yet answered the previous message, please try to send a message again after the bot replies")
            return
        context.user_data["processing"] = True
        context.job_queue.run_custom(process_message, {}, data=update, name=str(user_id), user_id=user_id)
    except Exception as e:
        logger.error(repr(e))
        await update.message.reply_text("Some error happened, please try to send message again")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.from_user.first_name
    await update.message.reply_text(f"Welcome {name} to the simple OpenAI chat bot!")


async def clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["messages"] = []
    await update.message.reply_text("Message history was cleaned!")

application = Application.builder().token(telegram_token).rate_limiter(AIORateLimiter()).build()
application.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(user_id=allowed_users, allow_empty=True), handle_message)
)
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("clean", clean))
application.run_polling()
