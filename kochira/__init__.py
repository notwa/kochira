from .bot import Bot

def main():
    import os
    import logging
    from tornado.options import define, options, parse_command_line

    define("config", default="config.yml", help="Configuration file.")
    define("console", default=False, help="Whether to start the console instead of the bot.")

    parse_command_line()

    if not os.path.exists(options.config):
        logging.error("""\
Could not find the configuration file: %s

If this is your first time starting Kochira, copy the file `config.yml.dist` to
`config.yml` and edit it appropriately.
""", options.config)
        return

    bot = Bot(options.config)
    if options.console:
        banner = """\
Welcome to the Kochira console!

Variables:
bot     -> current bot
"""
        my_locals = {"bot": bot}
        try:
            import IPython
        except ImportError:
            import code
            code.interact(banner, local=my_locals)
        else:
            IPython.embed(banner1=banner, user_ns=my_locals)

    else:
        bot.run()
