import time
import threading

def config(Field, messages=3, seconds=60, globally=False):
    timeout_messages = Field(doc=\
      "Timeout: number of messages allowed per timeframe.", default=messages)
    timeout_seconds = Field(doc=\
      "Timeout: timeframe in seconds.", default=seconds)
    timeout_global = Field(doc=\
      "Timeout: affect globally to all users.", default=globally)
    return timeout_messages, timeout_seconds, timeout_global

def setup(ctx):
    ctx.storage.lasttimes = {}
    ctx.storage.points = {}
    ctx.storage.lock = threading.Lock()

def bump(ctx, hostname):
    lasttimes = ctx.storage.lasttimes
    allpoints = ctx.storage.points
    tomsgs = max(0, ctx.config.get('timeout_messages', 3))
    tosecs = max(1, ctx.config.get('timeout_seconds', 60))

    now = time.time()
    then = lasttimes.get(hostname, now)
    points = allpoints.get(hostname, tomsgs)
    passed = now - then

    good = points >= 1
    points -= 1
    points += passed*tomsgs/tosecs
    points = min(max(points, 0), tomsgs)

    allpoints[hostname] = points
    lasttimes[hostname] = now

    return good

def handle(ctx, origin=None):
    if ctx.config.get('timeout_global') == None:
        print("kochira.timeout: something went wrong")
    if ctx.config.get('timeout_global', False):
        hostname = '(global timeout)'
    elif origin != None:
        hostname = ctx.client.users[origin].hostname
    else:
        # this is awful lol
        hostname = '(MISSING ORIGIN)'
        print('kochira.timeout:', hostname)
    with ctx.storage.lock:
        return bump(ctx, hostname)
