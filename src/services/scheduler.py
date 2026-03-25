import time
import threading
from typing import List, Callable, Optional
from models.job import Job

class CronScheduler:
    """Run named jobs on independent intervals from a shared heartbeat thread."""

    def __init__(self, tick_interval: float = 1.0):
        """Create the scheduler and configure how often due jobs are checked."""
        self.tick_interval = tick_interval
        self._jobs: List[Job] = []
        self._jobs_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    def add_job(self, name: str, task_func: Callable, interval_seconds: int, invoke_on_start: bool = False):
        """Register a job definition without starting the scheduler automatically."""
        with self._jobs_lock:
            new_job = Job(name=name, task_func=task_func, interval_seconds=interval_seconds)
            
            if invoke_on_start:
                new_job.set_due_now()
                
            self._jobs.append(new_job)
            print(f"➕ Registered job '{name}' every {interval_seconds}s (Invoke on start: {invoke_on_start}).")

    def start(self):
        """Start the background heartbeat that watches for due jobs."""
        if self._is_running:
            return
        self._is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        print("🚀 Scheduler heartbeat started.")

    def _heartbeat_loop(self):
        """Poll due jobs and dispatch each run in its own worker thread."""
        while not self._stop_event.is_set():
            with self._jobs_lock:
                for job in self._jobs:
                    if job.is_due():
                        # We execute the job in its own thread to avoid blocking the heartbeat
                        # This ensures long-running jobs don't delay other tasks.
                        threading.Thread(target=self._execute_job, args=(job,), daemon=True).start()
            
            # Precise sleep to keep the loop steady
            time.sleep(self.tick_interval)

    def _execute_job(self, job: Job):
        """Execute one job safely while keeping its scheduling metadata current."""
        try:
            # We update BEFORE so a long execution doesn't cause overlapping runs 
            # if we wanted skip-overlapping logic.
            job.update_last_run()
            job.task_func()
        except Exception as e:
            print(f"❌ Error executing job '{job.name}': {e}")

    def stop(self):
        """Stop the scheduler thread and forget all registered jobs."""
        self._stop_event.set()
        self._is_running = False
        if self._thread:
            self._thread.join(timeout=1)
        with self._jobs_lock:
            self._jobs.clear()
        print("🛑 Scheduler stopped.")

    def is_active(self) -> bool:
        """Report whether the scheduler heartbeat is currently running."""
        return self._is_running
