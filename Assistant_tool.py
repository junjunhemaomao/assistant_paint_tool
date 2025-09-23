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
import webbrowser

CURRENT_VERSION = "1.0"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/version.txt"
GITHUB_SCRIPT_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/Assistant_tool.py"
GITHUB_BANNER_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/3D_Modeling_Assistant.png"
GITHUB_PAGE_URL = "https://github.com/junjunhemaomao/assistant_paint_tool"

try:
    LOCAL_SCRIPT_PATH = os.path.abspath(__file__)
except NameError:
    LOCAL_SCRIPT_PATH = os.path.abspath(sys.argv[0])

COLOR_PRESETS = [
    {"name": "Red", "rgb": (1.0, 0.0, 0.0)},
    {"name": "Green", "rgb": (0.0, 1.0, 0.0)},
    {"name": "Blue", "rgb": (0.0, 0.5, 1.0)},
    {"name": "Yellow", "rgb": (1.0, 1.0, 0.0)},
    {"name": "Purple", "rgb": (1.0, 0.0, 1.0)},
    {"name": "Light Gray", "rgb": (0.9, 0.9, 0.9)},
    {"name": "Medium Gray", "rgb": (0.7, 0.7, 0.7)},
    {"name": "Standard Gray", "rgb": (0.5, 0.5, 0.5)},
    {"name": "Dark Gray", "rgb": (0.3, 0.3, 0.3)},
    {"name": "Charcoal", "rgb": (0.1, 0.1, 0.1)}
]

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
    if not positions: return
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

def connect_vertices(*args): mel.eval('polyConnectComponents;')
def delete_vertices(*args): mel.eval('DeleteVertex;')
def bridge_edges(*args): mel.eval('polyBridgeEdge -divisions 0 -ch 1;')
def insert_edge_loop(*args): mel.eval('InsertEdgeLoopTool;')
def fill_hole(*args): mel.eval('polyCloseBorder -ch 1;')
def multi_cut(*args): mel.eval('MultiCutTool;')
def extrude_faces(*args): mel.eval('PolyExtrude;')
def bevel_edges(*args): mel.eval('BevelPolygon;')

def separate_objects(*args):
    sel = cmds.ls(selection=True)
    if not sel: return
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
    if not orig_face_sel: return
    orig_obj_shape = cmds.listRelatives(orig_face_sel[0], parent=True)
    orig_obj = cmds.listRelatives(orig_obj_shape[0], parent=True)
    face_num = [face.split(".")[1] for face in orig_face_sel]
    new_obj = cmds.duplicate(orig_obj[0], un=True)[0]
    cmds.delete(new_obj, ch=True)
    new_face_sel = [f"{new_obj}.{f}" for f in face_num]
    cmds.delete(orig_face_sel)
    all_faces = cmds.ls(f"{new_obj}.f[*]", flatten=True)
    faces_to_delete = list(set(all_faces) - set(new_face_sel))
    if faces_to_delete: cmds.delete(faces_to_delete)
    cmds.select(new_obj)

def create_arnold_material(color_info):
    name, rgb = color_info["name"], color_info["rgb"]
    material = cmds.shadingNode('aiStandardSurface', asShader=True, name=f'{name}_mat')
    cmds.setAttr(material + '.base', 1.0)
    cmds.setAttr(material + '.baseColor', rgb[0], rgb[1], rgb[2], type='double3')
    
    if "Gray" in name:
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
    if not selected: return
    shading_group = create_arnold_material(color_info)
    cmds.sets(selected, forceElement=shading_group)

def assign_custom_color_to_selection():
    selected = cmds.ls(selection=True)
    if not selected: return
    result = cmds.colorEditor()
    if cmds.colorEditor(query=True, result=True):
        rgb = cmds.colorEditor(query=True, rgb=True)
        custom_color = {"name": f"Custom({rgb[0]:.2f},{rgb[1]:.2f},{rgb[2]:.2f})", "rgb": rgb}
        shading_group = create_arnold_material(custom_color)
        cmds.sets(selected, forceElement=shading_group)

