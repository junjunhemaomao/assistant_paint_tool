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
    LOCAL_SCRIPT_PATH = os.path.abspath(sys.argv[0])

# ------------------------------
# 预设颜色列表
# ------------------------------
COLOR_PRESETS = [
    # 5个彩色
    {"name": "红色", "rgb": (1.0, 0.0, 0.0)},
    {"name": "绿色", "rgb": (0.0, 1.0, 0.0)},
    {"name": "蓝色", "rgb": (0.0, 0.5, 1.0)},
    {"name": "黄色", "rgb": (1.0, 1.0, 0.0)},
    {"name": "紫色", "rgb": (1.0, 0.0, 1.0)},

    # 5个灰色
    {"name": "浅灰", "rgb": (0.9, 0.9, 0.9)},
    {"name": "中灰", "rgb": (0.7, 0.7, 0.7)},
    {"name": "标准灰", "rgb": (0.5, 0.5, 0.5)},
    {"name": "深灰", "rgb": (0.3, 0.3, 0.3)},
    {"name": "暗灰", "rgb": (0.1, 0.1, 0.1)}
]

# ------------------------------
# 建模基础函数
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
# 材质相关函数
# ------------------------------
def create_arnold_material(color_info):
    """创建Arnold材质并返回材质组"""
    name = color_info["name"]
    rgb = color_info["rgb"]
    
    material = cmds.shadingNode('aiStandardSurface', asShader=True, name=f'{name}_mat')
    cmds.setAttr(material + '.base', 1.0)
    cmds.setAttr(material + '.baseColor', rgb[0], rgb[1], rgb[2], type='double3')
    
    if name in ["浅灰", "中灰", "标准灰", "深灰", "暗灰"]:
        cmds.setAttr(material + '.specular', 0.2)
        cmds.setAttr(material + '.specularRoughness', 0.5)
    else:
        cmds.setAttr(material + '.specular', 0.5)
        cmds.setAttr(material + '.specularRoughness', 0.3)
    
    shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=material+'SG')
    cmds.connectAttr(material + '.outColor', shading_group + '.surfaceShader', force=True)
    
    return shading_group

def assign_material_to_selection(color_info):
    selected = cmds.ls(selection=True)
    if not selected:
        cmds.warning("请先选择对象！")
        return
    
    shading_group = create_arnold_material(color_info)
    cmds.sets(selected, forceElement=shading_group)
    print(f"已将 '{color_info['name']}' 材质赋予 {len(selected)} 个对象")

def assign_custom_color_to_selection():
    selected = cmds.ls(selection=True)
    if not selected:
        cmds.warning("请先选择对象！")
        return
    
    result = cmds.colorEditor()
    if cmds.colorEditor(query=True, result=True):
        rgb = cmds.colorEditor(query=True, rgb=True)
        custom_color = {
            "name": f"自定义颜色({rgb[0]:.2f},{rgb[1]:.2f},{rgb[2]:.2f})",
            "rgb": rgb
        }
        shading_group = create_arnold_material(custom_color)
        cmds.sets(selected, forceElement=shading_group)
        print(f"已将自定义颜色材质赋予 {len(selected)} 个对象")

def open_hypershade():
    hypershade_window = 'hyperShadePanel'
    if cmds.window(hypershade_window, exists=True):
        cmds.showWindow(hypershade_window)
    else:
        cmds.HypershadeWindow()

# ------------------------------
# 更新函数
# ------------------------------
def check_for_updates(*args):
    global modeling_tools_dialog
    try:
        response = requests.get(GITHUB_VERSION_URL)
        if response.status_code == 200:
            latest_version = response.text.strip()
            if latest_version != CURRENT_VERSION:
                cmds.confirmDialog(title="Update Available", message="New version {} available!".format(latest_version), button=["OK"])
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
# UI 类 (整合版本)
# ------------------------------
def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)

