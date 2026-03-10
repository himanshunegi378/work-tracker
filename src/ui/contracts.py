from abc import ABC, ABCMeta, abstractmethod
from typing import Dict, Any
from PySide6.QtCore import QObject

# Define a compatible metaclass to resolve the conflict between ABC and Qt
class QtABCMeta(type(QObject), ABCMeta):
    pass

class ProjectAddViewInterface(ABC, metaclass=QtABCMeta):
    """The 'Dumb' View interface that only knows how to show data and emit events."""
    
    @abstractmethod
    def get_form_data(self) -> Dict[str, str]:
        """Returns the raw input from the user."""
        pass

    @abstractmethod
    def show_error(self, message: str):
        """Displays an error message to the user."""
        pass

    @abstractmethod
    def show_success(self, message: str):
        """Displays a success message to the user."""
        pass

    @abstractmethod
    def clear_form(self):
        """Resets the input fields."""
        pass

    @abstractmethod
    def set_loading(self, is_loading: bool):
        """Disables/Enables UI during processing."""
        pass
