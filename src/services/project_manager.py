from dataclasses import asdict
from typing import List
from models.project import Project
from persistence.storage import StorageInterface

# ---------------------------------------------------------------------------
# DEPRECATED: ProjectManager is a local JSON-backed store used by the CLI.
# The GUI now uses ProjectService (API-backed). Do not add new GUI features
# that depend on this class. It will be removed once the CLI is migrated.
# ---------------------------------------------------------------------------

class ProjectManager:
    """Manage the deprecated local project store used by the CLI path."""

    def __init__(self, storage: StorageInterface):
        """Load the persisted project snapshot into memory."""
        self.storage = storage
        self._projects: List[Project] = []
        self._sync_load()

    def _sync_load(self):
        """Refresh the in-memory project list from local storage."""
        data = self.storage.load()
        self._projects = [Project(**item) for item in data]

    def add_project(self, name: str, description: str, status: str = "active"):
        """Create a local project record and persist it to the JSON-backed store."""
        project = Project(name=name, description=description, status=status)
        self._projects.append(project)
        self.storage.save([asdict(p) for p in self._projects])
        return project

    def get_all_projects(self) -> List[Project]:
        """Return all locally stored projects in their saved order."""
        return self._projects
