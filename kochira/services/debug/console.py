"""
Interactive Python console.

Run Python code through IRC messages.
"""

import code
import sys

from io import StringIO

from kochira.auth import requires_permission
from kochira.service import Service

service = Service(__name__, __doc__)


@service.setup
def setup_console(bot):
    storage = service.storage_for(bot)
    storage.console = code.InteractiveConsole({"bot": bot})


@service.command(r">>>(?: (?P<code>.+))?", priority=3000)
@requires_permission("admin")
def eval_code(client, target, origin, code):
    """
    Evaluate code.

    Evaluate code inside the bot. The local ``bot`` is provided for access to
    bot internals.
    """

    code = code or ""

    storage = service.storage_for(client.bot)

    stdout = StringIO()
    stderr = StringIO()

    sys.stdout = stdout
    sys.stderr = stderr

    err = None

    try:
        r = storage.console.push(code)
    except BaseException as e:
        err = "{}: {}".format(e.__class__.__qualname__, e)
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    out = stdout.getvalue().rstrip("\n")

    if err is None:
        err = stderr.getvalue().rstrip("\n")

    if out:
        for line in out.split("\n"):
            client.message(target, "<<< {}".format(line))
    elif err:
        client.message(target, "<<! {}".format(err.split("\n")[-1]))
    elif not r:
        client.message(target, "(no result)")
