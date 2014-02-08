from .bot import Bot

def main():
    from tornado.options import define, options, parse_command_line

    define("config", default="config.yml", help="Configuration file")

    parse_command_line()

    bot = Bot(options.config)
    bot.run()
