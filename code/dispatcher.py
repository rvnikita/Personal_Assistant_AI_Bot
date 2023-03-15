from admin_log import admin_log

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

admin_log(f"Starting {__file__} in {config['BOT']['MODE']} mode at {os.uname()}")

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
                body = soup.body.get_text(separator=" ", strip=True)

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

def helper_get_summary_from_text(content_body, content_title = None, ):
    # get openai summary from url_content
    openai.api_key = config['OPENAI']['KEY']

    # split content into chunks of 2000 chars and loop through them
    content_chunks = [content_body[i:i + 2000] for i in range(0, len(content_body), 2000)]

    summary_chunks = []

    for i, content_chunk in enumerate(content_chunks):
        chunk_messages = [
            {"role": "system",
             "content": f"Give me a takeaway summary for this text"},
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

        #TODO: it's a good idea to edit previous message adding a dot at each iteration for Generating summary...
        print(f"Generating summary... {i}")

    messages = [
        {"role": "system",
         "content": f"Give me a takeaway summary based on title and texts."},
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


async def tg_summary_dispatcher(update, context, command_args):
    #TODO we need tests for this funciton
    try:
        if update.message is not None:
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
                summary = helper_get_summary_from_text(url_or_text)

            await bot.send_message(update.message.chat.id, summary, reply_to_message_id=update.message.message_id)

    except Exception as e:
        admin_log(f"Error in {__file__}: {e}")
        await bot.send_message(update.message.chat.id, f"Something went wrong. Error: {e}")

#we will use this function to separate command and it's parameters and send to the proper function
async def tg_dispatcher(update, context):
    try:
        if update.message is not None:
            command = None
            match = re.match(r"^\/(\w+)\s*(.*)$", update.message.text)
            if match:
                command = match.group(1)
                command_args = match.group(2)
            else:
                await bot.send_message(update.message.chat.id, f"Unknown command")
                return

            if command == "summary":
                await tg_summary_dispatcher(update, context, command_args)
            # Add more command handlers here as elif statements
            else:
                await bot.send_message(update.message.chat.id, f"Unknown command: {command}")

    except Exception as e:
        admin_log(f"Error in {__file__}: {e}")
        await bot.send_message(update.message.chat.id, f"Something went wrong. Error: {e}")


def main() -> None:
    try:
        application = Application.builder().token(config['BOT']['KEY']).build()

        #summary command handler
        application.add_handler(MessageHandler(filters=filters.ALL, callback=tg_dispatcher), group=0)

        #TODO (!) rewrite everything to separate command and it's parameters and then coll needed functions

        #TODO: add handler for replys to messages, so we can get questions from users on our summary and answer them

        #TODO: We can add default behaviour to show available commands if user sends a message that is not a command

        #TODO: we should add logging to admin for debugging purposes of all requests and add "mode" PROD and DEV to config

        # Start the Bot
        application.run_polling()
    except Exception as error:
        admin_log(f"Error in file {__file__}: {error}")

if __name__ == '__main__':
    main()

