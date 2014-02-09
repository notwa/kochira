from kochira import Bot
from kochira.auth import ACLEntry

bot = Bot()

print("Enter a network and hostmask to grant full administrator permissions to.")

network = None
while not network:
    network = input("Network (one of {}): ".format(", ".join(bot.config.networks)))

hostmask = None
while not hostmask:
    hostmask = input("Hostmask: ")

ACLEntry.grant(network, hostmask, "admin")
