"""
Configurable Scheduler Module
Provides a flexible scheduling system for running tasks at specific intervals
"""
import logging
from typing import Callable, Dict, Any, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import environ

logger = logging.getLogger(__name__)


class SchedulerConfig:
    """Configuration for a scheduled task"""

    def __init__(
        self,
        name: str,
        func: Callable,
        trigger_type: str = 'interval',
        **kwargs
    ):
        """
        Initialize a scheduler configuration

        Args:
            name: Unique name for the scheduled task
            func: The function to be called
            trigger_type: Type of trigger ('interval' or 'cron')
            **kwargs: Additional arguments for the trigger
                For interval: seconds, minutes, hours, days, weeks
                For cron: year, month, day, week, day_of_week, hour, minute, second
                    Cron fields accept:
                    - Integers: hour=3
                    - Strings for ranges: hour='8-15'
                    - Strings for step values: minute='*/3' (every 3rd minute)
                    - Strings for lists: hour='8,12,16'
                    Examples:
                        hour='8-15', minute='*/3'  # Every 3 minutes during hours 8-15
                        day_of_week='mon-fri', hour=9  # Weekdays at 9 AM
        """
        self.name = name
        self.func = func
        self.trigger_type = trigger_type
        self.trigger_kwargs = kwargs

    def __repr__(self):
        return f"SchedulerConfig(name={self.name}, trigger_type={self.trigger_type})"


class TaskScheduler:
    """
    Main scheduler class for managing scheduled tasks
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.jobs: Dict[str, Any] = {}
        self._setup_event_listeners()

    def _setup_event_listeners(self):
        """Setup listeners for job execution events"""
        self.scheduler.add_listener(
            self._job_executed_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

    def _job_executed_listener(self, event):
        """Log job execution events"""
        if event.exception:
            logger.error(
                f"Job {event.job_id} failed with exception: {event.exception}",
                exc_info=event.exception
            )
        else:
            logger.debug(f"Job {event.job_id} executed successfully")

    def add_task(self, config: SchedulerConfig) -> None:
        """
        Add a task to the scheduler

        Args:
            config: SchedulerConfig object defining the task
        """
        try:
            if config.trigger_type == 'interval':
                job = self.scheduler.add_job(
                    config.func,
                    trigger=IntervalTrigger(**config.trigger_kwargs),
                    id=config.name,
                    name=config.name,
                    replace_existing=True
                )
            elif config.trigger_type == 'cron':
                job = self.scheduler.add_job(
                    config.func,
                    trigger=CronTrigger(**config.trigger_kwargs),
                    id=config.name,
                    name=config.name,
                    replace_existing=True
                )
            else:
                raise ValueError(f"Unknown trigger type: {config.trigger_type}")

            self.jobs[config.name] = job
            logger.info(f"Added scheduled task: {config.name} with trigger {config.trigger_type}")

        except Exception as e:
            logger.error(f"Failed to add task {config.name}: {e}")
            raise

    def remove_task(self, name: str) -> None:
        """
        Remove a task from the scheduler

        Args:
            name: Name of the task to remove
        """
        try:
            self.scheduler.remove_job(name)
            if name in self.jobs:
                del self.jobs[name]
            logger.info(f"Removed scheduled task: {name}")
        except Exception as e:
            logger.warning(f"Failed to remove task {name}: {e}")

    def start(self) -> None:
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info(f"Scheduler started with {len(self.jobs)} tasks")
        else:
            logger.warning("Scheduler is already running")

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the scheduler

        Args:
            wait: If True, wait for all jobs to complete before shutting down
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("Scheduler shut down")
        else:
            logger.warning("Scheduler is not running")

    def pause_task(self, name: str) -> None:
        """Pause a specific task"""
        try:
            self.scheduler.pause_job(name)
            logger.info(f"Paused task: {name}")
        except Exception as e:
            logger.error(f"Failed to pause task {name}: {e}")

    def resume_task(self, name: str) -> None:
        """Resume a paused task"""
        try:
            self.scheduler.resume_job(name)
            logger.info(f"Resumed task: {name}")
        except Exception as e:
            logger.error(f"Failed to resume task {name}: {e}")

    def get_jobs(self) -> list:
        """Get list of all scheduled jobs"""
        return self.scheduler.get_jobs()

    def get_job_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific job

        Args:
            name: Name of the job

        Returns:
            Dictionary with job information or None if not found
        """
        try:
            job = self.scheduler.get_job(name)
            if job:
                return {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time,
                    'trigger': str(job.trigger)
                }
        except Exception as e:
            logger.error(f"Failed to get job info for {name}: {e}")
        return None


def load_scheduler_config_from_env() -> list[SchedulerConfig]:
    """
    Load scheduler configuration from environment variables

    Environment variables should be in the format:
    SCHEDULER_TASK_<NAME>_ENABLED=true|false
    SCHEDULER_TASK_<NAME>_TYPE=interval|cron
    SCHEDULER_TASK_<NAME>_INTERVAL_SECONDS=60
    SCHEDULER_TASK_<NAME>_INTERVAL_MINUTES=5
    SCHEDULER_TASK_<NAME>_CRON_HOUR=*/2
    etc.

    Returns:
        List of SchedulerConfig objects
    """
    env = environ.Env()
    configs = []

    # This is a placeholder - you would implement actual parsing logic
    # based on your specific requirements

    logger.debug("Loaded scheduler configuration from environment")
    return configs


# Global scheduler instance
_scheduler_instance: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """Get the global scheduler instance"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = TaskScheduler()
    return _scheduler_instance

