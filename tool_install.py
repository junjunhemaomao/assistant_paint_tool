from maya import cmds
from PySide2 import QtWidgets, QtCore
from shiboken2 import wrapInstance
import maya.OpenMayaUI as omui
import os, shutil, sys, urllib.request, ssl, importlib

dialog = None
VERSION = "0.9"
URL_VERSION = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/version.txt"
URL_SCRIPT = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/Assistant_tool.py"
TIMEOUT, SSL_CTX = 10, ssl._create_unverified_context()

try:
    LOCAL_PATH = os.path.abspath(__file__)
except NameError:
    LOCAL_PATH = os.path.abspath(sys.argv[0])

def popup(title, msg): cmds.confirmDialog(title=title, message=msg, button=["OK"])

def check_update():
    global dialog
    try:
        req = urllib.request.Request(URL_VERSION, headers={"User-Agent": "Assistant"})
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=TIMEOUT) as r:
            latest = r.read().decode().strip()
            if latest != VERSION:
                popup("Update Available", f"New {latest} available!\nCurrent: {VERSION}")
                dialog.btn_update.setEnabled(True)
                dialog.btn_update.setStyleSheet(dialog.style_enabled)
            else:
                popup("Up to Date", "You are using the latest version.")
    except Exception as e:
        popup("Update Check Failed", str(e))

def do_update():
    global dialog
    try:
        req = urllib.request.Request(URL_SCRIPT, headers={"User-Agent": "Assistant"})
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=TIMEOUT) as r:
            tmp = LOCAL_PATH + ".tmp"
            with open(tmp, "wb") as f: f.write(r.read())
            shutil.move(tmp, LOCAL_PATH)
        popup("Update Complete", "Tool updated. UI will restart.")
        dialog.close()
        importlib.reload(sys.modules[os.path.splitext(os.path.basename(LOCAL_PATH))[0]])
        showUI()
    except Exception as e:
        popup("Update Failed", str(e))

def maya_main(): return wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)

class AssistantUI(QtWidgets.QDialog):
    def __init__(self, parent=maya_main()):
        super().__init__(parent)
        self.setWindowTitle(f"Assistant Install Tool v{VERSION}")
        self.setFixedSize(380, 180)

        self.style_enabled = "QPushButton{background:#2ecc71;color:white;border-radius:6px;padding:8px;}"
        style_blue = "QPushButton{background:#3498db;color:white;border-radius:6px;padding:8px;}"
        style_disabled = "QPushButton{background:#7f8c8d;color:white;border-radius:6px;padding:8px;}"

        title = QtWidgets.QLabel("Assistant Install Tool", alignment=QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size:16px;font-weight:bold;")
        version = QtWidgets.QLabel(f"Current Version: {VERSION}", alignment=QtCore.Qt.AlignCenter)

        self.btn_check = QtWidgets.QPushButton("Check for Updates"); self.btn_check.setStyleSheet(style_blue)
        self.btn_update = QtWidgets.QPushButton("Update Tool"); self.btn_update.setStyleSheet(style_disabled); self.btn_update.setEnabled(False)

        layout = QtWidgets.QVBoxLayout(self); layout.addStretch(1)
        layout.addWidget(title); layout.addWidget(version); layout.addStretch(1)
        h = QtWidgets.QHBoxLayout(); h.addWidget(self.btn_check); h.addWidget(self.btn_update); layout.addLayout(h); layout.addStretch(2)

        self.btn_check.clicked.connect(check_update)
        self.btn_update.clicked.connect(do_update)

def showUI():
    global dialog
    dialog = AssistantUI(); dialog.show()

showUI()