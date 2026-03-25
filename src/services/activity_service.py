import logging
from typing import Any, Dict, List, Optional
import time

from src.api import ApiClient, ApiClientError

logger = logging.getLogger(__name__)

class ActivityServiceError(Exception):
    """Raised when an activity operation fails."""
    pass

class ActivityService:
    """Loads activity type options from the Frappe search API."""
    
    def __init__(self, api_client: ApiClient):
        """Store the API client and shared search endpoint for activity lookups."""
        self.api_client = api_client
        self.search_endpoint = "/api/method/frappe.desk.search.search_widget"

    def get_activities(self, search_text: str = "", start: int = 0, page_length: int = 10, csrf_token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return normalized activity type records for the current search query."""
        # Appending a cache-buster timestamp helps avoid stale data
        timestamp = int(time.time() * 1000)
        
        params = {
            "txt": search_text,
            "searchfield": "name",
            "start": start,
            "page_length": page_length,
            "doctype": "Activity Type",
            "_": timestamp
        }

        headers = {
            "accept": "application/json",
            "x-frappe-cmd": "",
            "x-frappe-doctype": "Activity Type",
            "x-requested-with": "XMLHttpRequest"
        }
        
        # In Frappe, CSRF tokens can often be passed if you have extracted them from window.csrf_token
        # or the initial HTML payload.
        if csrf_token:
            headers["x-frappe-csrf-token"] = csrf_token

        try:
            response = self.api_client.get(
                self.search_endpoint, 
                params=params, 
                headers=headers
            )
            
            data = response.json()
            
            # Frappe 'search_widget' normally returns the data in the "message" key as a list of lists
            # e.g. {"message": [["Backlog Grooming"], ["Document Reviews"]]}
            activities = []
            if "message" in data and isinstance(data["message"], list):
                for raw_activity in data["message"]:
                    if isinstance(raw_activity, list) and len(raw_activity) >= 1:
                        activities.append({
                            "name": raw_activity[0]
                        })
                    else:
                        activities.append({"raw_data": raw_activity})
                return activities
            
            # If there are no results, sometimes it might just be empty or absent
            return []
            
        except ApiClientError as e:
            logger.error(f"Failed to fetch activities: {str(e)}")
            raise ActivityServiceError(f"Failed to fetch activities: {str(e)}") from e

    def get_activity_names(
        self,
        search_text: str = "",
        page_length: int = 200,
        csrf_token: Optional[str] = None,
    ) -> List[str]:
        """Return a deduplicated activity-name list for local selection UIs."""
        activities = self.get_activities(
            search_text=search_text,
            start=0,
            page_length=page_length,
            csrf_token=csrf_token,
        )
        names: List[str] = []
        seen = set()
        for activity in activities:
            name = str(activity.get("name") or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return names
