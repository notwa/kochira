import threading
import logging
import time

logger = logging.getLogger(__name__)


class Work(object):
    """
    A piece of work for the scheduler. Contains a deadline indicating to the
    scheduler how long to wait until the task needs to be executed.
    """

    def __init__(self, deadline, repeat=None, args=None, kwargs=None):
        self.deadline = deadline
        self.repeat = repeat
        self.args = args if args is not None else []
        self.kwargs = kwargs if kwargs is not None else {}

    def reset_repeating_deadline(self):
        self.deadline += self.repeat.total_seconds()


class Scheduler(threading.Thread):
    daemon = True

    def __init__(self, bot):
        self.bot = bot
        self.work = {}
        self.work_lock = threading.RLock()

        super().__init__()

    def run(self):
        self.last_tick = time.time()

        while True:
            current = time.time()
            dt = current - self.last_tick

            with self.work_lock:
                # we hold a massive scheduler lock here so that we have a
                # consistent view of all work that needs to be scheduled and
                # nothing attempts to schedule while we're in the middle of
                # processing tasks
                for service, _ in self.bot.services.values():
                    for task in service.tasks:
                        k = (service.name, task.__name__)

                        if k not in self.work:
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

                                if work.repeat is not None:
                                    work.reset_repeating_deadline()

                            if work.deadline > 0:
                                # deadline may have been reset
                                remaining_work.append(work)

                        if remaining_work:
                            self.work[k] = remaining_work
                        else:
                            del self.work[k]

            self.last_tick = current
            self._cleanup_dead_queues()

            time.sleep(0.1)

    def _cleanup_dead_queues(self):
        active_queue_names = set([])

        for service, _ in self.bot.services.values():
            for task in service.tasks:
                k = (service.name, task.__name__)
                active_queue_names.add(k)

        with self.work_lock:
            for k in set(self.work) - active_queue_names:
                logger.info("Removing dead queue for %s.%s", k[0], k[1])
                del self.work[k]

    def _schedule_work(self, task, work):
        logger.info("Scheduling task %s.%s in %s seconds (repeat: %s)",
                    task.service.name, task.__name__, work.deadline,
                    work.repeat)

        with self.work_lock:
            self.work \
                .setdefault((task.service.name, task.__name__), []) \
                .append(work)

        return work

    def schedule_after(self, time, task, *args, **kwargs):
        """
        Schedule a task to run after a given amount of time.
        """
        return self._schedule_work(task,
                                   Work(time.total_seconds(),
                                        None, args, kwargs))

    def schedule_every(self, interval, task, *args, **kwargs):
        """
        Schedule a task to run every given interval.
        """
        return self._schedule_work(task,
                                   Work(interval.total_seconds(), interval,
                                        args, kwargs))

    def unschedule_task(self, task):
        logger.info("Unscheduling all work for task %s.%s",
                    task.service.name, task.__name__)

        with self.work_lock:
            for service_name, task_name in list(self.work.keys()):
                if service_name == task.service.name and \
                   task_name == task.__name__:
                    del self.work[service_name, task_name]

    def unschedule_service(self, service):
        logger.info("Unscheduling all work for service %s", service.name)

        with self.work_lock:
            for service_name, task_name in list(self.work.keys()):
                if service_name == service.name:
                    del self.work[service_name, task_name]