class ModelingToolsUI(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super(ModelingToolsUI, self).__init__(parent)
        self.setWindowTitle("3D Assistant Tools v{}".format(CURRENT_VERSION))
        self.setMinimumWidth(500)
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.camera_snapshots = {}
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
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #1c5980; }
        """
        # Banner
        self.banner_label = QtWidgets.QLabel()
        self.banner_label.setAlignment(QtCore.Qt.AlignCenter)
        try:
            response = requests.get(GITHUB_BANNER_URL)
            if response.status_code == 200:
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(response.content)
                pixmap = pixmap.scaledToWidth(460, QtCore.Qt.SmoothTransformation)
                self.banner_label.setPixmap(pixmap)
            else:
                self.banner_label.setText("Banner not found")
        except:
            self.banner_label.setText("Failed to load banner")

        # Tabs
        self.tabs = QtWidgets.QTabWidget()

        # --- 建模按钮 ---
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

        # --- 材质按钮 ---
        self.btn_open_hypershade = QtWidgets.QPushButton("Open Hypershade")
        self.btn_custom_color = QtWidgets.QPushButton("Custom Color")

        # 颜色预设按钮
        self.color_buttons = []
        for i, color in enumerate(COLOR_PRESETS):
            btn = QtWidgets.QPushButton()
            qcolor = QtGui.QColor(int(color["rgb"][0]*255), int(color["rgb"][1]*255), int(color["rgb"][2]*255))
            style = f"background-color: rgb({int(color['rgb'][0]*255)}, {int(color['rgb'][1]*255)}, {int(color['rgb'][2]*255)});"
            if color["name"] in ["深灰", "暗灰"]:
                style += "color: white;"
            btn.setStyleSheet(style)
            btn.setFixedSize(70, 30)
            self.color_buttons.append(btn)

        # --- 其他功能按钮 ---
        self.btn_create_persp_cam = QtWidgets.QPushButton("Create Perspective Cam")
        self.btn_three_point = QtWidgets.QPushButton("3-Point Lighting")
        self.btn_open_render_view = QtWidgets.QPushButton("Open Arnold RenderView")
        self.btn_check_updates = QtWidgets.QPushButton("Check for Updates")
        self.btn_update = QtWidgets.QPushButton("Update")
        self.btn_update.setEnabled(False)

        # Footer
        self.label_footer = QtWidgets.QLabel("3D Assistant Tools v{}".format(CURRENT_VERSION))
        self.label_footer.setAlignment(QtCore.Qt.AlignCenter)
        self.label_footer.setStyleSheet("color: gray;")

        # 相机快照按钮
        self.btn_save_snapshot = QtWidgets.QPushButton("保存当前快照")
        self.btn_restore_snapshot = QtWidgets.QPushButton("恢复快照")
        self.btn_newcam_from_snapshot = QtWidgets.QPushButton("新建相机并应用快照")
        self.btn_delete_snapshot = QtWidgets.QPushButton("删除快照")
        self.list_snapshots = QtWidgets.QListWidget()
        self.list_snapshots.setFixedHeight(100)

        # 应用按钮样式
        for btn in [self.btn_merge_center, self.btn_target_weld, self.btn_connect_vertices,
                    self.btn_delete_vertices, self.btn_bridge_edges, self.btn_insert_edge_loop,
                    self.btn_multi_cut, self.btn_fill_hole, self.btn_bevel_edges, self.btn_extrude_faces,
                    self.btn_separate_objects, self.btn_combine_objects, self.btn_detach_faces,
                    self.btn_open_hypershade, self.btn_custom_color,
                    self.btn_create_persp_cam, self.btn_three_point, self.btn_open_render_view,
                    self.btn_check_updates, self.btn_save_snapshot, self.btn_restore_snapshot,
                    self.btn_newcam_from_snapshot, self.btn_delete_snapshot]:
            btn.setFont(font)
            btn.setStyleSheet(self.btn_style)
        self.btn_update.setFont(font)

    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.banner_label)
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.btn_check_updates)
        main_layout.addWidget(self.btn_update)
        main_layout.addWidget(self.label_footer)

        def add_group(title, buttons):
            group = QtWidgets.QGroupBox(title)
            layout = QtWidgets.QVBoxLayout()
            for b in buttons: layout.addWidget(b)
            group.setLayout(layout)
            return group

        # --- Modeling Tab ---
        modeling_layout = QtWidgets.QVBoxLayout()
        modeling_layout.addWidget(add_group("Universal", [self.btn_merge_center]))
        modeling_layout.addWidget(add_group("Vertex Operations", [self.btn_target_weld, self.btn_connect_vertices, self.btn_delete_vertices]))
        modeling_layout.addWidget(add_group("Edge Operations", [self.btn_bridge_edges, self.btn_insert_edge_loop, self.btn_multi_cut,
                                      self.btn_fill_hole, self.btn_bevel_edges]))
        modeling_layout.addWidget(add_group("Face Operations", [self.btn_extrude_faces]))
        modeling_layout.addWidget(add_group("Object Operations", [self.btn_separate_objects, self.btn_combine_objects, self.btn_detach_faces]))
        modeling_page = QtWidgets.QWidget(); modeling_page.setLayout(modeling_layout)

        # --- Materials Tab ---
        mat_layout = QtWidgets.QVBoxLayout()
        color_group = QtWidgets.QGroupBox("Color Presets")
        color_group_layout = QtWidgets.QVBoxLayout()
        color_row1 = QtWidgets.QHBoxLayout(); color_row2 = QtWidgets.QHBoxLayout()
        for i in range(5): color_row1.addWidget(self.color_buttons[i])
        for i in range(5,10): color_row2.addWidget(self.color_buttons[i])
        color_group_layout.addLayout(color_row1)
        color_group_layout.addLayout(color_row2)
        color_group_layout.addWidget(self.btn_custom_color)
        color_group_layout.addWidget(QtWidgets.QLabel("提示: 先选择对象，然后点击颜色按钮赋予材质"))
        color_group.setLayout(color_group_layout)
        mat_layout.addWidget(color_group)
        mat_layout.addWidget(add_group("Utilities", [self.btn_open_hypershade]))
        mat_page = QtWidgets.QWidget(); mat_page.setLayout(mat_layout)

        # --- Camera Tab ---
        cam_layout = QtWidgets.QVBoxLayout()
        cam_layout.addWidget(add_group("Camera", [self.btn_create_persp_cam]))
        snapshot_group = QtWidgets.QGroupBox("Camera Snapshots")
        snapshot_layout = QtWidgets.QVBoxLayout()
        snapshot_layout.addWidget(self.btn_save_snapshot)
        snapshot_layout.addWidget(self.list_snapshots)
        snapshot_layout.addWidget(self.btn_restore_snapshot)
        snapshot_layout.addWidget(self.btn_newcam_from_snapshot)
        snapshot_layout.addWidget(self.btn_delete_snapshot)
        snapshot_group.setLayout(snapshot_layout)
        cam_layout.addWidget(snapshot_group)
        cam_page = QtWidgets.QWidget(); cam_page.setLayout(cam_layout)

        # --- Lighting Tab ---
        light_layout = QtWidgets.QVBoxLayout(); light_layout.addWidget(add_group("Lighting", [self.btn_three_point]))
        light_page = QtWidgets.QWidget(); light_page.setLayout(light_layout)

        # --- Rendering Tab ---
        render_layout = QtWidgets.QVBoxLayout(); render_layout.addWidget(add_group("Render", [self.btn_open_render_view]))
        render_page = QtWidgets.QWidget(); render_page.setLayout(render_layout)

        # Add Tabs
        self.tabs.addTab(modeling_page, "Modeling")
        self.tabs.addTab(cam_page, "Camera")
        self.tabs.addTab(mat_page, "Materials")
        self.tabs.addTab(light_page, "Lighting")
        self.tabs.addTab(render_page, "Rendering")

    def create_connections(self):
        # Modeling
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

        # Materials
        self.btn_open_hypershade.clicked.connect(open_hypershade)
        self.btn_custom_color.clicked.connect(assign_custom_color_to_selection)
        for i, btn in enumerate(self.color_buttons):
            btn.clicked.connect(lambda checked=False, idx=i: assign_material_to_selection(COLOR_PRESETS[idx]))

        # Other
        self.btn_create_persp_cam.clicked.connect(self.create_perspective_camera)
        self.btn_three_point.clicked.connect(self.create_three_point_light)
        self.btn_open_render_view.clicked.connect(self.open_arnold_render_view)
        self.btn_check_updates.clicked.connect(check_for_updates)
        self.btn_update.clicked.connect(update_tool)

        # Camera Snapshots
        self.btn_save_snapshot.clicked.connect(self.save_camera_snapshot)
        self.btn_restore_snapshot.clicked.connect(self.restore_camera_snapshot)
        self.btn_newcam_from_snapshot.clicked.connect(self.create_camera_from_snapshot)
        self.btn_delete_snapshot.clicked.connect(self.delete_camera_snapshot)

    # --- Camera Snapshot Functions ---
    def save_camera_snapshot(self):
        cam = cmds.ls(selection=True, type="transform")
        if not cam:
            cmds.warning("请先选择一个摄像机")
            return
        cam = cam[0]
        shape = cmds.listRelatives(cam, shapes=True, type="camera")
        if not shape:
            cmds.warning("选择的不是摄像机")
            return
        shape = shape[0]

        data = {
            "translate": cmds.getAttr(cam + ".translate")[0],
            "rotate": cmds.getAttr(cam + ".rotate")[0],
            "focalLength": cmds.getAttr(shape + ".focalLength")
        }
        snapshot_name = f"{cam}_Snapshot{len(self.camera_snapshots)+1}"
        self.camera_snapshots[snapshot_name] = (cam, data)
        self.list_snapshots.addItem(snapshot_name)
        print(f"已保存快照: {snapshot_name}")

    def restore_camera_snapshot(self):
        item = self.list_snapshots.currentItem()
        if not item:
            cmds.warning("请选择一个快照")
            return
        name = item.text()
        if name not in self.camera_snapshots:
            cmds.warning("快照不存在")
            return
        cam, data = self.camera_snapshots[name]
        if not cmds.objExists(cam):
            cmds.warning("原相机已不存在")
            return
        cmds.setAttr(cam + ".translate", *data["translate"], type="double3")
        cmds.setAttr(cam + ".rotate", *data["rotate"], type="double3")
        shape = cmds.listRelatives(cam, shapes=True, type="camera")[0]
        cmds.setAttr(shape + ".focalLength", data["focalLength"])
        cmds.select(cam)
        print(f"已恢复快照: {name}")

    def create_camera_from_snapshot(self):
        item = self.list_snapshots.currentItem()
        if not item:
            cmds.warning("请选择一个快照")
            return
        name = item.text()
        cam, data = self.camera_snapshots[name]
        new_cam, shape = cmds.camera()
        cmds.setAttr(new_cam + ".translate", *data["translate"], type="double3")
        cmds.setAttr(new_cam + ".rotate", *data["rotate"], type="double3")
        cmds.setAttr(shape + ".focalLength", data["focalLength"])
        cmds.select(new_cam)
        print(f"已基于快照新建相机: {new_cam}")

    def delete_camera_snapshot(self):
        item = self.list_snapshots.currentItem()
        if not item:
            cmds.warning("请选择一个快照删除")
            return
        name = item.text()
        del self.camera_snapshots[name]
        self.list_snapshots.takeItem(self.list_snapshots.currentRow())
        print(f"已删除快照: {name}")

    # --- Example Functions ---
    def create_perspective_camera(self):
        cam, shape = cmds.camera()
        cmds.setAttr(cam + ".translateZ", 30)
        cmds.setAttr(shape + ".focalLength", 35)
        cmds.select(cam)

    def create_three_point_light(self):
        key = cmds.directionalLight(name="KeyLight")
        cmds.setAttr(cmds.listRelatives(key, p=True)[0] + ".translate", 10, 10, 10, type="double3")
        fill = cmds.directionalLight(name="FillLight")
        cmds.setAttr(cmds.listRelatives(fill, p=True)[0] + ".translate", -10, 5, 10, type="double3")
        back = cmds.directionalLight(name="BackLight")
        cmds.setAttr(cmds.listRelatives(back, p=True)[0] + ".translate", 0, 10, -10, type="double3")

    def open_arnold_render_view(self):
        try:
            mel.eval("ArnoldRenderViewWindow;")
        except:
            cmds.warning("Arnold not available")

# ------------------------------
# Show UI
# ------------------------------
def showUI():
    global modeling_tools_dialog
    try:
        modeling_tools_dialog.close()
        modeling_tools_dialog.deleteLater()
    except:
        pass
    modeling_tools_dialog = ModelingToolsUI()
    modeling_tools_dialog.show()
showUI()