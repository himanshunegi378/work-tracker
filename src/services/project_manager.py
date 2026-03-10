from dataclasses import asdict
from typing import List
from models.project import Project
from persistence.storage import StorageInterface

class ProjectManager:
    def __init__(self, storage: StorageInterface):
        self.storage = storage
        self._projects: List[Project] = []
        self._sync_load()

    def _sync_load(self):
        data = self.storage.load()
        self._projects = [Project(**item) for item in data]

    def add_project(self, name: str, description: str, status: str = "active"):
        project = Project(name=name, description=description, status=status)
        self._projects.append(project)
        self.storage.save([asdict(p) for p in self._projects])
        return project

    def get_all_projects(self) -> List[Project]:
        return self._projects
