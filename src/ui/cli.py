from services.project_manager import ProjectManager
from services.log_manager import LogManager

class CLIPromptHandler:
    def __init__(self, project_manager: ProjectManager, log_manager: LogManager):
        self.project_manager = project_manager
        self.log_manager = log_manager

    def invoke_log_prompt(self):
        print("\n" + "="*40)
        print("🕒 SCHEDULED LOG UPDATE")
        print("="*40)

        projects = self.project_manager.get_all_projects()
        if not projects:
            print("No projects found to log against.")
            return

        print("Select a project:")
        for i, p in enumerate(projects):
            print(f"{i + 1}. {p.name}")

        try:
            choice = int(input("\nEnter project number: ")) - 1
            if 0 <= choice < len(projects):
                selected_project = projects[choice]
                description = input(f"What did you just finish for '{selected_project.name}'? ")
                
                if description.strip():
                    self.log_manager.add_log(selected_project.name, description)
                    print(f"✅ Log saved for {selected_project.name}.")
                else:
                    print("⚠️ Log description cannot be empty. Skipping.")
            else:
                print("❌ Invalid selection.")
        except (ValueError, IndexError):
            print("❌ Invalid input. Skipping log entry.")
        except KeyboardInterrupt:
            print("\n⚠️ Log entry cancelled.")
        
        print("="*40 + "\n")
