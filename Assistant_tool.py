# -*- coding: utf-8 -*-
from maya import cmds, mel
from PySide2 import QtWidgets, QtCore, QtGui
from shiboken2 import wrapInstance
import maya.OpenMayaUI as omui
import requests
import os
import shutil
import sys
import threading
import time
import importlib

# ------------------------------
# 当前工具版本
# ------------------------------
CURRENT_VERSION = "3.5"

# GitHub 文件路径
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/version.txt"
GITHUB_SCRIPT_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/Assistant_tool.py"
GITHUB_BANNER_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/3D_Modeling_Assistant.png"

# ------------------------------
# 本地脚本路径（动态获取）
# ------------------------------
try:
    LOCAL_SCRIPT_PATH = os.path.abspath(__file__)
except NameError:
    # 在 Maya 控制台直接运行，__file__ 不存在
    LOCAL_SCRIPT_PATH = os.path.abspath(sys.argv[0])

# ------------------------------
# Tool Functions
# ------------------------------
def universal_merge_to_center(*args):
    sel = cmds.ls(selection=True, flatten=True)
    vtx_list = []
    for comp in sel:
        if ".vtx[" in comp:
            vtx_list.append(comp)
        elif ".e[" in comp:
            vtx_list.extend(cmds.polyListComponentConversion(comp, fromEdge=True, toVertex=True))
        elif ".f[" in comp:
            vtx_list.extend(cmds.polyListComponentConversion(comp, fromFace=True, toVertex=True))
        elif "." not in comp:
            vtx_list.extend(cmds.ls(comp + ".vtx[*]", flatten=True))
    vtx_list = list(set(cmds.ls(vtx_list, flatten=True)))
    positions = [cmds.pointPosition(v, world=True) for v in vtx_list]
    if not positions:
        return
    center = [sum(p[i] for p in positions) / len(positions) for i in range(3)]
    for vtx in vtx_list:
        cmds.move(center[0], center[1], center[2], vtx, worldSpace=True, absolute=True)
    mel.eval('polyMergeVertex -d 0.000001 -ch 1;')
    cmds.select(clear=True)

def target_weld(*args):
    sel = cmds.ls(orderedSelection=True, flatten=True)
    if len(sel) < 2:
        cmds.warning("Please select two vertices or objects for target weld")
        return
    src, tgt = sel[0], sel[1]
    pos = cmds.pointPosition(tgt, world=True)
    cmds.move(pos[0], pos[1], pos[2], src, worldSpace=True, absolute=True)
    mel.eval('polyMergeVertex -d 0.000001 -ch 1;')
    cmds.select(clear=True)

def connect_vertices(*args):
    mel.eval('polyConnectComponents;')
    cmds.select(clear=True)

def delete_vertices(*args):
    mel.eval('DeleteVertex;')

def bridge_edges(*args):
    mel.eval('polyBridgeEdge -divisions 0 -ch 1;')
    cmds.select(clear=True)

def insert_edge_loop(*args):
    mel.eval('InsertEdgeLoopTool;')

def fill_hole(*args):
    mel.eval('polyCloseBorder -ch 1;')
    cmds.select(clear=True)

def multi_cut(*args):
    mel.eval('MultiCutTool;')

def extrude_faces(*args):
    mel.eval('PolyExtrude;')

def bevel_edges(*args):
    mel.eval('BevelPolygon;')

def separate_objects(*args):
    sel = cmds.ls(selection=True)
    if not sel:
        cmds.warning("No objects selected")
        return
    new_objs = mel.eval('polySeparate;')
    for obj in new_objs:
        cmds.delete(obj, ch=True)
        cmds.centerPivot(obj)
    cmds.select(clear=True)

def combine_objects(*args):
    sel = cmds.ls(selection=True)
    if len(sel) < 2:
        cmds.warning("Please select two or more objects to combine")
        return
    result = mel.eval('polyUnite -ch 0 -mergeUVSets 1;')
    merged_obj = result[0] if isinstance(result, list) else result
    cmds.delete(merged_obj, ch=True)
    cmds.centerPivot(merged_obj)
    cmds.select(clear=True)

