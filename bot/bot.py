import asyncio
import html
import json
import logging
import traceback
from datetime import datetime

import ai_generator.abstract as abstract
import ai_generator.openai_utils as openai_utils
import ai_generator.presentation as presentation

import config

import database

import telegram
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Update,
    User,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)


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
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_id = update.message.from_user.id

    db.set_user_attribute(user_id, "last_interaction", datetime.now())


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
    await query.edit_message_text(f"{CHAT_MODES[chat_mode]['welcome_message']}\n\n" + HELP_MESSAGE,
                                  parse_mode=ParseMode.HTML)


SELECTING_ACTION, SELECTING_MENU, INPUT_TOPIC, INPUT_PROMPT = map(chr, range(4))
END = ConversationHandler.END
PRESENTATION = "Presentation"
ABSTRACT = "Abstract"
LANGUAGES = ['English', 'Russian', 'German', 'French', 'Italian', 'Spanish', 'Ukrainian', 'Polish', 'Turkish',
             'Romanian', 'Dutch', 'Greek', 'Czech', 'Portuguese', 'Swedish', 'Hungarian', 'Serbian', 'Bulgarian',
             'Danish', 'Norwegian', 'Finnish', 'Slovak', 'Croatian', 'Arabic', 'Hebrew', 'Lithuanian', 'Slovenian',
             'Bengali', 'Chinese', 'Persian', 'Indonesian', 'Latvian', 'Tamil', 'Japanese', 'Estonian', 'Telugu',
             'Korean', 'Thai', 'Icelandic', 'Vietnamese']
LANGUAGES_EMOJI = ['🇬🇧', '🏳️', '🇩🇪', '🇫🇷', '🇮🇹', '🇪🇸', '🇺🇦', '🇵🇱', '🇹🇷', '🇷🇴', '🇳🇱', '🇬🇷',
                   '🇨🇿', '🇵🇹', '🇸🇪', '🇭🇺', '🇷🇸', '🇧🇬', '🇩🇰', '🇳🇴', '🇫🇮', '🇸🇰', '🇭🇷', '🇸🇦',
                   '🇮🇱', '🇱🇹', '🇸🇮', '🇧🇩', '🇨🇳', '🇮🇷', '🇮🇩', '🇱🇻', '🇮🇳', '🇯🇵', '🇪🇪', '🇮🇳',
                   '🇰🇷', '🇹🇭', '🇮🇸', '🇻🇳']
TEMPLATES = ["Mountains", "Organic", "East Asia", "Explore", "3D Float", "Luminous", "Academic", "Snowflake"]
TEMPLATES_EMOJI = ["🗻", "🌿", "🐼", "🧭", "🌑", "🕯️", "🎓", "❄️"]
TYPES = ["Fun", "Serious", "Creative", "Informative", "Inspirational", "Motivational", "Educational", "Historical",
         "Romantic", "Mysterious", "Relaxing", "Adventurous", "Humorous", "Scientific", "Musical", "Horror", "Fantasy",
         "Action", "Dramatic", "Satirical", "Poetic", "Thriller", "Sports", "Comedy", "Biographical", "Political",
         "Magical", "Mystery", "Travel", "Documentary", "Crime", "Cooking"]
TYPES_EMOJI = ["😂", "😐", "🎨", "📚", "🌟", "💪", "👨‍🎓", "🏛️", "💕", "🕵️‍♂️", "🧘‍♀️", "🗺️", "🤣", "🔬", "🎵", "😱", "🦄",
               "💥", "😮", "🙃", "🌸", "😰", "⚽", "😆", "📜", "🗳️", "✨", "🔮", "✈️", "🎥", "🚓", "🍽️"]
COUNTS = [str(i) for i in range(3, 27)]
COUNTS_EMOJI = ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
BACK = "⬅️Back"
(
    PRESENTATION_LANGUAGE_CHOICE,
    ABSTRACT_LANGUAGE_CHOICE,
    TEMPLATE_CHOICE,
    PRESENTATION_TYPE_CHOICE,
    ABSTRACT_TYPE_CHOICE,
    COUNT_SLIDE_CHOICE,
    TOPIC_CHOICE,
    API_RESPONSE,
    START_OVER,
    MESSAGE_ID,
) = map(chr, range(10, 20))


