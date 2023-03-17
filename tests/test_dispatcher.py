import pytest
import code
import asyncio
from unittest.mock import MagicMock
from unittest.mock import AsyncMock
from unittest.mock import patch

# Import the function from your code
from src.dispatcher import tg_start_dispatcher

# Mock the bot object to avoid sending actual messages during the test
class MockBot:
    async def send_message(self, chat_id, text, parse_mode, disable_web_page_preview):
        pass

bot = MockBot()

# Mock the logger object to avoid logging during the test
class MockLogger:
    def info(self, message):
        pass

    def error(self, message):
        pass

@pytest.mark.asyncio
@patch('src.dispatcher.bot', bot)
@patch('src.dispatcher.logger', MockLogger())
# @patch('src.dispatcher.Bot.send_message', new_callable=AsyncMock)
async def test_tg_start_dispatcher():
    # Create mock update and context objects
    update = MagicMock()
    update.message.chat.first_name = "John"
    update.message.chat.last_name = "Doe"
    update.message.chat.username = "johndoe"
    update.message.chat.id = 12345
    update.message.text = "/start"

    context = MagicMock()

    # Replace the original bot and logger objects with mock objects

    # global logger
    # logger = MockLogger()

    # Call the tg_start_dispatcher function with the mock update and context objects
    await tg_start_dispatcher(update, context, [])

    # Check if the result contains the expected welcome message
    expected_welcome_message = (
        f"Hi John Doe!\n"
        "I'm an AI Personal Aisstant.\n\n"
        "<b>List of supported commands:</b>\n"
        "/summary or /s - get summary of a text or a webpage\n"
        "/prompt or /p - get GPT prompt answe\n"
        "/start - get welcome message with available commands\n\n"
        "I'm still in development, so I'm not very smart yet. But I'm learning every day."
        "You can find my source code here: <a href=\"https://github.com/rvnikita/Personal_Assistant_AI_Bot\">https://github.com/rvnikita/Personal_Assistant_AI_Bot</a>"
    )

    # assert mock_send_message.called_once_with(
    #     12345,
    #     expected_welcome_message,
    #     parse_mode="HTML",
    #     disable_web_page_preview=True
    # )