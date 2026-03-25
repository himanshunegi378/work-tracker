from PySide6.QtCore import QObject, Slot
from ui.views.settings_view import SettingsView
from services.auth_service import AuthService
from PySide6.QtCore import QTimer

class SettingsPresenter(QObject):
    """Coordinate credential settings actions between the view and auth service."""

    def __init__(self, view: SettingsView, auth_service: AuthService):
        """Wire settings view events to auth actions and preload saved state."""
        super().__init__()
        self.view = view
        self.auth = auth_service
        
        # Connect signals
        self.view.save_credentials_requested.connect(self.handle_save_credentials)
        self.view.clear_credentials_requested.connect(self.handle_clear_credentials)
        
        # Initial population of UI based on existing state
        self._populate_initial_state()
        
    def _populate_initial_state(self):
        """Pre-fill the view with any username already saved on disk."""
        # Check if auth_service has previously loaded credentials via its credential_storage
        if hasattr(self.auth, 'get_saved_username'):
            saved_user = self.auth.get_saved_username()
            if saved_user:
                self.view.populate_credentials(saved_user)
                
    @Slot(str, str)
    def handle_save_credentials(self, username, password):
        """Validate the provided credentials and persist them through AuthService."""
        self.view.set_loading(True)
        
        # Due to potential UI blocking by synchronous HTTP requests, process events.
        # For a truly non-blocking architecture, threading/QRunnable should be used.
        # Using a QTimer to offload the call allows the UI to update "Saving..." text before blocking.
        QTimer.singleShot(50, lambda: self._execute_save(username, password))
        
    def _execute_save(self, username, password):
        """Run the actual save flow after the UI has had a chance to update."""
        try:
            # Login authenticates against the backend
            success = self.auth.login(username, password)
            if success:
                # With successful login, we also tell auth service to persist these.
                # In current implementation, Auth service will persist them if we adapt it.
                self.view.show_success("Credentials saved and verified successfully.")
            else:
                self.view.show_error("Validation failed. Check your credentials.")
        except Exception as e:
            self.view.show_error(f"Failed to authenticate: {str(e)}")
        finally:
            self.view.set_loading(False)
            
    @Slot()
    def handle_clear_credentials(self):
        """Remove saved credentials and clear the related form fields."""
        try:
            if hasattr(self.auth, 'clear_saved_credentials'):
                self.auth.clear_saved_credentials()
            
            self.view.username_input.clear()
            self.view.password_input.clear()
            self.view.show_success("Credentials explicitly cleared.")
        except Exception as e:
            self.view.show_error(f"Failed to clear credentials: {str(e)}")
