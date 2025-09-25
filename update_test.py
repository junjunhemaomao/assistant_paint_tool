from maya import cmds
from PySide2 import QtWidgets, QtCore, QtGui
from shiboken2 import wrapInstance
import maya.OpenMayaUI as omui
import os, shutil, sys, threading, time, urllib.request, ssl

test_tool_dialog = None
CURRENT_VERSION = "0.9" 
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/version.txt"
GITHUB_SCRIPT_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/Assistant_tool.py"
GITHUB_PAGE_URL = "https://github.com/junjunhemaomao/assistant_paint_tool"
TIMEOUT = 10
SSL_CTX = ssl.create_default_context()

try:
    LOCAL_SCRIPT_PATH = os.path.abspath(__file__)
except NameError:
    LOCAL_SCRIPT_PATH = os.path.abspath(sys.argv[0])

def check_for_updates():
    global test_tool_dialog
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(GITHUB_VERSION_URL, headers={"User-Agent": "Test-Tool"})
        with urllib.request.urlopen(req, context=ctx, timeout=TIMEOUT) as resp:
            if resp.getcode() == 200:
                latest_version = resp.read().decode("utf-8").strip()
                cmds.warning(f"[TEST] Current version: {CURRENT_VERSION}, Latest version: {latest_version}")
                
                if latest_version != CURRENT_VERSION:
                    cmds.confirmDialog(
                        title="Update Available", 
                        message=f"New version {latest_version} available!\nCurrent version: {CURRENT_VERSION}",
                        button=["OK"]
                    )
                    test_tool_dialog.btn_update.setEnabled(True)
                    test_tool_dialog.btn_update.setStyleSheet(test_tool_dialog.update_btn_style_enabled)
                    return True
                else:
                    cmds.confirmDialog(
                        title="Up to Date", 
                        message="You are using the latest version.",
                        button=["OK"]
                    )
        return False
    except urllib.error.URLError as e:
        cmds.warning(f"[TEST] Update check failed: {str(e)}")
        cmds.confirmDialog(
            title="Network Error", 
            message=f"Network error: {str(e)}",
            button=["OK"]
        )
        return False
    except Exception as e:
        cmds.warning(f"[TEST] Update check failed: {str(e)}")
        cmds.confirmDialog(
            title="Update Check Failed", 
            message=f"Failed to check for updates: {str(e)}",
            button=["OK"]
        )
        return False

def update_tool():
    global test_tool_dialog
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(GITHUB_SCRIPT_URL, headers={"User-Agent": "Test-Tool"})
        with urllib.request.urlopen(req, context=ctx, timeout=TIMEOUT) as resp:
            if resp.getcode() == 200:
                tmp_path = LOCAL_SCRIPT_PATH + ".tmp"
                with open(tmp_path, "wb") as f:
                    f.write(resp.read())

                shutil.move(tmp_path, LOCAL_SCRIPT_PATH)
                
                cmds.confirmDialog(
                    title="Update Complete", 
                    message="Tool updated successfully. UI will restart automatically.",
                    button=["OK"]
                )
                
                test_tool_dialog.close()
                
                import importlib
                module_name = os.path.splitext(os.path.basename(LOCAL_SCRIPT_PATH))[0]
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])

                showUI()
                return True
    except urllib.error.URLError as e:
        cmds.warning(f"[TEST] Update failed: {e}")
        cmds.confirmDialog(
            title="Network Error", 
            message=f"Network error: {str(e)}",
            button=["OK"]
        )
    except Exception as e:
        cmds.warning(f"[TEST] Update failed: {e}")
        cmds.confirmDialog(
            title="Update Failed", 
            message=f"Error updating tool: {e}",
            button=["OK"]
        )
    return False

def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)

class TestToolUI(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super(TestToolUI, self).__init__(parent)
        self.setWindowTitle(f"Version Update Test Tool v{CURRENT_VERSION}")
        self.setFixedSize(400, 200)
        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        self.update_btn_style_disabled = """
            QPushButton { 
                background-color: #7f8c8d; 
                color: white; 
                border-radius: 6px; 
                padding: 8px;
            }
        """
        self.update_btn_style_enabled = """
            QPushButton { 
                background-color: #2ecc71; 
                color: white; 
                border-radius: 6px; 
                padding: 8px;
            }
            QPushButton:hover { 
                background-color: #27ae60; 
            }
            QPushButton:pressed { 
                background-color: #219653; 
            }
        """
        
        self.label_title = QtWidgets.QLabel(f"Version Update Test Tool")
        self.label_title.setAlignment(QtCore.Qt.AlignCenter)
        self.label_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.label_version = QtWidgets.QLabel(f"Current Version: {CURRENT_VERSION}")
        self.label_version.setAlignment(QtCore.Qt.AlignCenter)
        
        self.btn_check_updates = QtWidgets.QPushButton("Check for Updates")
        self.btn_check_updates.setStyleSheet("""
            QPushButton { 
                background-color: #3498db; 
                color: white; 
                border-radius: 6px; 
                padding: 8px;
            }
            QPushButton:hover { 
                background-color: #2980b9; 
            }
            QPushButton:pressed { 
                background-color: #1c5980; 
            }
        """)
        
        self.btn_update = QtWidgets.QPushButton("Update Tool")
        self.btn_update.setStyleSheet(self.update_btn_style_disabled)
        self.btn_update.setEnabled(False)

    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.addStretch(1)
        main_layout.addWidget(self.label_title)
        main_layout.addWidget(self.label_version)
        main_layout.addStretch(1)
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.btn_check_updates)
        button_layout.addWidget(self.btn_update)
        main_layout.addLayout(button_layout)
        
        main_layout.addStretch(2)

    def create_connections(self):
        self.btn_check_updates.clicked.connect(check_for_updates)
        self.btn_update.clicked.connect(update_tool)

def showUI():
    global test_tool_dialog 
    test_tool_dialog = TestToolUI()
    test_tool_dialog.show()
showUI()