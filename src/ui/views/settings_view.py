from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, 
    QFrame, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal

from src.ui.theme import COLORS, card_style
from src.ui.design import SPACE, Card, bind_style, button, current as _t, label, manager, set_prop

class SettingsView(QWidget):
    """View component for managing application settings like login credentials."""
    
    # Signals to communicate user actions to the Presenter
    save_credentials_requested = Signal(str, str) # username, password
    clear_credentials_requested = Signal()
    install_cli_requested = Signal()
    install_skill_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        """Sets up the layout and widgets for the settings view."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(20)
        self.layout.setAlignment(Qt.AlignTop)
        
        # Header
        self.layout.addWidget(label("Settings", "title"))

        # Appearance Section
        appearance = Card()
        appearance.body.addWidget(label("Appearance", "heading"))
        appearance.body.addWidget(label("Choose how Work Tracker looks. Your choice is remembered.", "caption"))
        theme_row = QHBoxLayout()
        theme_row.setSpacing(SPACE["sm"])
        self.light_btn = button("Light", "secondary")
        self.dark_btn = button("Dark", "secondary")
        for name, btn in (("light", self.light_btn), ("dark", self.dark_btn)):
            btn.setFixedWidth(110)
            btn.clicked.connect(lambda _=False, n=name: manager.set_theme(n))
            theme_row.addWidget(btn)
        theme_row.addStretch()
        appearance.body.addLayout(theme_row)
        self.layout.addWidget(appearance)
        manager.changed.connect(lambda _t_: self._sync_theme_buttons())
        self._sync_theme_buttons()
        
        # Command line section
        cli_card = Card()
        cli_card.body.addWidget(label("Command line and AI agents", "heading"))
        cli_card.body.addWidget(label(
            "Use Work Tracker from any terminal as 'samta-tracker', and let AI agents such as "
            "Claude Code control it.", "caption"))
        self.cli_status_label = label("", "caption")
        self.cli_status_label.setWordWrap(True)
        cli_card.body.addWidget(self.cli_status_label)
        cli_row = QHBoxLayout()
        cli_row.setSpacing(SPACE["sm"])
        self.install_cli_btn = button("Install command-line tool", "secondary")
        self.install_skill_btn = button("Install agent skill", "secondary")
        self.install_cli_btn.clicked.connect(lambda _=False: self.install_cli_requested.emit())
        self.install_skill_btn.clicked.connect(lambda _=False: self.install_skill_requested.emit())
        cli_row.addWidget(self.install_cli_btn)
        cli_row.addWidget(self.install_skill_btn)
        cli_row.addStretch()
        cli_card.body.addLayout(cli_row)
        self.layout.addWidget(cli_card)

        # Credentials Section Frame
        cred_frame = QFrame()
        cred_frame.setObjectName("cred_frame")
        bind_style(cred_frame, lambda: card_style("cred_frame"))
        cred_layout = QVBoxLayout(cred_frame)
        cred_layout.setContentsMargins(20, 20, 20, 20)
        cred_layout.setSpacing(15)
        
        section_lbl = QLabel("Login Credentials")
        bind_style(section_lbl, lambda: f"font-size: 16px; font-weight: bold; color: {_t().text}; border: none;")
        cred_layout.addWidget(section_lbl)
        
        # Username Input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username or Email")
        bind_style(self.username_input, lambda: f"""
            QLineEdit {{
                padding: 10px;
                border: 1px solid {_t().border};
                border-radius: 4px;
                font-size: 14px;
            }}
            QLineEdit:focus {{ border: 1px solid {_t().accent}; }}
        """)
        cred_layout.addWidget(self.username_input)
        
        # Password Input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        bind_style(self.password_input, lambda: f"""
            QLineEdit {{
                padding: 10px;
                border: 1px solid {_t().border};
                border-radius: 4px;
                font-size: 14px;
            }}
            QLineEdit:focus {{ border: 1px solid {_t().accent}; }}
        """)
        cred_layout.addWidget(self.password_input)
        
        # Show Password Checkbox
        self.show_password_checkbox = QCheckBox("Show Password")
        bind_style(self.show_password_checkbox, lambda: f"""
            QCheckBox {{
                font-size: 13px;
                color: {_t().text_secondary};
                border: none;
            }}
        """)
        self.show_password_checkbox.stateChanged.connect(self._on_show_password_changed)
        cred_layout.addWidget(self.show_password_checkbox)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.save_btn = QPushButton("Save Credentials")
        bind_style(self.save_btn, lambda: f"""
            QPushButton {{
                background-color: {_t().success};
                color: {_t().text_on_accent};
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{ background-color: {_t().success_hover}; }}
            QPushButton:disabled {{ background-color: {_t().success}; }}
        """)
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_layout.addWidget(self.save_btn)
        
        self.clear_btn = QPushButton("Clear Credentials")
        bind_style(self.clear_btn, lambda: f"""
            QPushButton {{
                background-color: {_t().danger};
                color: {_t().text_on_accent};
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{ background-color: {_t().danger_hover}; }}
        """)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        cred_layout.addLayout(btn_layout)
        
        self.layout.addWidget(cred_frame)
        self.layout.addStretch()
        
    def set_cli_state(self, status_text: str, can_install_cli: bool, cli_label: str, skill_label: str):
        """Shows whether the command line and agent skill are set up, and what the buttons will do."""
        self.cli_status_label.setText(status_text)
        self.install_cli_btn.setEnabled(can_install_cli)
        self.install_cli_btn.setText(cli_label)
        self.install_skill_btn.setText(skill_label)

    def show_info(self, message: str):
        """Displays a neutral notification (used for setup results with extra instructions)."""
        QMessageBox.information(self, "Command line", message)

    def _sync_theme_buttons(self):
        active = _t().name
        set_prop(self.light_btn, "variant", "primary" if active == "light" else "secondary")
        set_prop(self.dark_btn, "variant", "primary" if active == "dark" else "secondary")

    def _on_save_clicked(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            self.show_error("Please enter both username and password.")
            return
            
        self.save_credentials_requested.emit(username, password)
        
    def _on_clear_clicked(self):
        self.clear_credentials_requested.emit()
        
    def _on_show_password_changed(self, state):
        if self.show_password_checkbox.isChecked():
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)

    def set_loading(self, is_loading: bool):
        """Updates the UI state while an operation is occurring."""
        self.save_btn.setEnabled(not is_loading)
        self.save_btn.setText("Saving..." if is_loading else "Save Credentials")
        self.username_input.setEnabled(not is_loading)
        self.password_input.setEnabled(not is_loading)
        self.show_password_checkbox.setEnabled(not is_loading)
        
    def populate_credentials(self, username: str, password: str = ""):
        """Pre-fills the username and password fields."""
        if username:
            self.username_input.setText(username)
        if password:
            self.password_input.setText(password)
            
    def show_success(self, message: str):
        """Displays a success notification to the user."""
        QMessageBox.information(self, "Success", message)
        
    def show_error(self, message: str):
        """Displays an error notification to the user."""
        QMessageBox.critical(self, "Error", message)
