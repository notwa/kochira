from .bot import Bot

def main():
    import os
    import logging
    from tornado.options import define, options, parse_command_line

    define("config", default="config.yml", help="Configuration file")

    parse_command_line()

    if not os.path.exists(options.config):
        logging.error("""\
Could not find the configuration file: %s

If this is your first time starting Kochira, copy the file `config.yml.dist` to
`config.yml` and edit it appropriately.
""", options.config)
        return

    bot = Bot(options.config)
    bot.run()
