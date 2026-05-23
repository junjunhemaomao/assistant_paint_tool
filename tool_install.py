from maya import cmds
from PySide2 import QtWidgets, QtCore
from shiboken2 import wrapInstance
import maya.OpenMayaUI as omui
import os, shutil, sys, urllib.request, ssl, importlib

VERSION = "1.0"
UPDATE_HOST = "http://139.155.152.122:8080"
GITHUB_BASE = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main"

URL_SCRIPT_SRV = f"{UPDATE_HOST}/Assistant_tool.py"
URL_SCRIPT_GH  = f"{GITHUB_BASE}/Assistant_tool.py"
URL_ICON_SRV   = f"{UPDATE_HOST}/3D_Modeling_Assistant.png"
URL_ICON_GH    = f"{GITHUB_BASE}/3D_Modeling_Assistant.png"
TIMEOUT, SSL_CTX = 30, ssl._create_unverified_context()

def _maya_scripts_dir():
    """Maya用户scripts目录，确保拖拽执行也能取到正确路径"""
    try:
        d = cmds.internalVar(userScriptDir=True)
        if d:
            return d
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents", "maya", "scripts")

SCRIPTS_DIR = _maya_scripts_dir()
os.makedirs(SCRIPTS_DIR, exist_ok=True)

INSTALL_DIR = os.path.join(SCRIPTS_DIR, "Assistant_tool")
os.makedirs(INSTALL_DIR, exist_ok=True)

MAIN_SCRIPT = os.path.join(INSTALL_DIR, "__init__.py")
ICON_FILE   = os.path.join(INSTALL_DIR, "icon.png")

def popup(title, msg):
    cmds.confirmDialog(title=title, message=msg, button=["OK"])

def _fetch_url(primary, fallback):
    """先尝试主URL（国内），失败则用备用URL（GitHub），每个URL最多重试3次"""
    for url in (primary, fallback):
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AssistantInstaller"})
                with urllib.request.urlopen(req, context=SSL_CTX, timeout=TIMEOUT) as r:
                    return r.read()
            except Exception:
                if attempt < 2:
                    import time
                    time.sleep(1)
                continue
    return None

def _download(primary_url, fallback_url, path):
    """下载文件（国内优先，GitHub备用）"""
    data = _fetch_url(primary_url, fallback_url)
    if data is None:
        raise Exception(f"All URLs failed for: {path}")
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    shutil.move(tmp, path)

def _create_shelf_button():
    """在 Maya 当前工具架上创建启动按钮"""
    shelf = cmds.shelfTabLayout("ShelfLayout", query=True, selectTab=True)
    if not shelf:
        return
    # 删除已存在的同名按钮
    existing = cmds.shelfLayout(shelf, query=True, childArray=True) or []
    for btn in existing:
        if cmds.shelfButton(btn, query=True, exists=True) and cmds.shelfButton(btn, query=True, label=True) == "Assistant":
            cmds.deleteUI(btn)
            break
    # 下载图标
    icon_path = "pythonFamily.png"
    try:
        _download(URL_ICON_SRV, URL_ICON_GH, ICON_FILE)
        icon_path = ICON_FILE
    except Exception:
        pass
    cmds.shelfButton(
        parent=shelf,
        image=icon_path,
        label="Assistant",
        annotation="3D Assistant Paint Tool",
        command='import Assistant_tool; Assistant_tool.showUI()',
        sourceType="python"
    )

def do_install(parent_ui):
    parent_ui.status_label.setText("Downloading...")
    QtCore.QCoreApplication.processEvents()
    try:
        _download(URL_SCRIPT_SRV, URL_SCRIPT_GH, MAIN_SCRIPT)
    except Exception as e:
        popup("Install Failed", f"Failed to download tool:\n{e}")
        parent_ui.status_label.setText("Failed.")
        return
    parent_ui.status_label.setText("Creating shelf button...")
    QtCore.QCoreApplication.processEvents()
    try:
        _create_shelf_button()
    except Exception as e:
        cmds.warning(f"Shelf button creation failed: {e}")
    popup("Install Complete", "Tool installed successfully!\nMaya shelf button created.")
    parent_ui.close()
    # 启动工具
    try:
        if "Assistant_tool" in sys.modules:
            importlib.reload(sys.modules["Assistant_tool"])
        else:
            import Assistant_tool
        # 模块级 showUI() 已在上一步触发，无需重复调用
    except Exception as e:
        cmds.warning(f"Failed to launch tool: {e}")

def maya_main():
    return wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)

class InstallerUI(QtWidgets.QDialog):
    def __init__(self, parent=maya_main()):
        super().__init__(parent)
        self.setWindowTitle(f"Assistant Paint Tool Installer v{VERSION}")
        self.setFixedSize(360, 160)

        self.title = QtWidgets.QLabel("Assistant Paint Tool", alignment=QtCore.Qt.AlignCenter)
        self.title.setStyleSheet("font-size:16px;font-weight:bold;")
        self.sub = QtWidgets.QLabel(f"Installer v{VERSION}", alignment=QtCore.Qt.AlignCenter)

        self.btn_install = QtWidgets.QPushButton("Install")
        self.btn_install.setStyleSheet(
            "QPushButton{background:#2ecc71;color:white;font-size:14px;border-radius:8px;padding:10px;}"
            "QPushButton:hover{background:#27ae60;}"
        )
        self.btn_install.clicked.connect(lambda: do_install(self))

        self.status_label = QtWidgets.QLabel("Ready to install.", alignment=QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("color:#888;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(self.title)
        layout.addWidget(self.sub)
        layout.addStretch(1)
        layout.addWidget(self.btn_install)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

dialog = None

def showUI():
    global dialog
    if dialog is not None:
        dialog.close()
        dialog.deleteLater()
    dialog = InstallerUI()
    dialog.show()

def onMayaDroppedPythonFile(path):
    """拖入Maya时的入口，复用showUI"""
    showUI()

showUI()