def detach_selected_faces(*args):
    orig_face_sel = cmds.filterExpand(sm=34, ex=1)
    if not orig_face_sel:
        cmds.warning("No faces selected")
        return
    orig_obj_shape = cmds.listRelatives(orig_face_sel[0], parent=True)
    orig_obj = cmds.listRelatives(orig_obj_shape[0], parent=True)
    face_num = [face.split(".")[1] for face in orig_face_sel]
    new_obj = cmds.duplicate(orig_obj[0], un=True)[0]
    cmds.delete(new_obj, ch=True)
    new_face_sel = ["{0}.{1}".format(new_obj, f) for f in face_num]
    cmds.delete(orig_face_sel)
    all_faces = cmds.ls("{0}.f[*]".format(new_obj), flatten=True)
    faces_to_delete = list(set(all_faces) - set(new_face_sel))
    if faces_to_delete:
        cmds.delete(faces_to_delete)
    cmds.select(new_obj)

# ------------------------------
# Update Functions
# ------------------------------
def check_for_updates(*args):
    global modeling_tools_dialog
    try:
        response = requests.get(GITHUB_VERSION_URL)
        if response.status_code == 200:
            latest_version = response.text.strip()
            if latest_version != CURRENT_VERSION:
                cmds.confirmDialog(title="Update Available",
                                   message="New version {} available!".format(latest_version),
                                   button=["OK"])
                modeling_tools_dialog.btn_update.setEnabled(True)
                modeling_tools_dialog.btn_update.setStyleSheet(modeling_tools_dialog.btn_style)
            else:
                cmds.confirmDialog(title="Up to Date", message="You are using the latest version.", button=["OK"])
        else:
            cmds.warning("Failed to fetch version info from GitHub.")
    except:
        cmds.warning("Error checking updates from GitHub.")

def update_tool(*args):
    global modeling_tools_dialog
    try:
        response = requests.get(GITHUB_SCRIPT_URL, stream=True)
        if response.status_code == 200:
            tmp_path = LOCAL_SCRIPT_PATH + ".tmp"
            with open(tmp_path, "wb") as f:
                f.write(response.content)
            shutil.move(tmp_path, LOCAL_SCRIPT_PATH)
            cmds.confirmDialog(title="Update Complete", message="Tool updated successfully.", button=["OK"])
            try:
                modeling_tools_dialog.close()
                modeling_tools_dialog.deleteLater()
            except:
                pass
            def reload_ui():
                time.sleep(0.2)
                if os.path.dirname(LOCAL_SCRIPT_PATH) not in sys.path:
                    sys.path.append(os.path.dirname(LOCAL_SCRIPT_PATH))
                module_name = os.path.splitext(os.path.basename(LOCAL_SCRIPT_PATH))[0]
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                else:
                    importlib.import_module(module_name)
            threading.Thread(target=reload_ui).start()
        else:
            cmds.warning("Failed to download latest tool script.")
    except Exception as e:
        cmds.warning("Error updating tool: {}".format(e))

# ------------------------------
# PySide2 UI
# ------------------------------
def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)  # 兼容 Python 2/3

