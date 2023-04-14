import os
import logging
import traceback
import html
import json
import tempfile
from pathlib import Path
from datetime import datetime

import telegram
from telegram import (
    Update,
    User,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    LabeledPrice,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackContext,
    PreCheckoutQueryHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ParseMode, ChatAction
import config
import database
import ai_generator.presentation as presentation

# setup
db = database.Database()
logger = logging.getLogger(__name__)

CHAT_MODES = config.chat_modes

HELP_MESSAGE = """Commands:
⚪ /menu – Show menu
⚪ /mode – Select mode
⚪ /balance – Show balance
⚪ /help – Show help
"""


async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("/menu", "Show menu"),
        BotCommand("/mode", "Select mode"),
        BotCommand("/balance", "Show balance"),
        BotCommand("/help", "Show help"),
    ])


def split_text_into_chunks(text, chunk_size):
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]


async def register_user_if_not_exists(update: Update, context: CallbackContext, user: User):
    if not db.check_if_user_exists(user.id):
        db.add_new_user(
            user.id,
            update.message.chat_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )


async def start_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id

    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    reply_text = "Hi! I'm bot implemented with ChatGPT integration 🤖\n\n"
    reply_text += HELP_MESSAGE

    reply_text += "\nAnd now... choose what you want!"

    await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)


async def help_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML)


async def message_handle(update: Update, context: CallbackContext, message=None):
    # check if message is edited
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return

    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id

    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    # # send typing action
    # await update.message.chat.send_action(action="typing")  ###


