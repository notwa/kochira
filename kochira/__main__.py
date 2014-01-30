from . import Bot
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = Bot()
    bot.run()