class ModelingToolsUI(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super(ModelingToolsUI, self).__init__(parent)
        self.setWindowTitle("3D Modeling Assistant Tools v{}".format(CURRENT_VERSION))
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        font = QtGui.QFont("Arial", 10)
        self.btn_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1c5980;
            }
        """

        # Banner Image 自动从 GitHub 加载
        self.banner_label = QtWidgets.QLabel()
        self.banner_label.setAlignment(QtCore.Qt.AlignCenter)
        self.banner_label.setCursor(QtCore.Qt.PointingHandCursor)
        try:
            response = requests.get(GITHUB_BANNER_URL)
            if response.status_code == 200:
                image_data = response.content
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(image_data)
                pixmap = pixmap.scaledToWidth(380, QtCore.Qt.SmoothTransformation)
                self.banner_label.setPixmap(pixmap)
            else:
                self.banner_label.setText("Banner image not found")
        except:
            self.banner_label.setText("Failed to load banner image")

        # 功能按钮
        self.btn_merge_center = QtWidgets.QPushButton("Merge to Center")
        self.btn_target_weld = QtWidgets.QPushButton("Target Weld")
        self.btn_connect_vertices = QtWidgets.QPushButton("Connect Vertices")
        self.btn_delete_vertices = QtWidgets.QPushButton("Delete Vertices")
        self.btn_bridge_edges = QtWidgets.QPushButton("Bridge Edges")
        self.btn_insert_edge_loop = QtWidgets.QPushButton("Insert Edge Loop")
        self.btn_multi_cut = QtWidgets.QPushButton("Multi-Cut")
        self.btn_fill_hole = QtWidgets.QPushButton("Fill Hole")
        self.btn_bevel_edges = QtWidgets.QPushButton("Bevel Edges")
        self.btn_extrude_faces = QtWidgets.QPushButton("Extrude Faces")
        self.btn_separate_objects = QtWidgets.QPushButton("Separate Objects")
        self.btn_combine_objects = QtWidgets.QPushButton("Combine Objects")
        self.btn_detach_faces = QtWidgets.QPushButton("Detach Selected Faces")

        # Update 按钮
        self.btn_check_updates = QtWidgets.QPushButton("Check for Updates")
        self.btn_update = QtWidgets.QPushButton("Update")
        self.btn_update.setEnabled(False)
        self.btn_update.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: white;
            }
        """)

        # Apply styles
        for btn in [self.btn_merge_center, self.btn_target_weld, self.btn_connect_vertices,
                    self.btn_delete_vertices, self.btn_bridge_edges, self.btn_insert_edge_loop,
                    self.btn_multi_cut, self.btn_fill_hole, self.btn_bevel_edges, self.btn_extrude_faces,
                    self.btn_separate_objects, self.btn_combine_objects, self.btn_detach_faces,
                    self.btn_check_updates]:
            btn.setFont(font)
            btn.setStyleSheet(self.btn_style)
        self.btn_update.setFont(font)  # Update 用单独灰色样式

        # Footer
        self.label_footer = QtWidgets.QLabel("3D Modeling Assistant Tools v{}".format(CURRENT_VERSION))
        self.label_footer.setAlignment(QtCore.Qt.AlignCenter)
        self.label_footer.setFont(QtGui.QFont("Arial", 9))
        self.label_footer.setStyleSheet("color: gray;")

    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.addWidget(self.banner_label)

        def add_group(title, buttons):
            group = QtWidgets.QGroupBox(title)
            layout = QtWidgets.QVBoxLayout()
            layout.setSpacing(5)
            for btn in buttons:
                layout.addWidget(btn)
            group.setLayout(layout)
            main_layout.addWidget(group)

        add_group("Universal", [self.btn_merge_center])
        add_group("Vertex Operations", [self.btn_target_weld, self.btn_connect_vertices, self.btn_delete_vertices])
        add_group("Edge Operations", [self.btn_bridge_edges, self.btn_insert_edge_loop, self.btn_multi_cut,
                                      self.btn_fill_hole, self.btn_bevel_edges])
        add_group("Face Operations", [self.btn_extrude_faces])
        add_group("Object Operations", [self.btn_separate_objects, self.btn_combine_objects, self.btn_detach_faces])
        add_group("Updates", [self.btn_check_updates, self.btn_update])
        main_layout.addWidget(self.label_footer)

    def create_connections(self):
        self.btn_merge_center.clicked.connect(universal_merge_to_center)
        self.btn_target_weld.clicked.connect(target_weld)
        self.btn_connect_vertices.clicked.connect(connect_vertices)
        self.btn_delete_vertices.clicked.connect(delete_vertices)
        self.btn_bridge_edges.clicked.connect(bridge_edges)
        self.btn_insert_edge_loop.clicked.connect(insert_edge_loop)
        self.btn_multi_cut.clicked.connect(multi_cut)
        self.btn_fill_hole.clicked.connect(fill_hole)
        self.btn_bevel_edges.clicked.connect(bevel_edges)
        self.btn_extrude_faces.clicked.connect(extrude_faces)
        self.btn_separate_objects.clicked.connect(separate_objects)
        self.btn_combine_objects.clicked.connect(combine_objects)
        self.btn_detach_faces.clicked.connect(detach_selected_faces)
        self.btn_check_updates.clicked.connect(check_for_updates)
        self.btn_update.clicked.connect(update_tool)
        self.banner_label.mousePressEvent = self.open_github

    def open_github(self, event):
        import webbrowser
        webbrowser.open("https://github.com/junjunhemaomao/assistant_paint_tool")

# ------------------------------
# Show UI
# ------------------------------
def show_ui():
    global modeling_tools_dialog
    try:
        modeling_tools_dialog.close()
        modeling_tools_dialog.deleteLater()
    except:
        pass
    modeling_tools_dialog = ModelingToolsUI()
    modeling_tools_dialog.show()

show_ui()
