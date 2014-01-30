from threading import Thread
import logging
import time

logger = logging.getLogger(__name__)


class Scheduler(Thread):
    daemon = True

    def __init__(self, bot):
        self.bot = bot
        self.deadlines = {}

        super().__init__()

    def run(self):
        self.last_tick = time.time()

        while True:
            current = time.time()
            dt = current - self.last_tick

            # now schedule all the jobs
            for service in self.bot.services.values():
                for task, interval in service.tasks:
                    k = (service.name, task.__name__)

                    if k not in self.deadlines:
                        # this task has never been scheduled
                        self.deadlines[k] = interval.total_seconds()

                    self.deadlines[k] -= dt

                    if self.deadlines[k] <= 0:
                        # task needs to run now
                        logger.info("Submitting task %s.%s to executor (late by %.2fs)",
                            service.name,
                            task.__name__,
                            -self.deadlines[k]
                        )

                        self.bot.executor.submit(task, self.bot)

                        # reschedule the task next tick
                        del self.deadlines[k]

            self.last_tick = current

            time.sleep(0.1)