async def show_chat_modes_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    keyboard = []
    for chat_mode, chat_mode_dict in CHAT_MODES.items():
        keyboard.append([InlineKeyboardButton(chat_mode_dict["name"], callback_data=f"set_chat_mode|{chat_mode}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Select chat mode:", reply_markup=reply_markup)


async def set_chat_mode_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    user_id = update.callback_query.from_user.id

    query = update.callback_query
    await query.answer()

    chat_mode = query.data.split("|")[1]

    db.set_user_attribute(user_id, "current_chat_mode", chat_mode)

    # await query.edit_message_text(f"<b>{CHAT_MODES[chat_mode]['name']}</b> mode is set", parse_mode=ParseMode.HTML)

    await query.edit_message_text(f"{CHAT_MODES[chat_mode]['welcome_message']}", parse_mode=ParseMode.HTML)


SELECTING_ACTION, SELECTING_LANGUAGE, SELECTING_TEMPLATE, SELECTING_TYPE, SELECTING_SLIDE_COUNT, INPUT_TOPIC, \
    INPUT_PROMPT = map(chr, range(7))
END = ConversationHandler.END
PRESENTATION = "Presentation"
ABSTRACT = "Abstract"
LANGUAGES = ["English", "Ukrainian", "Polish", "Russian", "Spanish", "French", "German", "Italian", "Portuguese"]
LANGUAGES_EMOJI = ["🇬🇧", "🇺🇦", "🇵🇱", "🏳️", "🇪🇸", "🇫🇷", "🇩🇪", "🇮🇹", "🇵🇹"]  # Should have the same count with languages
TEMPLATES = ["Mountains", "Organic", "East Asia", "Explore", "3D Float", "Luminous", "Academic"]
TEMPLATES_EMOJI = ["🗻", "🌿", "🐼", "🧭", "🌑", "🕯️", "🎓"]
TYPES = ["Fun", "Serious", "Creative", "Informative", "Inspirational", "Motivational", "Educational", "Historical",
         "Romantic", "Mysterious", "Relaxing", "Adventurous"]
TYPES_EMOJI = ["😂", "😐", "🎨", "📚", "🌟", "💪", "👨‍🎓", "🏛️", "💕", "🕵️‍♂️", "🧘‍♀️", "🗺️"]
COUNTS = [str(i) for i in range(3, 15)]
BACK = "⬅️Back"
MENU = "⬅️Menu"
(
    MENU_CHOICE,
    LANGUAGE_CHOICE,
    TEMPLATE_CHOICE,
    TYPE_CHOICE,
    COUNT_SLIDE_CHOICE,
    TOPIC_CHOICE,
    API_RESPONSE,
    START_OVER,
    MESSAGE_ID,
) = map(chr, range(10, 19))


async def menu_handle(update: Update, context: CallbackContext) -> str:
    if context.user_data.get(START_OVER):
        await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    else:
        await register_user_if_not_exists(update, context, update.message.from_user)

        try:
            await context.bot.deleteMessage(message_id=context.user_data[MESSAGE_ID].message_id - 1,
                                            chat_id=context.user_data[MESSAGE_ID].chat_id)
            await context.bot.deleteMessage(message_id=context.user_data[MESSAGE_ID].message_id,
                                            chat_id=context.user_data[MESSAGE_ID].chat_id)
        except Exception:
            pass

    keyboard = [
        [
            InlineKeyboardButton(f"💻{PRESENTATION}", callback_data=PRESENTATION)
        ],
        [
            InlineKeyboardButton(f"📝{ABSTRACT}", callback_data=ABSTRACT)
        ]
    ]
    if context.user_data.get(START_OVER):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Menu:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        context.user_data[MESSAGE_ID] = await update.message.reply_text("Menu:",
                                                                        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data[START_OVER] = False
    return SELECTING_ACTION


async def language_callback(update: Update, context: CallbackContext) -> str:  # flags inline buttons
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    context.user_data[MENU_CHOICE] = data
    text = f"Choose language of your {data}:"
    keyboard = []
    for i, languages in enumerate(LANGUAGES):
        if i % 3 == 0:
            keyboard.append([InlineKeyboardButton(LANGUAGES_EMOJI[i] + languages,
                                                  callback_data=f"language_{languages}")])
        else:
            keyboard[-1].append(InlineKeyboardButton(LANGUAGES_EMOJI[i] + languages,
                                                     callback_data=f"language_{languages}"))
    keyboard.append([InlineKeyboardButton(text=BACK, callback_data=str(END))])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return SELECTING_LANGUAGE


async def template_callback(update: Update, context: CallbackContext) -> str:  # many inline buttons
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    context.user_data[LANGUAGE_CHOICE] = data
    text = f"Choose template of your {context.user_data[MENU_CHOICE]}:"
    keyboard = []
    for i, templates in enumerate(TEMPLATES):
        if i % 3 == 0:
            keyboard.append([InlineKeyboardButton(TEMPLATES_EMOJI[i] + templates,
                                                  callback_data=f"template_{templates}")])
        else:
            keyboard[-1].append(InlineKeyboardButton(TEMPLATES_EMOJI[i] + templates,
                                                     callback_data=f"template_{templates}"))
    keyboard.append([InlineKeyboardButton(text=MENU, callback_data=str(END))])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return SELECTING_TEMPLATE


async def type_callback(update: Update, context: CallbackContext) -> str:
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    match context.user_data[MENU_CHOICE]:
        case "Presentation":
            context.user_data[TEMPLATE_CHOICE] = data
        case "Abstract":
            context.user_data[LANGUAGE_CHOICE] = data
    text = f"Choose type of your {context.user_data[MENU_CHOICE]}"
    keyboard = []
    for i, types in enumerate(TYPES):
        if i % 3 == 0:
            keyboard.append([InlineKeyboardButton(TYPES_EMOJI[i] + types, callback_data=f"type_{types}")])
        else:
            keyboard[-1].append(InlineKeyboardButton(TYPES_EMOJI[i] + types, callback_data=f"type_{types}"))
    keyboard.append([InlineKeyboardButton(text=MENU, callback_data=str(END))])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return SELECTING_TYPE


async def slide_count_callback(update: Update, context: CallbackContext) -> str:  # many inline buttons ?3-12?
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    context.user_data[TYPE_CHOICE] = data
    text = f"Choose the number of slides for your {context.user_data[MENU_CHOICE]}:"
    keyboard = []
    for i, counts in enumerate(COUNTS):
        if i % 3 == 0:
            keyboard.append([InlineKeyboardButton(counts, callback_data=f"slide_count_{counts}")])
        else:
            keyboard[-1].append(InlineKeyboardButton(counts, callback_data=f"slide_count_{counts}"))
    keyboard.append([InlineKeyboardButton(text=MENU, callback_data=str(END))])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return SELECTING_SLIDE_COUNT


async def topic_callback(update: Update, context: CallbackContext) -> str:  # user message
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    text = f"Whats topic of your {context.user_data[MENU_CHOICE]}?"
    match context.user_data[MENU_CHOICE]:
        case "Presentation":
            context.user_data[COUNT_SLIDE_CHOICE] = data
        case "Abstract":
            context.user_data[TYPE_CHOICE] = data
    await query.answer()
    await query.edit_message_text(text=text)
    return INPUT_TOPIC


async def save_input(update: Update, context: CallbackContext):  # user message
    if update.edited_message is not None:
        return
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_data = context.user_data
    user_data[TOPIC_CHOICE] = update.message.text
    user_id = update.message.from_user.id
    message_id = update.message.message_id
    user_mode = db.get_user_attribute(user_id, "current_chat_mode")
    menu_choice = user_data[MENU_CHOICE]
    match menu_choice:
        case "Presentation":
            language_choice = user_data[LANGUAGE_CHOICE].replace("language_", "")
            template_choice = user_data[TEMPLATE_CHOICE].replace("template_", "")
            type_choice = user_data[TYPE_CHOICE].replace("type_", "")
            count_slide_choice = user_data[COUNT_SLIDE_CHOICE].replace("slide_count_", "")
            topic_choice = user_data[TOPIC_CHOICE]
            prompt = await presentation.generate_ppt_prompt(language_choice, type_choice, count_slide_choice,
                                                            topic_choice)
            if user_mode == "auto":
                available_tokens = db.get_user_attribute(user_id, "n_available_tokens")
                if available_tokens > 0:
                    used_tokens = db.get_user_attribute(user_id, "n_used_tokens")
                    try:
                        response, n_used_tokens = await presentation.process_ppt_prompt(prompt)
                    except OverflowError:
                        await update.message.reply_text(text="System is currently overloaded. Please try again. 😊",
                                                        reply_to_message_id=message_id)
                        return END
                    except RuntimeError:
                        await update.message.reply_text(text="Some error happened. Please try again. 😊",
                                                        reply_to_message_id=message_id)
                        return END
                    db.set_user_attribute(user_id, "n_available_tokens", available_tokens - n_used_tokens)
                    db.set_user_attribute(user_id, "n_used_tokens", n_used_tokens + used_tokens)
                    pptx_bytes, pptx_title = await presentation.generate_ppt(response, template_choice)
                    await update.message.reply_document(document=pptx_bytes, filename=pptx_title)
                else:
                    await update.message.reply_text("You have not enough tokens.")
            else:
                await update.message.reply_text(text=prompt)
                return INPUT_PROMPT

        case "Abstract":
            language_choice = user_data[LANGUAGE_CHOICE].replace("language_", "")
            type_choice = user_data[TYPE_CHOICE].replace("type_", "")
            topic_choice = user_data[TOPIC_CHOICE]
    return END


async def prompt_callback(update: Update, context: CallbackContext):  # user message, skip if mode == auto
    if update.edited_message is not None:
        return
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_data = context.user_data
    user_data[API_RESPONSE] = update.message.text
    menu_choice = user_data[MENU_CHOICE]
    template_choice = user_data[TEMPLATE_CHOICE].replace("template_", "")
    match menu_choice:
        case "Presentation":
            api_response = user_data[API_RESPONSE]
            try:
                pptx_bytes, pptx_title = await presentation.generate_ppt(api_response, template_choice)
                await update.message.reply_document(document=pptx_bytes, filename=pptx_title)
            except IndexError:
                await update.message.reply_text("Check inserted data and try again!")
                return INPUT_PROMPT
        case "Abstract":
            pass

    return END


async def end_second_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to top level conversation."""
    context.user_data[START_OVER] = True
    await menu_handle(update, context)

    return END


async def show_balance_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)

    user_id = update.message.from_user.id
    db.set_user_attribute(user_id, "last_interaction", datetime.now())

    n_used_tokens = db.get_user_attribute(user_id, "n_used_tokens")
    n_available_tokens = db.get_user_attribute(user_id, "n_available_tokens")

    text = f"🟢Your have <b>{n_available_tokens}</b> tokens left\n"
    text += f"You totally spent <b>{n_used_tokens}</b> tokens\n\n"

    keyboard = [
        [
            InlineKeyboardButton("🟣+10K tokens — 0.99$", callback_data="buy_tokens_10")
        ],
        [
            InlineKeyboardButton("🟣+30K tokens — 2.49$", callback_data="buy_tokens_30")
        ],
        [
            InlineKeyboardButton("🟣+100K tokens — 4.99$", callback_data="buy_tokens_100")
        ]
    ]

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))


async def buy_tokens_callback(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    user_id = query.from_user.id

    await query.answer()
    # Calculate the price based on the token amount
    if query.data == "buy_tokens_10":
        price = 0.99
        token_amount = 10000
    elif query.data == "buy_tokens_30":
        price = 2.49
        token_amount = 30000
    elif query.data == "buy_tokens_100":
        price = 4.99
        token_amount = 100000

    # Create an invoice
    title = f"{token_amount} tokens"
    description = f"Purchase of {token_amount} tokens for the chat bot"
    payload = f"{user_id}-{token_amount}"  # Custom payload to identify the user and token amount
    currency = "USD"
    prices = [LabeledPrice("Test", int(float(price) * 100))]
    # Send the invoice to the user
    await context.bot.send_invoice(chat_id=user_id,
                                   title=title,
                                   description=description,
                                   start_parameter=payload,
                                   provider_token=config.provider_token,
                                   currency=currency,
                                   prices=prices,
                                   payload=payload
                                   )


async def pre_checkout_callback(update: Update, context: CallbackContext):
    query = update.pre_checkout_query
    await context.bot.answer_pre_checkout_query(query.id, ok=True)


async def successful_payment_handle(update: Update, context: CallbackContext):
    await register_user_if_not_exists(update, context, update.message.from_user)
    payment = update.message.successful_payment
    payment_info = payment.invoice_payload.split('-')
    payment_chat_id = int(payment_info[0])
    payment_tokens = int(payment_info[1])
    n_available_tokens = db.get_user_attribute(payment_chat_id, "n_available_tokens")
    db.set_user_attribute(payment_chat_id, "n_available_tokens", n_available_tokens + payment_tokens)
    db.set_user_attribute(payment_chat_id, "last_invoice_payload", payment.invoice_payload)
    await update.message.reply_text("Thank you for your payment!")


async def edited_message_handle(update: Update, context: CallbackContext):
    text = "🥲 Unfortunately, message <b>editing</b> is not supported"
    await update.edited_message.reply_text(text, parse_mode=ParseMode.HTML)


async def error_handle(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    try:
        # collect error message
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            f"An exception was raised while handling an update\n"
            f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
            "</pre>\n\n"
            f"<pre>{html.escape(tb_string)}</pre>"
        )

        # split text into multiple messages due to 4096 character limit
        for message_chunk in split_text_into_chunks(message, 4096):
            try:
                await context.bot.send_message(update.effective_chat.id, message_chunk, parse_mode=ParseMode.HTML)
            except telegram.error.BadRequest:
                # answer has invalid characters, so we send it without parse_mode
                await context.bot.send_message(update.effective_chat.id, message_chunk)
    except:
        await context.bot.send_message(update.effective_chat.id, "Some error in error handler")


def run_bot() -> None:
    application = (
        ApplicationBuilder()
        .token(config.telegram_token)
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )

    # add handlers
    if len(config.allowed_telegram_usernames) == 0:
        user_filter = filters.ALL
    else:
        user_filter = filters.User(username=config.allowed_telegram_usernames)

    application.add_handler(CommandHandler("start", start_handle, filters=user_filter))
    application.add_handler(CommandHandler("help", help_handle, filters=user_filter))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & user_filter, message_handle))

    application.add_handler(CommandHandler("mode", show_chat_modes_handle, filters=user_filter))
    application.add_handler(CallbackQueryHandler(set_chat_mode_handle, pattern="^set_chat_mode"))

    presentation_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(language_callback, pattern=f"^{PRESENTATION}$")],
        states={
            SELECTING_LANGUAGE: [CallbackQueryHandler(template_callback, pattern="^language_")],
            SELECTING_TEMPLATE: [CallbackQueryHandler(type_callback, pattern="^template_")],
            SELECTING_TYPE: [CallbackQueryHandler(slide_count_callback, pattern="^type_")],
            SELECTING_SLIDE_COUNT: [CallbackQueryHandler(topic_callback, pattern="^slide_count_")],
            INPUT_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_input)],
            INPUT_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, prompt_callback)],
        },
        fallbacks=[
            CallbackQueryHandler(end_second_level, pattern=f"^{str(END)}$"),
            CommandHandler("menu", menu_handle, filters=user_filter)
        ],
        map_to_parent={
            END: SELECTING_ACTION,
        },
        allow_reentry=True,
    )

    abstract_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(language_callback, pattern=f"^{ABSTRACT}$")],
        states={
            SELECTING_LANGUAGE: [CallbackQueryHandler(type_callback, pattern="^language_")],
            SELECTING_TYPE: [CallbackQueryHandler(topic_callback, pattern="^type_")],
            INPUT_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_input)],
            INPUT_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, prompt_callback)],
        },
        fallbacks=[
            CallbackQueryHandler(end_second_level, pattern=f"^{str(END)}$"),
            CommandHandler("menu", menu_handle, filters=user_filter)
        ],
        map_to_parent={
            END: SELECTING_ACTION,
        },
        allow_reentry=True,
    )

    selection_handlers = [
        presentation_conv,
        abstract_conv,
    ]

    menu_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("menu", menu_handle, filters=user_filter)],
        states={
            SELECTING_ACTION: selection_handlers,
        },
        fallbacks=[
            CommandHandler("menu", menu_handle, filters=user_filter)
        ],
    )
    application.add_handler(menu_conv_handler, group=1)

    application.add_handler(CommandHandler("balance", show_balance_handle, filters=user_filter))
    application.add_handler(CallbackQueryHandler(buy_tokens_callback, pattern="^buy_tokens_"))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handle))

    application.add_error_handler(error_handle)

    # start the bot
    application.run_polling()


if __name__ == "__main__":
    run_bot()
