import logging
from typing import Any, Dict, List, Optional
import time

from src.api import ApiClient, ApiClientError

logger = logging.getLogger(__name__)

class ProjectServiceError(Exception):
    """Raised when a project operation fails."""
    pass

class ProjectService:
    """Loads project search results from the Frappe backend."""
    
    def __init__(self, api_client: ApiClient):
        """Store the API client and shared endpoint used for project searches."""
        self.api_client = api_client
        self.search_endpoint = "/api/method/frappe.desk.search.search_widget"

    def get_projects(
        self, 
        search_text: str = "", 
        start: int = 0, 
        page_length: int = 10, 
        filters: str = "{}",
        csrf_token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return normalized project records for the current search and filter set."""
        # Appending a cache-buster timestamp helps avoid stale data
        timestamp = int(time.time() * 1000)
        
        params = {
            "txt": search_text,
            "searchfield": "name",
            "start": start,
            "page_length": page_length,
            "filters": filters,
            "doctype": "Project",
            "_": timestamp
        }

        headers = {
            "accept": "application/json",
            "x-frappe-cmd": "",
            "x-frappe-doctype": "Project",
            "x-requested-with": "XMLHttpRequest"
        }
        
        if csrf_token:
            headers["x-frappe-csrf-token"] = csrf_token

        try:
            response = self.api_client.get(
                self.search_endpoint, 
                params=params, 
                headers=headers
            )
            
            data = response.json()
            
            projects = []
            
            # Frappe 'search_widget' for Project returns data in the "message" key
            # as a list of lists: e.g., ["PROJ-0006", "Crowst", null, "Open", "Medium", "Yes"]
            if "message" in data and isinstance(data["message"], list):
                for raw_project in data["message"]:
                    if isinstance(raw_project, list) and len(raw_project) >= 6:
                        projects.append({
                            "id": raw_project[0],          # "PROJ-0006"
                            "name": raw_project[1],        # "Crowst"
                            "description": raw_project[2], # null
                            "status": raw_project[3],      # "Open"
                            "priority": raw_project[4],    # "Medium"
                            "is_active": raw_project[5] == "Yes"  # "Yes" -> True
                        })
                    else:
                        # Fallback for unexpected formats
                        projects.append({"raw_data": raw_project})
                return projects
            
            return []
            
        except ApiClientError as e:
            logger.error(f"Failed to fetch projects: {str(e)}")
            raise ProjectServiceError(f"Failed to fetch projects: {str(e)}") from e

    def get_project_names(
        self,
        search_text: str = "",
        page_length: int = 200,
        filters: str = "{}",
        csrf_token: Optional[str] = None,
    ) -> List[str]:
        """Return a deduplicated project-name list for selection UIs."""
        projects = self.get_projects(
            search_text=search_text,
            start=0,
            page_length=page_length,
            filters=filters,
            csrf_token=csrf_token,
        )
        names: List[str] = []
        seen = set()
        for project in projects:
            name = str(project.get("name") or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return names
