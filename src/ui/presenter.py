from ui.contracts import ProjectAddViewInterface
from services.project_manager import ProjectManager

# ---------------------------------------------------------------------------
# DEPRECATED: ProjectAddPresenter is no longer used by the GUI.
# The Projects page is now read-only (API-backed via ProjectService).
# This file is kept to avoid breaking any incremental imports until a
# full cleanup pass is performed.
# ---------------------------------------------------------------------------

class ProjectAddPresenter:
    """The 'Brain' that coordinates the View and Service layers."""
    
    def __init__(self, view: ProjectAddViewInterface, project_manager: ProjectManager):
        self.view = view
        self.pm = project_manager

    def on_submit_clicked(self):
        """Logic for adding a project, decoupled from PySide components."""
        data = self.view.get_form_data()
        
        # 1. Validation Logic (Decoupled from Qt)
        name = data.get("name", "").strip()
        desc = data.get("description", "").strip()
        status = data.get("status", "active")

        if not name:
            self.view.show_error("Project Name is mandatory.")
            return

        # 2. Process Data via Service
        try:
            self.view.set_loading(True)
            self.pm.add_project(name=name, description=desc, status=status)
            
            # 3. Update View based on success
            self.view.show_success(f"Project '{name}' successfully created.")
            self.view.clear_form()
            
        except Exception as e:
            self.view.show_error(f"Internal Error: {str(e)}")
        finally:
            self.view.set_loading(False)
