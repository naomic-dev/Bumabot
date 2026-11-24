"""Entry point for Bumabot."""

import ChatBot
from logging_config import configure_logging


def main() -> None:
    """Create the bot and start the chat loop."""
    configure_logging()
    chat_bot = ChatBot.ChatBot()
    chat_bot.monitor_chat()


if __name__ == "__main__":
    main()
