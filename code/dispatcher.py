import tglogging as logging

import requests
from urllib.parse import urlparse
import os
import configparser
from telegram import Bot
from telegram.ext import Application, MessageHandler, filters, CommandHandler
import openai
import re
from bs4 import BeautifulSoup

config = configparser.SafeConfigParser(os.environ)
config_path = os.path.dirname(__file__) + '/../config/' #we need this trick to get path to config folder
config.read(config_path + 'settings.ini')

logger = logging.get_logger()

logger.info('Starting ' + __file__ + ' in ' + config['BOT']['MODE'] + ' mode at ' + str(os.uname()))

bot = Bot(config['BOT']['KEY'])

def helper_get_url_content(text):
    # Check if the input text is a valid URL
    try:
        result = urlparse(text)
        if all([result.scheme, result.netloc]):
            # If it is a valid URL, retrieve the content from the URL
            response = requests.get(text)
            if response.status_code == 200:
                # If the request is successful, let's clean it with BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.title.get_text(separator=" ", strip=True) if soup.title else None
                body = soup.body.get_text(separator=" ", strip=True) if soup.body else None

                return title, body
            else:
                # If the request is not successful, raise an exception
                raise Exception(f"Request to {text} failed with status code {response.status_code}")
        else:
            # If it is not a valid URL, return None
            return None, None
    except ValueError:
        # If there is an error parsing the URL, return None
        return None, None

