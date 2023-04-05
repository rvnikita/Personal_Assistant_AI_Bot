import src.tglogging as logging
import src.openai_helper as openai_helper
import src.db_helper as db_helper

import os
import configparser
from telegram import Bot
from telegram.ext import Application, MessageHandler, filters, CommandHandler
from telegram.request import HTTPXRequest
import re
import datetime


#TODO:HIGH: move env variables to .env file
#TODO:HIGH: we need to move all this to a separate file
config = configparser.ConfigParser(os.environ)
config_path = os.path.dirname(__file__) + '/../config/' #we need this trick to get path to config folder
config.read(config_path + 'settings.ini')

logger = logging.get_logger()
logger.info('Starting ' + __file__ + ' in ' + config['BOT']['MODE'] + ' mode at ' + str(os.uname()))

bot = Bot(config['BOT']['KEY'],
          request=HTTPXRequest(http_version="1.1"), #we need this to fix bug https://github.com/python-telegram-bot/python-telegram-bot/issues/3556
          get_updates_request=HTTPXRequest(http_version="1.1")) #we need this to fix bug https://github.com/python-telegram-bot/python-telegram-bot/issues/3556


async def tg_prompt_dispatcher(update, context, command_args):
    try:
        #TODO:MED: support previous conversation history
        if update.message is not None:
            logger.info(f"tg_prompt_dispatcher request {update.message.chat.first_name} {update.message.chat.last_name} @{update.message.chat.username} ({update.message.chat.id}): {update.message.text}")

        if re.match(r"^[\s\t]*$", command_args):
            #TODO:HIGH: Seems like we need to write a fucntion that will wrap answers to the user so we can log inside it for cleaner code
            logger.info("You need to provide a prompt after /prompt command")
            await bot.send_message(update.message.chat.id,
                                   "You need to provide a prompt after /prompt command")
            return

        await bot.send_message(update.message.chat.id, "Generating answer...",  reply_to_message_id=update.message.message_id)

        answer = openai_helper.helper_get_answer_from_prompt(command_args)
        if answer is not None:
            logger.info(f"tg_prompt_dispatcher answer {answer}")
            await bot.send_message(update.message.chat.id, answer, reply_to_message_id=update.message.message_id)
        else:
            logger.info(f"tg_prompt_dispatcher answer \"Sorry, I can't answer that.\"")
            await bot.send_message(update.message.chat.id, "Sorry, I can't answer that.", reply_to_message_id=update.message.message_id)

        return



    except Exception as e:
        logger.error(f"tg_prompt_dispatcher error {e}")

async def tg_summary_dispatcher(update, context, command_args):
    #TODO:HIGH: we need tests for this funciton
    try:
        if update.message is not None:
            logger.info(f"tg_summary_dispatcher request {update.message.chat.first_name} {update.message.chat.last_name} @{update.message.chat.username} ({update.message.chat.id}): {update.message.text}")
            #check if it is a reply to a message or a forwarded message
            if update.message.reply_to_message is not None:
                #TODO: maybe here we should check if an url exists even inside the reply_to_message.text together with text
                url_or_text = update.message.reply_to_message.text
            elif update.message.forward_from is not None:
                #TODO because forward message and text attached to it comming as two different messages I  don't know how to handle it for now
                url_or_text = update.message.forward_from.text
            #TODO: check if we can also see forwarded messages here
            else:
                url_or_text = command_args

                # check if it's a url_or_text is empty (only spaces,tabs or nothing)
                if re.match(r"^[\s\t]*$", url_or_text):
                    await bot.send_message(update.message.chat.id, "You need to provide an url or text after /summary, or reply to a message with /summary command to get summary")
                    return

            if url_or_text is None:
                await bot.send_message(update.message.chat.id, "You need to reply to a message or forward a message with an url or just send a text tp get summary")
                return

            await bot.send_message(update.message.chat.id, "Generating summary... \n(can take 2-3 minutes for big pages)", reply_to_message_id=update.message.message_id)
            await bot.send_chat_action(update.message.chat.id, 'typing')

            url_content_title, url_content_body = openai_helper.helper_get_url_content(url_or_text)

            #check if it's a url or a text
            if url_content_body is not None: #so that was a valid url
                summary = openai_helper.helper_get_summary_from_text(url_content_body, url_content_title)
            else: #so that was a text
                #FIXME: we can get url_content_body = None even for valid url. So this else is not 100% correct
                summary = openai_helper.helper_get_summary_from_text(url_or_text)

            logger.info(f"tg_summary_dispatcher response: {summary}")
            await bot.send_message(update.message.chat.id, summary, reply_to_message_id=update.message.message_id)

    except Exception as e:
        logger.error(f"Error in {__file__}: {e}")

