import pytest
import code
import asyncio
from unittest.mock import MagicMock
from unittest.mock import AsyncMock
from unittest.mock import patch

# START OF MOCKING
pytestmark = pytest.mark.asyncio

# Mock the bot object to avoid sending actual messages during the test
bot = MagicMock()
patch('src.dispatcher.bot', bot)

def mock_get_logger():
    return MagicMock()

def mock_configparser(environ):
    return MagicMock()

with patch('src.tglogging.get_logger', mock_get_logger), patch('src.tglogging.configparser.SafeConfigParser', mock_configparser):
    # from src.dispatcher import tg_start_dispatcher
    import src.dispatcher
# END OF MOCKING

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

    # Call the tg_start_dispatcher function with the mock update and context objects
    await src.dispatcher.tg_start_dispatcher(update, context, [])

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

#just a random comment to test autolaunch tests