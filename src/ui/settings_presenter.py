from PySide6.QtCore import QObject, Slot
from src.core import cli_setup
from src.services.auth_service import AuthService
from src.ui.views.settings_view import SettingsView
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
        self.view.install_cli_requested.connect(self.handle_install_cli)
        self.view.install_skill_requested.connect(self.handle_install_skill)
        self.refresh_cli_state()
        
        # Initial population of UI based on existing state
        self._populate_initial_state()
        
    def _populate_initial_state(self):
        """Pre-fill the view with any credentials already saved and attempt auto-login."""
        saved_user = self.auth.get_saved_username() if hasattr(self.auth, 'get_saved_username') else None
        saved_pass = self.auth.get_saved_password() if hasattr(self.auth, 'get_saved_password') else None
        
        if saved_user:
            self.view.populate_credentials(saved_user, saved_pass or "")
            
            # If both are present, trigger an initial login check to verify the session
            if saved_pass:
                # We trigger this after a short delay to ensure UI is ready
                QTimer.singleShot(500, lambda: self._execute_save(saved_user, saved_pass, silent=True))
                
    @Slot(str, str)
    def handle_save_credentials(self, username, password):
        """Validate the provided credentials and persist them through AuthService."""
        self.view.set_loading(True)
        QTimer.singleShot(50, lambda: self._execute_save(username, password, silent=False))

    def _execute_save(self, username, password, silent=False):
        """Run the actual save flow after the UI has had a chance to update."""
        try:
            # Login authenticates against the backend
            success = self.auth.login(username, password)
            if success:
                if not silent:
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
            self.view.show_password_checkbox.setChecked(False)
            self.view.show_success("Credentials explicitly cleared.")
        except Exception as e:
            self.view.show_error(f"Failed to clear credentials: {str(e)}")

    def refresh_cli_state(self):
        """Show whether the terminal command and the agent skill are already set up."""
        exe = cli_setup.cli_executable()
        installed = cli_setup.is_installed()
        skill = cli_setup.skill_status()
        if exe is None:
            text = "The command-line program was not found next to this app, so it cannot be installed from here."
        else:
            text = ("Terminal command: " + ("installed" if installed else "not installed")
                    + "  |  Agent skill: " + {"current": "installed", "outdated": "update available", "missing": "not installed"}[skill])
        self.view.set_cli_state(
            text,
            can_install_cli=exe is not None,
            cli_label="Command-line tool installed" if (exe is not None and installed) else "Install command-line tool",
            skill_label={"current": "Agent skill installed", "outdated": "Update agent skill", "missing": "Install agent skill"}[skill],
        )

    @Slot()
    def handle_install_cli(self):
        """Put `samta-tracker` on the user's PATH."""
        try:
            outcome = cli_setup.install_command()
        except cli_setup.SetupError as exc:
            self.view.show_error(str(exc))
        else:
            message = outcome.message
            if outcome.restart_terminal:
                message += "\n\nOpen a new terminal for it to take effect."
            if outcome.hint:
                message += "\n\n" + outcome.hint
            self.view.show_info(message)
        self.refresh_cli_state()

    @Slot()
    def handle_install_skill(self):
        """Install (or refresh) the agent skill for Claude Code."""
        try:
            status, path = cli_setup.install_skill(force=True)
        except cli_setup.SetupError as exc:
            self.view.show_error(str(exc))
        else:
            self.view.show_info(
                f"Agent skill {status}:\n{path}\n\nRestart your agent (for example Claude Code) to pick it up.")
        self.refresh_cli_state()
