from threading import Thread
import logging
import time

logger = logging.getLogger(__name__)


class Work(object):
    """
    A piece of work for the scheduler. Contains a deadline indicating to the
    scheduler how long to wait until the task needs to be executed.
    """

    def __init__(self, deadline, args=None, kwargs=None):
        self.deadline = deadline
        self.args = args if args is not None else []
        self.kwargs = kwargs if kwargs is not None else {}


class Scheduler(Thread):
    daemon = True

    def __init__(self, bot):
        self.bot = bot
        self.work = {}

        super().__init__()

    def run(self):
        self.last_tick = time.time()

        while True:
            current = time.time()
            dt = current - self.last_tick

            # now schedule all the jobs
            for service, _ in self.bot.services.values():
                for task, interval in service.tasks:
                    k = (service.name, task.__name__)

                    if k not in self.work and interval is not None:
                        # this task is being scheduled automatically
                        self.work.setdefault(k, []).append(Work(interval.total_seconds()))

                    if k not in self.work:
                        # task is scheduled in manual mode
                        continue

                    remaining_work = []

                    for work in self.work[k]:
                        work.deadline -= dt

                        if work.deadline <= 0:
                            # task needs to run now
                            logger.info("Submitting task %s.%s to executor (late by %.2fs)",
                                service.name,
                                task.__name__,
                                -work.deadline
                            )

                            future = self.bot.executor.submit(task, self.bot,
                                                              *work.args,
                                                              **work.kwargs)

                            @future.add_done_callback
                            def on_complete(future):
                                exc = future.exception()
                                if exc is not None:
                                    logger.error("Task error", exc_info=exc)
                        else:
                            remaining_work.append(work)

                    if remaining_work:
                        self.work[k] = remaining_work
                    else:
                        del self.work[k]

            self.last_tick = current

            time.sleep(0.1)

    def schedule_after(self, time, task, *args, **kwargs):
        """
        Schedule a task to run after a given amount of time.
        """
        k = (task.service.name, task.__name__)
        self.work.setdefault(k, []).append(Work(time.total_seconds(), args, kwargs))
