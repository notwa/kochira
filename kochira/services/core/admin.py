"""
Administration and bot management.

This service allows administrators to manage various aspects of the bot.
"""

import os
import signal
import subprocess
import sys

from kochira.auth import requires_permission
from kochira.service import Service

service = Service(__name__, __doc__)


@service.command(r"(?P<r>re)?load service (?P<service_name>\S+)$", mention=True, priority=3000)
@requires_permission("admin")
def load_service(ctx, r, service_name):
    """
    Load service.

    Load or reload a service with the given name. Reloading will force all code to
    be reloaded.
    """

    try:
        ctx.bot.load_service(service_name, r is not None)
    except Exception as e:
        ctx.respond(ctx._("Sorry, couldn't load the service \"{name}\".").format(
            name=service_name
        ))
        ctx.respond("↳ {name}: {info}".format(
            name=e.__class__.__name__,
            info=str(e)
        ))
        return

    if r is not None:
        message = "Reloaded service \"{name}\".".format(name=service_name)
    else:
        message = "Loaded service \"{name}\".".format(name=service_name)

    ctx.respond(message)


@service.command(r"unload service (?P<service_name>\S+)$", mention=True, priority=3000)
@requires_permission("admin")
def unload_service(ctx, service_name):
    """
    Unload service.

    Unload a currently running service.
    """

    try:
        ctx.bot.unload_service(service_name)
    except Exception as e:
        ctx.respond(ctx._("Sorry, couldn't unload the service \"{name}\".").format(
            name=service_name
        ))
        ctx.respond("↳ {name}: {info}".format(
            name=e.__class__.__name__,
            info=str(e)
        ))
        return

    ctx.respond(ctx._("Unloaded service \"{name}\".").format(name=service_name))


@service.command(r"what services are(?: you)? running\??$", mention=True, priority=3000)
@service.command(r"(?:list )?services$", mention=True, priority=3000)
@requires_permission("admin")
def list_services(ctx):
    """
    List services.

    List all running services.
    """

    ctx.respond(ctx._("I am running: {services}").format(
        services=", ".join(ctx.bot.services))
    )


@service.command(r"reload(?: all)? services$", mention=True, priority=3000)
@requires_permission("admin")
def reload_services(ctx):
    failed_services = []

    for service_name in list(ctx.bot.services.keys()):
        try:
            ctx.bot.load_service(service_name, True)
        except:
            failed_services.append(service_name)

    if failed_services:
        ctx.respond(ctx._("I couldn't reload the following services: {failed_services}").format(
            failed_services=", ".join(failed_services))
        )
    else:
        ctx.respond(ctx._("All services reloaded!"))


@service.command(r"rehash$", mention=True, priority=3000)
@requires_permission("admin")
def rehash(ctx):
    """
    Rehash configuration.

    Rehash the bot's configuration settings.
    """

    try:
        ctx.bot.rehash()
    except BaseException as e:
        ctx.respond(ctx._("Sorry, couldn't rehash."))
        ctx.respond("↳ {name}: {info}".format(
            name=e.__class__.__name__,
            info=str(e)
        ))
        return

    ctx.respond(ctx._("Configuration rehashed."))


@service.command(r"re(?:start|boot)$", mention=True, priority=3000)
@requires_permission("admin")
def restart(ctx):
    """
    Restart.

    Restart the bot. Will ``exec`` a new process into the currently running process
    space.
    """

    for ctx.client in list(ctx.bot.clients.values()):
        ctx.client.quit(ctx._("Restarting..."))

    @ctx.bot.event_loop.schedule
    def _restart():
        # The following code is ported from Tornado.
        # http://www.tornadoweb.org/en/branch2.4/_modules/tornado/autoreload.html

        if hasattr(signal, "setitimer"):
            # Clear the alarm signal set by
            # ioloop.set_blocking_log_threshold so it doesn't fire
            # after the exec.
            signal.setitimer(signal.ITIMER_REAL, 0, 0)
        # sys.path fixes: see comments at top of file.  If sys.path[0] is an empty
        # string, we were (probably) invoked with -m and the effective path
        # is about to change on re-exec.  Add the current directory to $PYTHONPATH
        # to ensure that the new process sees the same path we did.
        path_prefix = '.' + os.pathsep
        if (sys.path[0] == '' and
            not os.environ.get("PYTHONPATH", "").startswith(path_prefix)):
            os.environ["PYTHONPATH"] = (path_prefix +
                                        os.environ.get("PYTHONPATH", ""))
        if sys.platform == 'win32':
            # os.execv is broken on Windows and can't properly parse command line
            # arguments and executable name if they contain whitespaces. subprocess
            # fixes that behavior.
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit(0)
        else:
            try:
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except OSError:
                # Mac OS X versions prior to 10.6 do not support execv in
                # a process that contains multiple threads.  Instead of
                # re-executing in the current process, start a new one
                # and cause the current process to exit.  This isn't
                # ideal since the new process is detached from the parent
                # terminal and thus cannot easily be killed with ctrl-C,
                # but it's better than not being able to autoreload at
                # all.
                # Unfortunately the errno returned in this case does not
                # appear to be consistent, so we can't easily check for
                # this error specifically.
                os.spawnv(os.P_NOWAIT, sys.executable,
                          [sys.executable] + sys.argv)
                sys.exit(0)
