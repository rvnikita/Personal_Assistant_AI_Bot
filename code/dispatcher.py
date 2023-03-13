from admin_log import admin_log

import requests
from urllib.parse import urlparse
import os
import configparser
from telegram import Bot
from telegram.ext import Application, MessageHandler, filters, CommandHandler
import openai
from bs4 import BeautifulSoup

config = configparser.ConfigParser()
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

def helper_get_summary_from_url(url):
    url_content_title, url_content_body = helper_get_url_content(url)
    # check if url is valid
    if url_content_body is not None:
        # get openai summary from url_content
        openai.api_key = config['OPENAI']['KEY']

        # split content into chunks of 2000 chars and loop through them
        url_content_chunks = [url_content_body[i:i + 2000] for i in range(0, len(url_content_body), 2000)]

        summary_chunks = []

        for i, url_content_chunk in enumerate(url_content_chunks):
            chunk_messages = [
                {"role": "system",
                 "content": f"Give me a takeaway summary for this website chunk"},
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
                summary_chunks.append(response['choices'][0]['message']['content'])

        messages = [
            {"role": "system",
             "content": f"Give me a takeaway summary for website base on summary chunks from previous OpenAI calls."},
            {"role": "user",
             "content": f"Page title: {url_content_title}"}
        ]
        #now let's run through the summary chunks and get a summary of the summaries
        for j, summary_chunk in enumerate(summary_chunks):
            messages.append({"role": "user",
                             "content": f"Page summary chunk {j}:  {summary_chunk}"})

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
    else:
        return None

async def tg_private_dispatcher(update, context):
    if update.message is not None:
        url = update.message.text

        await bot.send_message(update.message.chat.id, "Generating summary...")
        summary_from_url = helper_get_summary_from_url(url)

        if summary_from_url is not None:
            await bot.send_message(update.message.chat.id, summary_from_url)
        else:
            await bot.send_message(update.message.chat.id, "This is not a valid URL.")

async def tg_summary_dispatcher(update, context):
    if update.message is not None:
        #cut command from the message and get string starting from non space char
        url = update.message.text[update.message.text.find(' ')+1:]

        await bot.send_message(update.message.chat.id, "Generating summary...")
        summary_from_url = helper_get_summary_from_url(url)

        if summary_from_url is not None:
            await bot.send_message(update.message.chat.id, summary_from_url)
        else:
            await bot.send_message(update.message.chat.id, "This is not a valid URL.")


def main() -> None:
    try:
        application = Application.builder().token(config['BOT']['KEY']).build()

        #handler for incoming DM
        application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, tg_private_dispatcher), group=0)

        #handler for supergroup and group
        application.add_handler(CommandHandler('summary', tg_summary_dispatcher), group=1)

        #TODO: add handler for replys to messages, so we can get questions from users on our summary and answer them

        # Start the Bot
        application.run_polling()
    except Exception as error:
        admin_log(f"Error in file {__file__}: {error}")

if __name__ == '__main__':
    main()

