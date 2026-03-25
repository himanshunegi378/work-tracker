from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, 
    QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal

class SettingsView(QWidget):
    """View component for managing application settings like login credentials."""
    
    # Signals to communicate user actions to the Presenter
    save_credentials_requested = Signal(str, str) # username, password
    clear_credentials_requested = Signal()
    
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
        header_lbl = QLabel("⚙️ Settings")
        header_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #333;")
        self.layout.addWidget(header_lbl)
        
        # Credentials Section Frame
        cred_frame = QFrame()
        cred_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #E0E0E0;
            }
        """)
        cred_layout = QVBoxLayout(cred_frame)
        cred_layout.setContentsMargins(20, 20, 20, 20)
        cred_layout.setSpacing(15)
        
        section_lbl = QLabel("Login Credentials")
        section_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #444; border: none;")
        cred_layout.addWidget(section_lbl)
        
        # Username Input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username or Email")
        self.username_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #CCC;
                border-radius: 4px;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #2196F3; }
        """)
        cred_layout.addWidget(self.username_input)
        
        # Password Input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #CCC;
                border-radius: 4px;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #2196F3; }
        """)
        cred_layout.addWidget(self.password_input)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.save_btn = QPushButton("Save Credentials")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #45A049; }
            QPushButton:disabled { background-color: #A5D6A7; }
        """)
        self.save_btn.clicked.connect(self._on_save_clicked)
        btn_layout.addWidget(self.save_btn)
        
        self.clear_btn = QPushButton("Clear Credentials")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #E53935; }
        """)
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        cred_layout.addLayout(btn_layout)
        
        self.layout.addWidget(cred_frame)
        self.layout.addStretch()
        
    def _on_save_clicked(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            self.show_error("Please enter both username and password.")
            return
            
        self.save_credentials_requested.emit(username, password)
        
    def _on_clear_clicked(self):
        self.clear_credentials_requested.emit()
        
    def set_loading(self, is_loading: bool):
        """Updates the UI state while an operation is occurring."""
        self.save_btn.setEnabled(not is_loading)
        self.save_btn.setText("Saving..." if is_loading else "Save Credentials")
        self.username_input.setEnabled(not is_loading)
        self.password_input.setEnabled(not is_loading)
        
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