def helper_answer_question_for_summary_from_url(question, url):
    url_content_title, url_content_body = helper_get_url_content(url)

    # check if url is valid
    if url_content_body is not None:
        # get openai summary from url_content
        openai.api_key = config['OPENAI']['KEY']

        # split content into chunks of 2000 chars and loop through them
        url_content_chunks = [url_content_body[i:i + 2000] for i in range(0, len(url_content_body), 2000)]

        answers_chunks = []

        for i, url_content_chunk in enumerate(url_content_chunks):
            chunk_messages = [
                {"role": "system",
                 "content": f"Answer users question for this chunk."},
                {"role": "user",
                 "content": f"Page title: {url_content_title}"},
                {"role": "user",
                 "content": f"Page content chunk {i}:  {url_content_chunk}"}
            ]

            response = openai.ChatCompletion.create(
                model=config['OPENAI']['COMPLETION_MODEL'],
                messages=chunk_messages,
                temperature=float(config['OPENAI']['TEMPERATURE']),
                max_tokens=int(config['OPENAI']['MAX_TOKENS']),
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
            )
            if response['choices'][0]['message']['content'] is not None:
                answers_chunks.append(response['choices'][0]['message']['content'])
        messages = [
            {"role": "system",
             "content": f"Answer users question based on answers chunks from previous OpenAI calls."},
            {"role": "user",
             "content": f"Page title: {url_content_title}"}
        ]
        # now let's run through the summary chunks and get a summary of the summaries
        for j, summary_chunk in enumerate(answers_chunks):
            messages.append({"role": "user",
                             "content": f"Answer chunk {j}:  {answers_chunks}"})

        response = openai.ChatCompletion.create(
            model=config['OPENAI']['COMPLETION_MODEL'],
            messages=messages,
            temperature=float(config['OPENAI']['TEMPERATURE']),
            max_tokens=int(config['OPENAI']['MAX_TOKENS']),
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
        answer_of_answers = response['choices'][0]['message']['content']

        return answer_of_answers
    else:
        None

def helper_get_summary_from_url(url):
    url_content_title, url_content_body = helper_get_url_content(url)
    # check if url is valid
    if url_content_body is not None:
        helper_get_summary_from_text(url_content_body)
    else:
        return None

def helper_get_answer_from_prompt(prompt):
    try:
        openai.api_key = config['OPENAI']['KEY']

        messages = [
            {"role": "system",
             "content": f"Act as a chatbot assistant and answer users question."}, #TODO:LOW: may be we need to rewrite this prompt
            {"role": "user",
             "content": f"{prompt}"}
        ]

        response = openai.ChatCompletion.create(
            model=config['OPENAI']['COMPLETION_MODEL'],
            messages=messages,
            temperature=float(config['OPENAI']['TEMPERATURE']),
            max_tokens=int(config['OPENAI']['MAX_TOKENS']),
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
        if response['choices'][0]['message']['content'] is not None:
            return response['choices'][0]['message']['content']
        else:
            return None
    except Exception as e:
        logger.error(e)
        return None


def helper_get_summary_from_text(content_body, content_title = None, ):
    #TODO:HIGH: seems like we need to move this helpers to a separate openai file
    # get openai summary from url_content
    openai.api_key = config['OPENAI']['KEY']

    # split content into chunks of 2000 chars and loop through them
    content_chunks = [content_body[i:i + 2000] for i in range(0, len(content_body), 2000)]

    summary_chunks = []

    for i, content_chunk in enumerate(content_chunks):
        chunk_messages = [
            {"role": "system",
             "content": f"Give me a takeaway summary for this text in the original language."},
            {"role": "user",
             "content": f"Title: {content_title}"},
            {"role": "user",
             "content": f"Content {i}:  {content_chunk}"}
        ]

        response = openai.ChatCompletion.create(
            model=config['OPENAI']['COMPLETION_MODEL'],
            messages=chunk_messages,
            temperature=float(config['OPENAI']['TEMPERATURE']),
            max_tokens=int(config['OPENAI']['MAX_TOKENS']),
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
        )
        if response['choices'][0]['message']['content'] is not None:
            summary_chunks.append(response['choices'][0]['message']['content'])

        #TODO:LOW: it's a good idea to edit previous message adding a dot at each iteration for Generating summary...
        print(f"Generating summary... {i}")

    messages = [
        {"role": "system",
         "content": f"Give me a takeaway summary in the original language based on title and texts."},
        {"role": "user",
         "content": f"Title: {content_title}"}
    ]
    # now let's run through the summary chunks and get a summary of the summaries
    for j, summary_chunk in enumerate(summary_chunks):
        messages.append({"role": "user",
                         "content": f"Content {j}:  {summary_chunk}"})
    messages.append({"role": "user",
                     "content": f"Summary:"})

    response = openai.ChatCompletion.create(
        model=config['OPENAI']['COMPLETION_MODEL'],
        messages=messages,
        temperature=float(config['OPENAI']['TEMPERATURE']),
        max_tokens=int(config['OPENAI']['MAX_TOKENS']),
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
    )
    summary_of_summaries = response['choices'][0]['message']['content']

    return summary_of_summaries

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

        answer = helper_get_answer_from_prompt(command_args)
        if answer is not None:
            await bot.send_message(update.message.chat.id, answer, reply_to_message_id=update.message.message_id)
        else:
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
            url_content_title, url_content_body = helper_get_url_content(url_or_text)

            #check if it's a url or a text
            if url_content_body is not None: #so that was a valid url
                summary = helper_get_summary_from_text(url_content_body, url_content_title)
            else: #so that was a text
                #FIXME: we can get url_content_body = None even for valid url. So this else is not 100% correct
                summary = helper_get_summary_from_text(url_or_text)

            await bot.send_message(update.message.chat.id, summary, reply_to_message_id=update.message.message_id)

    except Exception as e:
        logger.error(f"Error in {__file__}: {e}")

async def tg_start_dispatcher(update, context, command_args):
    try:
        if update.message is not None:
            # TODO: think how could we compile this message automatically from the list of supported commands
            logger.info(f"tg_start_dispatcher request {update.message.chat.first_name} {update.message.chat.last_name} @{update.message.chat.username} ({update.message.chat.id}): {update.message.text}")
            welcome_message = (f"Hi {update.message.chat.first_name} {update.message.chat.last_name}!\n"
            "I'm an AI Personal Aisstant.\n\n"
            "<b>List of supported commands:</b>\n"
            "/summary or /s - get summary of a text or a webpage\n"
            "/prompt or /p - get GPT prompt answe\n"
            "/start - get welcome message with available commands\n\n"
            "I'm still in development, so I'm not very smart yet. But I'm learning every day."
            "You can find my source code here: <a href=\"https://github.com/rvnikita/Personal_Assistant_AI_Bot\">https://github.com/rvnikita/Personal_Assistant_AI_Bot</a>")

            await bot.send_message(update.message.chat.id, welcome_message, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in {__file__}: {e}")

#we will use this function to separate command and it's parameters and send to the proper function
async def tg_dispatcher(update, context):
    try:
        if update.message is not None:
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

def main() -> None:
    try:
        application = Application.builder().token(config['BOT']['KEY']).build()

        #for now only work with commands
        application.add_handler(MessageHandler(filters=filters.ALL & filters.COMMAND, callback=tg_dispatcher), group=0)

        #TODO:LOW: add handler for replys to messages, so we can get questions from users on our summary and answer them
        #TODO:LOW: We can add default behaviour to show available commands if user sends a message that is not a command, but we should not send it in chats, otherwise we will be triggered everytime

        # Start the Bot
        application.run_polling()
    except Exception as error:
        logger.info(f"Error in file {__file__}: {error}")

if __name__ == '__main__':
    main()

