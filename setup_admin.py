from kochira import Bot
from kochira.services.core.admin import grant_permission

bot = Bot()

print("Enter a network and hostmask to grant full administrator permissions to.")

network = None
while not network:
    network = input("Network (one of {}): ".format(", ".join(bot.config.networks)))

hostmask = None
while not hostmask:
    hostmask = input("Hostmask: ")

grant_permission(network, hostmask, "admin")