def open_hypershade():
    hypershade_window = 'hyperShadePanel'
    if cmds.window(hypershade_window, exists=True):
        cmds.showWindow(hypershade_window)
    else:
        cmds.HypershadeWindow()

def create_perspective_camera():
    cam, shape = cmds.camera()
    cmds.setAttr(cam + ".translateZ", 30)
    cmds.setAttr(shape + ".focalLength", 35)
    cmds.select(cam)

def save_camera_snapshot(snapshot_dict, list_widget):
    cam = cmds.ls(selection=True, type="transform")
    if not cam: return
    cam = cam[0]
    shape = cmds.listRelatives(cam, shapes=True, type="camera")
    if not shape: return
    shape = shape[0]

    data = {
        "translate": cmds.getAttr(cam + ".translate")[0],
        "rotate": cmds.getAttr(cam + ".rotate")[0],
        "focalLength": cmds.getAttr(shape + ".focalLength")
    }
    snapshot_name = f"{cam}_Snapshot{len(snapshot_dict)+1}"
    snapshot_dict[snapshot_name] = (cam, data)
    list_widget.addItem(snapshot_name)

def restore_camera_snapshot(snapshot_dict, list_widget):
    item = list_widget.currentItem()
    if not item: return
    name = item.text()
    if name not in snapshot_dict: return
    cam, data = snapshot_dict[name]
    if not cmds.objExists(cam): return
    cmds.setAttr(cam + ".translate", *data["translate"], type="double3")
    cmds.setAttr(cam + ".rotate", *data["rotate"], type="double3")
    shape = cmds.listRelatives(cam, shapes=True, type="camera")[0]
    cmds.setAttr(shape + ".focalLength", data["focalLength"])
    cmds.select(cam)

def delete_camera_snapshot(snapshot_dict, list_widget):
    item = list_widget.currentItem()
    if not item: return
    name = item.text()
    if name in snapshot_dict: del snapshot_dict[name]
    list_widget.takeItem(list_widget.currentRow())

def create_area_light(): cmds.shadingNode('areaLight', asLight=True)
def create_sky_dome_light(): cmds.shadingNode('aiSkyDomeLight', asLight=True)
def open_arnold_render_view(): mel.eval("RenderGlobalsWindow;")

def check_for_updates(*args):
    global modeling_tools_dialog
    try:
        response = requests.get(GITHUB_VERSION_URL)
        if response.status_code == 200:
            latest_version = response.text.strip()
            if latest_version != CURRENT_VERSION:
                cmds.confirmDialog(title="Update Available", message=f"New version {latest_version} available!", button=["OK"])
                modeling_tools_dialog.btn_update.setEnabled(True)
                modeling_tools_dialog.btn_update.setStyleSheet(modeling_tools_dialog.update_btn_style_enabled)
            else:
                cmds.confirmDialog(title="Up to Date", message="You are using the latest version.", button=["OK"])
    except: pass

def update_tool(*args):
    global modeling_tools_dialog
    try:
        response = requests.get(GITHUB_SCRIPT_URL, stream=True)
        if response.status_code == 200:
            tmp_path = LOCAL_SCRIPT_PATH + ".tmp"
            with open(tmp_path, "wb") as f: f.write(response.content)
            shutil.move(tmp_path, LOCAL_SCRIPT_PATH)
            cmds.confirmDialog(title="Update Complete", message="Tool updated successfully.", button=["OK"])
            try:
                modeling_tools_dialog.close()
                modeling_tools_dialog.deleteLater()
            except: pass
            
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
    except Exception as e: cmds.warning(f"Error updating tool: {e}")

def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)

class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.Signal()
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()

