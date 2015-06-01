import time
import threading

def config():
    from kochira import config
    timeout_messages = config.Field(doc="Timeout: number of messages allowed per timeframe.", default=3)
    timeout_seconds = config.Field(doc="Timeout: Timeframe in seconds.", default=60)
    timeout_global = config.Field(doc="Timeout: Affect globally to all users.", default=False)
    return timeout_messages, timeout_seconds, timeout_global

def setup(ctx):
    ctx.storage.lasttimes = {}
    ctx.storage.points = {}
    ctx.storage.lock = threading.Lock()

def bump(ctx, hostmask):
    # TODO: act from @ onwards so you can't change nick to avoid timeout
    now = time.time()
    lasttimes = ctx.storage.lasttimes
    allpoints = ctx.storage.points
    if ctx.config.get('timeout_global', False):
        hostmask = '(global timeout)'
    one = max(0, ctx.config.get('timeout_messages', 3))
    two = max(1, ctx.config.get('timeout_seconds', 60))

    then = lasttimes.get(hostmask, now)
    points = allpoints.get(hostmask, one)

    passed = now - then

    good = points >= 1
    points -= 1
    points += passed*one/two
    points = min(max(points, 0), one)

    allpoints[hostmask] = points
    lasttimes[hostmask] = now

    return good

def handle(ctx, origin):
    hostmask = ctx.client.users[origin].hostmask
    with ctx.storage.lock:
        return bump(ctx, hostmask)
