import time
import sys
import os

# Add src to python path for modular imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from services.project_manager import ProjectManager
from services.log_manager import LogManager
from services.scheduler import CronScheduler
from persistence.storage import JSONStorage
from ui.cli import CLIPromptHandler

def backup_status():
    """A dummy secondary job for demonstration."""
    print("📋 [Background Task] Running data integrity check... OK.")

def main():
    # 1. Initialize storage
    p_storage = JSONStorage("data/projects.json")
    l_storage = JSONStorage("data/logs.json")
    
    p_manager = ProjectManager(p_storage)
    l_manager = LogManager(l_storage)

    # 2. Setup UI and Scheduler
    prompt_handler = CLIPromptHandler(p_manager, l_manager)
    
    # 3. Architect Multi-Job Scheduler
    scheduler = CronScheduler(tick_interval=1.0)
    
    # Job A: Periodic log prompt
    scheduler.add_job(
        name="Log Prompt", 
        task_func=prompt_handler.invoke_log_prompt, 
        interval_seconds=60*15,
        invoke_on_start=True
    )
    
    # Job B: System status check (invoked immediately on start)
    scheduler.add_job(
        name="Status Check", 
        task_func=backup_status, 
        interval_seconds=30,
        invoke_on_start=True
    )

    print("\n=== Senior Architect Multi-Job Scheduler ===")
    print("Job A: Log prompt every 15s")
    print("Job B: Status check every 5s")
    print("Ctrl+C to terminate.")

    try:
        scheduler.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    finally:
        scheduler.stop()

if __name__ == "__main__":
    main()