class ModelingToolsUI(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super(ModelingToolsUI, self).__init__(parent)
        self.setWindowTitle(f"3D Assistant Tools v{CURRENT_VERSION}")
        self.setMinimumWidth(500)
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.camera_snapshots = {}
        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        font = QtGui.QFont("Arial", 10)
        self.btn_style = """
            QPushButton { background-color: #3498db; color: white; border-radius: 6px; padding: 6px; }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #1c5980; }
        """
        self.update_btn_style_disabled = "QPushButton { background-color: #7f8c8d; color: white; border-radius: 6px; padding: 6px; }"
        self.update_btn_style_enabled = """
            QPushButton { background-color: #2ecc71; color: white; border-radius: 6px; padding: 6px; }
            QPushButton:hover { background-color: #27ae60; }
            QPushButton:pressed { background-color: #219653; }
        """
        self.check_update_btn_style = """
            QPushButton { background-color: #2ecc71; color: white; border-radius: 6px; padding: 6px; }
            QPushButton:hover { background-color: #27ae60; }
            QPushButton:pressed { background-color: #219653; }
        """
        
        self.banner_label = ClickableLabel()
        self.banner_label.setAlignment(QtCore.Qt.AlignCenter)
        self.banner_label.setCursor(QtCore.Qt.PointingHandCursor)
        try:
            response = requests.get(GITHUB_BANNER_URL)
            if response.status_code == 200:
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(response.content)
                pixmap = pixmap.scaledToWidth(460, QtCore.Qt.SmoothTransformation)
                self.banner_label.setPixmap(pixmap)
        except: pass

        self.tabs = QtWidgets.QTabWidget()

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
        self.btn_open_hypershade = QtWidgets.QPushButton("Open Hypershade")
        self.btn_custom_color = QtWidgets.QPushButton("Custom Color")

        self.color_buttons = []
        for color in COLOR_PRESETS:
            btn = QtWidgets.QPushButton()
            style = f"background-color: rgb({int(color['rgb'][0]*255)}, {int(color['rgb'][1]*255)}, {int(color['rgb'][2]*255)});"
            if "Dark" in color["name"] or "Charcoal" in color["name"]: style += "color: white;"
            btn.setStyleSheet(style)
            btn.setFixedSize(70, 30)
            btn.setToolTip(color["name"])
            self.color_buttons.append(btn)

        self.btn_create_persp_cam = QtWidgets.QPushButton("Create Perspective Cam")
        self.btn_save_snapshot = QtWidgets.QPushButton("Save Snapshot")
        self.btn_restore_snapshot = QtWidgets.QPushButton("Restore Snapshot")
        self.btn_delete_snapshot = QtWidgets.QPushButton("Delete Snapshot")
        self.list_snapshots = QtWidgets.QListWidget()
        self.list_snapshots.setFixedHeight(180)

        self.btn_area_light = QtWidgets.QPushButton("Area Light")
        self.btn_sky_dome = QtWidgets.QPushButton("Sky Dome Light")
        self.btn_open_render_view = QtWidgets.QPushButton("Open Arnold RenderView")
        self.btn_check_updates = QtWidgets.QPushButton("Check for Updates")
        self.btn_update = QtWidgets.QPushButton("Update")
        self.btn_update.setEnabled(False)
        self.label_footer = QtWidgets.QLabel(f"3D Assistant Tools v{CURRENT_VERSION}")
        self.label_footer.setAlignment(QtCore.Qt.AlignCenter)
        self.label_footer.setStyleSheet("color: gray;")

        buttons = [
            self.btn_merge_center, self.btn_target_weld, self.btn_connect_vertices,
            self.btn_delete_vertices, self.btn_bridge_edges, self.btn_insert_edge_loop,
            self.btn_multi_cut, self.btn_fill_hole, self.btn_bevel_edges, self.btn_extrude_faces,
            self.btn_separate_objects, self.btn_combine_objects, self.btn_detach_faces,
            self.btn_open_hypershade, self.btn_custom_color,
            self.btn_create_persp_cam, self.btn_save_snapshot, self.btn_restore_snapshot,
            self.btn_delete_snapshot, self.btn_area_light, self.btn_sky_dome,
            self.btn_open_render_view
        ]
        
        for btn in buttons:
            btn.setFont(font)
            btn.setStyleSheet(self.btn_style)
        
        self.btn_check_updates.setFont(font)
        self.btn_check_updates.setStyleSheet(self.check_update_btn_style)
        self.btn_update.setFont(font)
        self.btn_update.setStyleSheet(self.update_btn_style_disabled)

    def create_layout(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.addWidget(self.banner_label)
        main_layout.addWidget(self.tabs)
        
        update_layout = QtWidgets.QHBoxLayout()
        update_layout.addWidget(self.btn_check_updates)
        update_layout.addWidget(self.btn_update)
        main_layout.addLayout(update_layout)
        main_layout.addWidget(self.label_footer)

        # 建模选项卡
        modeling_page = QtWidgets.QWidget()
        modeling_layout = QtWidgets.QVBoxLayout(modeling_page)
        modeling_layout.setSpacing(8)
        
        # 通用操作组
        universal_group = QtWidgets.QGroupBox("通用操作")
        universal_layout = QtWidgets.QVBoxLayout()
        universal_layout.addWidget(self.btn_merge_center)
        universal_group.setLayout(universal_layout)
        modeling_layout.addWidget(universal_group)
        
        # 顶点操作组
        vertex_group = QtWidgets.QGroupBox("顶点操作")
        vertex_layout = QtWidgets.QGridLayout()
        vertex_layout.addWidget(self.btn_target_weld, 0, 0)
        vertex_layout.addWidget(self.btn_connect_vertices, 0, 1)
        vertex_layout.addWidget(self.btn_delete_vertices, 1, 0)
        vertex_group.setLayout(vertex_layout)
        modeling_layout.addWidget(vertex_group)
        
        # 边操作组
        edge_group = QtWidgets.QGroupBox("边操作")
        edge_layout = QtWidgets.QGridLayout()
        edge_layout.addWidget(self.btn_bridge_edges, 0, 0)
        edge_layout.addWidget(self.btn_insert_edge_loop, 0, 1)
        edge_layout.addWidget(self.btn_multi_cut, 1, 0)
        edge_layout.addWidget(self.btn_fill_hole, 1, 1)
        edge_layout.addWidget(self.btn_bevel_edges, 2, 0)
        edge_group.setLayout(edge_layout)
        modeling_layout.addWidget(edge_group)
        
        # 面操作组
        face_group = QtWidgets.QGroupBox("面操作")
        face_layout = QtWidgets.QVBoxLayout()
        face_layout.addWidget(self.btn_extrude_faces)
        face_group.setLayout(face_layout)
        modeling_layout.addWidget(face_group)
        
        # 对象操作组
        object_group = QtWidgets.QGroupBox("对象操作")
        object_layout = QtWidgets.QGridLayout()
        object_layout.addWidget(self.btn_separate_objects, 0, 0)
        object_layout.addWidget(self.btn_combine_objects, 0, 1)
        object_layout.addWidget(self.btn_detach_faces, 1, 0)
        object_group.setLayout(object_layout)
        modeling_layout.addWidget(object_group)
        
        modeling_layout.addStretch()
        
        # 材质选项卡
        mat_page = QtWidgets.QWidget()
        mat_layout = QtWidgets.QVBoxLayout(mat_page)
        mat_layout.setSpacing(8)
        
        # 颜色预设组
        color_group = QtWidgets.QGroupBox("颜色预设")
        color_layout = QtWidgets.QVBoxLayout()
        
        color_grid = QtWidgets.QGridLayout()
        for i, btn in enumerate(self.color_buttons):
            row = i // 5
            col = i % 5
            color_grid.addWidget(btn, row, col)
        color_layout.addLayout(color_grid)
        
        tip_label = QtWidgets.QLabel("提示: 选择对象后点击颜色按钮赋予材质")
        tip_label.setStyleSheet("color: #888888; font-style: italic;")
        tip_label.setAlignment(QtCore.Qt.AlignCenter)
        color_layout.addWidget(tip_label)
        color_layout.addWidget(self.btn_custom_color)
        
        color_group.setLayout(color_layout)
        mat_layout.addWidget(color_group)
        
        # 工具组
        util_group = QtWidgets.QGroupBox("工具")
        util_layout = QtWidgets.QVBoxLayout()
        util_layout.addWidget(self.btn_open_hypershade)
        util_group.setLayout(util_layout)
        mat_layout.addWidget(util_group)
        
        mat_layout.addStretch()
        
        # 相机选项卡
        cam_page = QtWidgets.QWidget()
        cam_layout = QtWidgets.QVBoxLayout(cam_page)
        cam_layout.setSpacing(8)
        
        # 相机创建组
        cam_create_group = QtWidgets.QGroupBox("相机")
        cam_create_layout = QtWidgets.QVBoxLayout()
        cam_create_layout.addWidget(self.btn_create_persp_cam)
        cam_create_group.setLayout(cam_create_layout)
        cam_layout.addWidget(cam_create_group)
        
        # 快照组
        snapshot_group = QtWidgets.QGroupBox("相机快照")
        snapshot_layout = QtWidgets.QVBoxLayout()
        
        snapshot_btn_layout = QtWidgets.QHBoxLayout()
        snapshot_btn_layout.addWidget(self.btn_save_snapshot)
        snapshot_btn_layout.addWidget(self.btn_restore_snapshot)
        snapshot_btn_layout.addWidget(self.btn_delete_snapshot)
        snapshot_layout.addLayout(snapshot_btn_layout)
        
        snapshot_layout.addWidget(QtWidgets.QLabel("保存的快照:"))
        snapshot_layout.addWidget(self.list_snapshots)
        
        snapshot_group.setLayout(snapshot_layout)
        cam_layout.addWidget(snapshot_group)
        
        cam_layout.addStretch()
        
        # 灯光选项卡
        light_page = QtWidgets.QWidget()
        light_layout = QtWidgets.QVBoxLayout(light_page)
        light_layout.setSpacing(8)
        
        light_group = QtWidgets.QGroupBox("灯光创建")
        light_group_layout = QtWidgets.QHBoxLayout()
        light_group_layout.addWidget(self.btn_area_light)
        light_group_layout.addWidget(self.btn_sky_dome)
        light_group.setLayout(light_group_layout)
        light_layout.addWidget(light_group)
        
        light_layout.addStretch()
        
        # 渲染选项卡
        render_page = QtWidgets.QWidget()
        render_layout = QtWidgets.QVBoxLayout(render_page)
        render_layout.setSpacing(8)
        
        render_group = QtWidgets.QGroupBox("渲染")
        render_group_layout = QtWidgets.QVBoxLayout()
        render_group_layout.addWidget(self.btn_open_render_view)
        render_group.setLayout(render_group_layout)
        render_layout.addWidget(render_group)
        
        render_layout.addStretch()

        self.tabs.addTab(modeling_page, "建模")
        self.tabs.addTab(cam_page, "相机")
        self.tabs.addTab(mat_page, "材质")
        self.tabs.addTab(light_page, "灯光")
        self.tabs.addTab(render_page, "渲染")

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
        self.btn_open_hypershade.clicked.connect(open_hypershade)
        self.btn_custom_color.clicked.connect(assign_custom_color_to_selection)
        
        for i, btn in enumerate(self.color_buttons):
            btn.clicked.connect(lambda checked=False, idx=i: assign_material_to_selection(COLOR_PRESETS[idx]))
        
        self.btn_create_persp_cam.clicked.connect(create_perspective_camera)
        self.btn_save_snapshot.clicked.connect(lambda: save_camera_snapshot(self.camera_snapshots, self.list_snapshots))
        self.btn_restore_snapshot.clicked.connect(lambda: restore_camera_snapshot(self.camera_snapshots, self.list_snapshots))
        self.btn_delete_snapshot.clicked.connect(lambda: delete_camera_snapshot(self.camera_snapshots, self.list_snapshots))
        self.btn_area_light.clicked.connect(create_area_light)
        self.btn_sky_dome.clicked.connect(create_sky_dome_light)
        self.btn_open_render_view.clicked.connect(open_arnold_render_view)
        self.btn_check_updates.clicked.connect(check_for_updates)
        self.btn_update.clicked.connect(update_tool)
        self.banner_label.clicked.connect(lambda: webbrowser.open(GITHUB_PAGE_URL))

def showUI():
    global modeling_tools_dialog
    try:
        modeling_tools_dialog.close()
        modeling_tools_dialog.deleteLater()
    except: pass
    modeling_tools_dialog = ModelingToolsUI()
    modeling_tools_dialog.show()

showUI()