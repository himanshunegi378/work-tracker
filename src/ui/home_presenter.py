from services.project_manager import ProjectManager
from ui.views.home_view import HomeView, AddProjectDialog

class HomePresenter:
    """Controls the dashboard and orchestration of project list updates."""
    def __init__(self, view: HomeView, project_manager: ProjectManager):
        self.view = view
        self.pm = project_manager
        
        # Connect View signals
        self.view.add_project_requested.connect(self.on_add_project_requested)
        
        # Initial data load
        self.refresh_projects()

    def refresh_projects(self):
        """Fetches and displays the latest project list."""
        projects = self.pm.get_all_projects()
        self.view.display_projects(projects)

    def on_add_project_requested(self):
        """Opens the add project dialog and refreshes on close."""
        dialog = AddProjectDialog(self.pm, parent=self.view)
        # We want to refresh the list after the dialog closes 
        # (assuming a project was added)
        dialog.exec()
        self.refresh_projects()