async def tg_start_dispatcher(update, context, command_args):
    try:
        if update.message is not None:
            # TODO: think how could we compile this message automatically from the list of supported commands
            logger.info(f"tg_start_dispatcher request {update.message.chat.first_name} {update.message.chat.last_name} @{update.message.chat.username} ({update.message.chat.id}): {update.message.text}")
            welcome_message = (f"Hi {update.message.chat.first_name} {update.message.chat.last_name}!\n"
            "Привет, боте переехал по адресу @rvnikita_public\n\n"
            "Адрес блога автора этого бота @rvnikita_blog")

            logger.info(f"tg_start_dispatcher response: {welcome_message}")
            await bot.send_message(update.message.chat.id, welcome_message, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in {__file__}: {e}")

#we will use this function to separate command and it's parameters and send to the proper function
async def tg_dispatcher(update, context):
    try:
        with db_helper.session_scope() as session:
            if update.message is not None:
                user = session.query(db_helper.User).filter_by(id=update.message.chat.id).first()

                if not user:
                    # If the user is not in the database, add them
                    user = db_helper.User(
                        id=update.message.chat.id,
                        username=update.message.chat.username,
                        first_name=update.message.chat.first_name,
                        last_name=update.message.chat.last_name,
                        status='active',
                        last_message_datetime=datetime.datetime.now(),
                        requests_counter=0
                    )
                    session.add(user)
                else:
                    if user.requests_counter is None:
                        user.requests_counter = 0

                if user.blacklisted is True:
                    return

                await bot.send_chat_action(update.message.chat.id, 'typing')

                user.requests_counter += 1
                user.last_message_datetime = datetime.datetime.now()

                session.commit()

                #TODO:MED: this is not working if it is a chat, not a DM
                logger.info(f"tg_dispatcher request {update.message.chat.first_name} {update.message.chat.last_name} @{update.message.chat.username} ({update.message.chat.id}): {update.message.text}")

                command = None
                match = re.match(r"^\/(\w+)\s*([\s\S]*)$", update.message.text, re.DOTALL)
                if match:
                    command = match.group(1)
                    command_args = match.group(2)
                else:
                    #await bot.send_message(update.message.chat.id, f"Unknown command")
                    #doing nothing
                    return

                if command == "summary" or command == "s":
                    await tg_summary_dispatcher(update, context, command_args)
                elif command == "start":
                    await tg_start_dispatcher(update, context, command_args)
                elif command == "prompt" or command == "p":
                    await tg_prompt_dispatcher(update, context, command_args)
                # Add more command handlers here as elif statements
                else:
                    await bot.send_message(update.message.chat.id, f"Unknown command: {command}")

    except Exception as e:
        logger.error(f"Error in {__file__}: {e}")

async def tg_error_handler(update, context):
    try:
        logger.error(f"tg_error_handler: {context.error}")
        if update.message is not None:
            await bot.send_message(update.message.chat.id, f"Error: {context.error}")
    except Exception as e:
        logger.error(f"Error in {__file__}: {e}")

def main() -> None:
    try:
        application = Application.builder().token(config['BOT']['KEY']).build()

        #for now only work with commands
        application.add_handler(MessageHandler(filters=filters.ALL & filters.COMMAND, callback=tg_dispatcher), group=0)

        #error handler
        application.add_error_handler(tg_error_handler)

        #TODO:LOW: add handler for replys to messages, so we can get questions from users on our summary and answer them
        #TODO:LOW: We can add default behaviour to show available commands if user sends a message that is not a command, but we should not send it in chats, otherwise we will be triggered everytime

        # Start the Bot
        application.run_polling()
    except Exception as error:
        logger.info(f"Error in file {__file__}: {error}")

if __name__ == '__main__':
    main()