async def menu_handle(update: Update, context: CallbackContext) -> str:
    try:
        await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    except AttributeError:
        await register_user_if_not_exists(update, context, update.message.from_user)
        try:
            if MESSAGE_ID in context.chat_data:
                await context.bot.delete_message(chat_id=update.effective_chat.id,
                                                 message_id=context.chat_data[MESSAGE_ID].message_id)
        except telegram.error.BadRequest:
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
        context.chat_data[MESSAGE_ID] = await update.message.reply_text("Menu:",
                                                                        reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data[START_OVER] = False
    return SELECTING_ACTION


async def generate_keyboard(page, word_array, emoji_array, callback):
    keyboard = []
    per_page = 12
    for i, words in enumerate(word_array[(page-1)*per_page:page*per_page]):
        if i % 2 == 0:
            keyboard.append([InlineKeyboardButton(emoji_array[i+((page-1)*per_page)] + words,
                                                  callback_data=f"{callback}{words}")])
        else:
            keyboard[-1].append(InlineKeyboardButton(emoji_array[i+((page-1)*per_page)] + words,
                                                     callback_data=f"{callback}{words}"))
    if len(word_array) > per_page and page == 1:
        keyboard.append([InlineKeyboardButton(">>", callback_data=f"page_{callback}{page+1}")])
    elif page != 1:
        if len(word_array) > page*per_page:
            keyboard.append([
                InlineKeyboardButton("<<", callback_data=f"page_{callback}{page-1}"),
                InlineKeyboardButton(">>", callback_data=f"page_{callback}{page+1}")
            ])
        else:
            keyboard.append([InlineKeyboardButton("<<", callback_data=f"page_{callback}{page-1}")])
    keyboard.append([InlineKeyboardButton(text=BACK, callback_data=str(END))])
    return InlineKeyboardMarkup(keyboard)


async def presentation_language_callback(update: Update, context: CallbackContext) -> str:
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    page = 1
    if data.startswith("page_language_"):
        page = int(data.replace("page_language_", ""))
    text = "Choose language of your Presentation:"
    reply_markup = await generate_keyboard(page, LANGUAGES, LANGUAGES_EMOJI, "language_")
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return SELECTING_MENU


async def abstract_language_callback(update: Update, context: CallbackContext) -> str:
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    page = 1
    if data.startswith("page_language_"):
        page = int(data.replace("page_language_", ""))
    text = "Choose language of your Abstract:"
    reply_markup = await generate_keyboard(page, LANGUAGES, LANGUAGES_EMOJI, "language_")
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return SELECTING_MENU


async def presentation_template_callback(update: Update, context: CallbackContext) -> str:
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    page = 1
    if data.startswith("page_template_"):
        page = int(data.replace("page_template_", ""))
    else:
        context.user_data[PRESENTATION_LANGUAGE_CHOICE] = data
    text = "Choose template of your Presentation:"
    reply_markup = await generate_keyboard(page, TEMPLATES, TEMPLATES_EMOJI, "template_")
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return SELECTING_MENU


async def presentation_type_callback(update: Update, context: CallbackContext) -> str:
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    page = 1
    if data.startswith("page_type_"):
        page = int(data.replace("page_type_", ""))
    else:
        context.user_data[TEMPLATE_CHOICE] = data
    text = "Choose type of your Presentation:"
    reply_markup = await generate_keyboard(page, TYPES, TYPES_EMOJI, "type_")
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return SELECTING_MENU


async def abstract_type_callback(update: Update, context: CallbackContext) -> str:
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    page = 1
    if data.startswith("page_type_"):
        page = int(data.replace("page_type_", ""))
    else:
        context.user_data[ABSTRACT_LANGUAGE_CHOICE] = data
    text = "Choose type of your Abstract:"
    reply_markup = await generate_keyboard(page, TYPES, TYPES_EMOJI, "type_")
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return SELECTING_MENU


async def presentation_slide_count_callback(update: Update, context: CallbackContext) -> str:
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    page = 1
    if data.startswith("page_slide_count_"):
        page = int(data.replace("page_slide_count_", ""))
    else:
        context.user_data[PRESENTATION_TYPE_CHOICE] = data
    text = "Choose an approximate number of slides for your Presentation:"
    reply_markup = await generate_keyboard(page, COUNTS, COUNTS_EMOJI, "slide_count_")
    await query.answer()
    await query.edit_message_text(text=text, reply_markup=reply_markup)
    return SELECTING_MENU


async def presentation_topic_callback(update: Update, context: CallbackContext) -> str:
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    text = "Whats topic of your Presentation?"
    context.user_data[COUNT_SLIDE_CHOICE] = data
    await query.answer()
    await query.edit_message_text(text=text)
    if MESSAGE_ID in context.chat_data:
        del context.chat_data[MESSAGE_ID]
    return INPUT_TOPIC


async def abstract_topic_callback(update: Update, context: CallbackContext) -> str:
    await register_user_if_not_exists(update.callback_query, context, update.callback_query.from_user)
    query = update.callback_query
    data = query.data
    text = "Whats topic of your Abstract?"
    context.user_data[ABSTRACT_TYPE_CHOICE] = data
    await query.answer()
    await query.edit_message_text(text=text)
    if MESSAGE_ID in context.chat_data:
        del context.chat_data[MESSAGE_ID]
    return INPUT_TOPIC


async def auto_generate_presentation(update: Update, context: CallbackContext, user_id, message_id, prompt, template_choice):
    notification_message = await update.message.reply_text("⌛", reply_to_message_id=message_id)
    try:
        response, n_used_tokens = await openai_utils.process_prompt(prompt)
    except OverflowError:
        await notification_message.delete()
        await update.message.reply_text(text="System is currently overloaded. Please try again. 😊",
                                        reply_to_message_id=message_id)
        return END
    except RuntimeError:
        await notification_message.delete()
        await update.message.reply_text(text="Some error happened. Please try again. 😊",
                                        reply_to_message_id=message_id)
        return END
    except ValueError:
        await notification_message.delete()
        await update.message.reply_text(text="Your Presentation is too big. Please try again😊",
                                        reply_to_message_id=message_id)
        return END
    available_tokens = db.get_user_attribute(user_id, "n_available_tokens")
    db.set_user_attribute(user_id, "n_available_tokens", available_tokens - n_used_tokens)
    used_tokens = db.get_user_attribute(user_id, "n_used_tokens")
    db.set_user_attribute(user_id, "n_used_tokens", n_used_tokens + used_tokens)
    pptx_bytes, pptx_title = await presentation.generate_ppt(response, template_choice)
    await update.message.reply_document(document=pptx_bytes, filename=pptx_title)
    await notification_message.delete()


async def presentation_save_input(update: Update, context: CallbackContext):
    if update.edited_message is not None:
        return
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_data = context.user_data
    user_id = update.message.from_user.id
    message_id = update.message.message_id
    topic_choice = update.message.text
    user_mode = db.get_user_attribute(user_id, "current_chat_mode")
    language_choice = user_data[PRESENTATION_LANGUAGE_CHOICE].replace("language_", "")
    template_choice = user_data[TEMPLATE_CHOICE].replace("template_", "")
    type_choice = user_data[PRESENTATION_TYPE_CHOICE].replace("type_", "")
    count_slide_choice = user_data[COUNT_SLIDE_CHOICE].replace("slide_count_", "")
    prompt = await presentation.generate_ppt_prompt(language_choice, type_choice, count_slide_choice, topic_choice)
    if user_mode == "auto":
        available_tokens = db.get_user_attribute(user_id, "n_available_tokens")
        if available_tokens > 0:
            loop = asyncio.get_event_loop()
            loop.create_task(auto_generate_presentation(update, context, user_id, message_id, prompt, template_choice))
        else:
            await update.message.reply_text("You have not enough tokens.")
    else:
        try:
            await update.message.reply_text(text="`" + prompt + "`", parse_mode=ParseMode.MARKDOWN_V2)
        except telegram.error.BadRequest:
            await update.message.reply_text("Check inserted data and input topic again😊")
            return INPUT_TOPIC
        await update.message.reply_text(text="1) Copy previous message with prompt and process it😊"
                                             "\n2) Copy the response of the processed prompt and paste it to the chat😊"
                                             "\n\nRecommended websites:",
                                        reply_markup=InlineKeyboardMarkup([
                                            [InlineKeyboardButton(text='Poe', url='https://poe.com/ChatGPT')],
                                            [InlineKeyboardButton(text='Chat OpenAI', url='https://chat.openai.com/')],
                                        ]))
        return INPUT_PROMPT
    return END


async def auto_generate_abstract(update: Update, context: CallbackContext, user_id, message_id, prompt):
    notification_message = await update.message.reply_text("⌛", reply_to_message_id=message_id)
    try:
        response, n_used_tokens = await openai_utils.process_prompt(prompt)
    except OverflowError:
        await notification_message.delete()
        await update.message.reply_text(text="System is currently overloaded. Please try again😊",
                                        reply_to_message_id=message_id)
        return END
    except RuntimeError:
        await notification_message.delete()
        await update.message.reply_text(text="Some error happened. Please try again😊",
                                        reply_to_message_id=message_id)
        return END
    except ValueError:
        await notification_message.delete()
        await update.message.reply_text(text="Your Abstract is too big. Please try again😊",
                                        reply_to_message_id=message_id)
        return END
    available_tokens = db.get_user_attribute(user_id, "n_available_tokens")
    db.set_user_attribute(user_id, "n_available_tokens", available_tokens - n_used_tokens)
    used_tokens = db.get_user_attribute(user_id, "n_used_tokens")
    db.set_user_attribute(user_id, "n_used_tokens", n_used_tokens + used_tokens)
    docx_bytes, docx_title = await abstract.generate_docx(response)
    await update.message.reply_document(document=docx_bytes, filename=docx_title)
    await notification_message.delete()


async def abstract_save_input(update: Update, context: CallbackContext):
    if update.edited_message is not None:
        return
    await register_user_if_not_exists(update, context, update.message.from_user)
    user_data = context.user_data
    user_id = update.message.from_user.id
    message_id = update.message.message_id
    topic_choice = update.message.text
    user_mode = db.get_user_attribute(user_id, "current_chat_mode")
    language_choice = user_data[ABSTRACT_LANGUAGE_CHOICE].replace("language_", "")
    type_choice = user_data[ABSTRACT_TYPE_CHOICE].replace("type_", "")
    prompt = await abstract.generate_docx_prompt(language_choice, type_choice, topic_choice)
    if user_mode == "auto":
        available_tokens = db.get_user_attribute(user_id, "n_available_tokens")
        if available_tokens > 0:
            loop = asyncio.get_event_loop()
            loop.create_task(auto_generate_abstract(update, context, user_id, message_id, prompt))
        else:
            await update.message.reply_text("You have not enough tokens😊")
    else:
        try:
            await update.message.reply_text(text="`" + prompt + "`", parse_mode=ParseMode.MARKDOWN_V2)
        except telegram.error.BadRequest:
            await update.message.reply_text("Check inserted data and input topic again😊")
            return INPUT_TOPIC
        await update.message.reply_text(text="1) Copy previous message with prompt and process it😊"
                                             "\n2) Copy the response of the processed prompt and paste it to the chat😊"
                                             "\n\nRecommended websites:",
                                        reply_markup=InlineKeyboardMarkup([
                                            [InlineKeyboardButton(text='Poe', url='https://poe.com/ChatGPT')],
                                            [InlineKeyboardButton(text='Chat OpenAI', url='https://chat.openai.com/')],
                                        ]))
        return INPUT_PROMPT
    return END


async def presentation_prompt_callback(update: Update, context: CallbackContext):
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    await register_user_if_not_exists(update, context, update.message.from_user)
    api_response = update.message.text
    user_data = context.user_data
    template_choice = user_data[TEMPLATE_CHOICE].replace("template_", "")
    try:
        pptx_bytes, pptx_title = await presentation.generate_ppt(api_response, template_choice)
        await update.message.reply_document(document=pptx_bytes, filename=pptx_title)
    except IndexError:
        await update.message.reply_text("Check inserted data and try again😊")
        return INPUT_PROMPT
    return END


async def abstract_prompt_callback(update: Update, context: CallbackContext):
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return
    await register_user_if_not_exists(update, context, update.message.from_user)
    api_response = update.message.text
    try:
        docx_bytes, docx_title = await abstract.generate_docx(api_response)
        await update.message.reply_document(document=docx_bytes, filename=docx_title)
    except IndexError:
        await update.message.reply_text("Check inserted data and try again😊")
        return INPUT_PROMPT
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
    chat_id = query.message.chat_id

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
    payload = f"{token_amount}"  # Custom payload to identify the user and token amount
    currency = "USD"
    prices = [LabeledPrice("Purchase", int(float(price) * 100))]
    # Send the invoice to the user
    await context.bot.send_invoice(chat_id=chat_id,
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
    payment_user_id = update.message.from_user.id
    payment_tokens = int(payment.invoice_payload)
    n_available_tokens = db.get_user_attribute(payment_user_id, "n_available_tokens")
    db.set_user_attribute(payment_user_id, "n_available_tokens", n_available_tokens + payment_tokens)
    db.set_user_attribute(payment_user_id, "last_invoice_payload", payment.invoice_payload)
    try:
        await update.message.reply_text("😊Thank you for your payment!")
    except telegram.error.Forbidden:
        pass


async def edited_message_handle(update: Update, context: CallbackContext):
    text = "🥲 Unfortunately, message <b>editing</b> is not supported"
    await update.edited_message.reply_text(text, parse_mode=ParseMode.HTML)


async def error_handle(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    # send error to the chat for test
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
    except Exception:
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

    application.add_handler(MessageHandler(filters.COMMAND & user_filter, message_handle), group=2)

    application.add_handler(CommandHandler("mode", show_chat_modes_handle, filters=user_filter))
    application.add_handler(CallbackQueryHandler(set_chat_mode_handle, pattern="^set_chat_mode"))

    presentation_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(presentation_language_callback, pattern=f"^{PRESENTATION}$")],
        states={
            SELECTING_MENU: [
                CallbackQueryHandler(presentation_language_callback, pattern="^page_language_"),
                CallbackQueryHandler(presentation_template_callback, pattern="^language_"),
                CallbackQueryHandler(presentation_template_callback, pattern="^page_template_"),
                CallbackQueryHandler(presentation_type_callback, pattern="^template_"),
                CallbackQueryHandler(presentation_type_callback, pattern="^page_type_"),
                CallbackQueryHandler(presentation_slide_count_callback, pattern="^type_"),
                CallbackQueryHandler(presentation_slide_count_callback, pattern="^page_slide_count_"),
                CallbackQueryHandler(presentation_topic_callback, pattern="^slide_count_"),
                             ],
            INPUT_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, presentation_save_input)],
            INPUT_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, presentation_prompt_callback)],
        },
        fallbacks=[
            CallbackQueryHandler(end_second_level, pattern=f"^{str(END)}$"),
            CommandHandler("menu", menu_handle, filters=user_filter)
        ],
        map_to_parent={
            END: SELECTING_ACTION,
            SELECTING_ACTION: SELECTING_ACTION,
        },
        allow_reentry=True,
    )

    abstract_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(abstract_language_callback, pattern=f"^{ABSTRACT}$")],
        states={
            SELECTING_MENU: [
                CallbackQueryHandler(abstract_language_callback, pattern="^page_language_"),
                CallbackQueryHandler(abstract_type_callback, pattern="^language_"),
                CallbackQueryHandler(abstract_type_callback, pattern="^page_type_"),
                CallbackQueryHandler(abstract_topic_callback, pattern="^type_")
                             ],
            INPUT_TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, abstract_save_input)],
            INPUT_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, abstract_prompt_callback)],
        },
        fallbacks=[
            CallbackQueryHandler(end_second_level, pattern=f"^{str(END)}$"),
            CommandHandler("menu", menu_handle, filters=user_filter)
        ],
        map_to_parent={
            END: SELECTING_ACTION,
            SELECTING_ACTION: SELECTING_ACTION,
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
    application.add_handler(menu_conv_handler)

    application.add_handler(CommandHandler("balance", show_balance_handle, filters=user_filter))
    application.add_handler(CallbackQueryHandler(buy_tokens_callback, pattern="^buy_tokens_"))
    application.add_handler(PreCheckoutQueryHandler(pre_checkout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handle))

    application.add_error_handler(error_handle)

    application.run_polling()


if __name__ == "__main__":
    run_bot()
