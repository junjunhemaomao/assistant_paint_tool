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
import webbrowser  # 添加webbrowser模块用于打开网页

# =============================================
# 全局变量和常量
# =============================================
CURRENT_VERSION = "1.0"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/version.txt"
GITHUB_SCRIPT_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/Assistant_tool.py"
GITHUB_BANNER_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/3D_Modeling_Assistant.png"
GITHUB_PAGE_URL = "https://github.com/junjunhemaomao/assistant_paint_tool"  # 添加GitHub页面URL

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

# =============================================
# 建模功能函数
# =============================================
def universal_merge_to_center(*args):
    """合并选定元素到中心点"""
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
    """目标焊接两个顶点"""
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
    """连接顶点"""
    mel.eval('polyConnectComponents;')
    cmds.select(clear=True)

def delete_vertices(*args):
    """删除顶点"""
    mel.eval('DeleteVertex;')

def bridge_edges(*args):
    """桥接边"""
    mel.eval('polyBridgeEdge -divisions 0 -ch 1;')
    cmds.select(clear=True)

def insert_edge_loop(*args):
    """插入循环边"""
    mel.eval('InsertEdgeLoopTool;')

def fill_hole(*args):
    """填充洞"""
    mel.eval('polyCloseBorder -ch 1;')
    cmds.select(clear=True)

def multi_cut(*args):
    """多切割工具"""
    mel.eval('MultiCutTool;')

def extrude_faces(*args):
    """挤出面"""
    mel.eval('PolyExtrude;')

def bevel_edges(*args):
    """倒角边"""
    mel.eval('BevelPolygon;')

def separate_objects(*args):
    """分离对象"""
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
    """合并对象"""
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
    """分离选定面"""
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

# =============================================
# 材质功能函数
# =============================================
def create_arnold_material(color_info):
    """创建Arnold材质"""
    name = color_info["name"]
    rgb = color_info["rgb"]
    
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
    """将材质赋予选定对象"""
    selected = cmds.ls(selection=True)
    if not selected:
        cmds.warning("Please select objects first!")
        return
    
    shading_group = create_arnold_material(color_info)
    cmds.sets(selected, forceElement=shading_group)
    print(f"Assigned '{color_info['name']}' material to {len(selected)} objects")

def assign_custom_color_to_selection():
    """赋予自定义颜色材质"""
    selected = cmds.ls(selection=True)
    if not selected:
        cmds.warning("Please select objects first!")
        return
    
    result = cmds.colorEditor()
    if cmds.colorEditor(query=True, result=True):
        rgb = cmds.colorEditor(query=True, rgb=True)
        custom_color = {
            "name": f"Custom({rgb[0]:.2f},{rgb[1]:.2f},{rgb[2]:.2f})",
            "rgb": rgb
        }
        shading_group = create_arnold_material(custom_color)
        cmds.sets(selected, forceElement=shading_group)
        print(f"Assigned custom color material to {len(selected)} objects")

def open_hypershade():
    """打开Hypershade编辑器"""
    hypershade_window = 'hyperShadePanel'
    if cmds.window(hypershade_window, exists=True):
        cmds.showWindow(hypershade_window)
    else:
        cmds.HypershadeWindow()

# =============================================
# 相机功能函数
# =============================================
def create_perspective_camera():
    """创建透视相机"""
    cam, shape = cmds.camera()
    cmds.setAttr(cam + ".translateZ", 30)
    cmds.setAttr(shape + ".focalLength", 35)
    cmds.select(cam)

def save_camera_snapshot(snapshot_dict, list_widget):
    """保存相机快照"""
    cam = cmds.ls(selection=True, type="transform")
    if not cam:
        cmds.warning("Please select a camera first")
        return
    cam = cam[0]
    shape = cmds.listRelatives(cam, shapes=True, type="camera")
    if not shape:
        cmds.warning("Selected object is not a camera")
        return
    shape = shape[0]

    data = {
        "translate": cmds.getAttr(cam + ".translate")[0],
        "rotate": cmds.getAttr(cam + ".rotate")[0],
        "focalLength": cmds.getAttr(shape + ".focalLength")
    }
    snapshot_name = f"{cam}_Snapshot{len(snapshot_dict)+1}"
    snapshot_dict[snapshot_name] = (cam, data)
    list_widget.addItem(snapshot_name)
    print(f"Saved snapshot: {snapshot_name}")

def restore_camera_snapshot(snapshot_dict, list_widget):
    """恢复相机快照"""
    item = list_widget.currentItem()
    if not item:
        cmds.warning("Please select a snapshot")
        return
    name = item.text()
    if name not in snapshot_dict:
        cmds.warning("Snapshot does not exist")
        return
    cam, data = snapshot_dict[name]
    if not cmds.objExists(cam):
        cmds.warning("Original camera no longer exists")
        return
    cmds.setAttr(cam + ".translate", *data["translate"], type="double3")
    cmds.setAttr(cam + ".rotate", *data["rotate"], type="double3")
    shape = cmds.listRelatives(cam, shapes=True, type="camera")[0]
    cmds.setAttr(shape + ".focalLength", data["focalLength"])
    cmds.select(cam)
    print(f"Restored snapshot: {name}")

def delete_camera_snapshot(snapshot_dict, list_widget):
    """删除相机快照"""
    item = list_widget.currentItem()
    if not item:
        cmds.warning("Please select a snapshot to delete")
        return
    name = item.text()
    if name in snapshot_dict:
        del snapshot_dict[name]
    list_widget.takeItem(list_widget.currentRow())
    print(f"Deleted snapshot: {name}")

# =============================================
# 灯光功能函数
# =============================================
def create_area_light():
    cmds.shadingNode('areaLight', asLight=True)

def create_sky_dome_light():
    cmds.shadingNode('aiSkyDomeLight', asLight=True)

# =============================================
# 渲染功能函数
# =============================================
def open_arnold_render_view():
    mel.eval("RenderGlobalsWindow;")

# =============================================
# 更新功能函数
# =============================================
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
        cmds.warning(f"Error updating tool: {e}")

# =============================================
# UI 类
# =============================================
def maya_main_window():
    """获取Maya主窗口"""
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)

class ClickableLabel(QtWidgets.QLabel):
    """可点击的标签类"""
    clicked = QtCore.Signal()
    
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()

class ModelingToolsUI(QtWidgets.QDialog):
    """3D Assistant Tools UI"""
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
        """创建UI控件"""
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
        
        # 更新按钮的特殊样式
        self.update_btn_style_disabled = """
            QPushButton {
                background-color: #7f8c8d;  /* 深灰色 */
                color: white;
                border-radius: 6px;
                padding: 6px;
            }
        """
        
        self.update_btn_style_enabled = """
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #27ae60; }
            QPushButton:pressed { background-color: #219653; }
        """
        
        # 检查更新按钮样式
        self.check_update_btn_style = """
            QPushButton {
                background-color: #2ecc71;  /* 绿色 */
                color: white;
                border-radius: 6px;
                padding: 6px;
            }
            QPushButton:hover { background-color: #27ae60; }
            QPushButton:pressed { background-color: #219653; }
        """
        
        # Banner - 使用可点击的标签
        self.banner_label = ClickableLabel()
        self.banner_label.setAlignment(QtCore.Qt.AlignCenter)
        self.banner_label.setCursor(QtCore.Qt.PointingHandCursor)  # 设置手型光标
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

        # Modeling buttons
        self.btn_merge_center = QtWidgets.QPushButton("Merge to Center")
        self.btn_target_weld = QtWidgets.QPushButton("Target Weld")
        self.btn_connect_vertices = QtWidgets.QPushButton("Connect Vertices")
        self.btn_delete_vertices = QtWidgets.QPushButton("Delete Vertices")
        self.btn_bridge_edges = QtWidgets.QPushButton("Bridge Edges")
        self.btn_insert_edge_loop = QtWidgets.QPushButton("Insert Edge Loop")
        self.btn_multi_cut = QtWidgets.QPushButton("Multi-Cut")
        self.btn_fill_hole = QtWidgets.QPushButton("Fill Hole")
        self.btn_bevel_edges = QtWidgets.QPushButton("Bevel Edges")
        self.btn_extrude_faces = QtWidgets.QPushButton("Extrude Faces")  # 面挤出按钮
        self.btn_separate_objects = QtWidgets.QPushButton("Separate Objects")
        self.btn_combine_objects = QtWidgets.QPushButton("Combine Objects")
        self.btn_detach_faces = QtWidgets.QPushButton("Detach Selected Faces")

        # Material buttons
        self.btn_open_hypershade = QtWidgets.QPushButton("Open Hypershade")
        self.btn_custom_color = QtWidgets.QPushButton("Custom Color")

        # Color preset buttons
        self.color_buttons = []
        for i, color in enumerate(COLOR_PRESETS):
            btn = QtWidgets.QPushButton()
            style = f"background-color: rgb({int(color['rgb'][0]*255)}, {int(color['rgb'][1]*255)}, {int(color['rgb'][2]*255)});"
            if "Dark" in color["name"] or "Charcoal" in color["name"]:
                style += "color: white;"
            btn.setStyleSheet(style)
            btn.setFixedSize(70, 30)
            btn.setToolTip(color["name"])
            self.color_buttons.append(btn)

        # Camera buttons
        self.btn_create_persp_cam = QtWidgets.QPushButton("Create Perspective Cam")
        self.btn_save_snapshot = QtWidgets.QPushButton("Save Snapshot")
        self.btn_restore_snapshot = QtWidgets.QPushButton("Restore Snapshot")
        self.btn_delete_snapshot = QtWidgets.QPushButton("Delete Snapshot")
        self.list_snapshots = QtWidgets.QListWidget()
        self.list_snapshots.setFixedHeight(180)  # 增加高度以显示更多内容

        # Lighting buttons
        self.btn_area_light = QtWidgets.QPushButton("Area Light")
        self.btn_sky_dome = QtWidgets.QPushButton("Sky Dome Light")

        # Rendering buttons
        self.btn_open_render_view = QtWidgets.QPushButton("Open Arnold RenderView")

        # Update buttons
        self.btn_check_updates = QtWidgets.QPushButton("Check for Updates")
        self.btn_update = QtWidgets.QPushButton("Update")
        self.btn_update.setEnabled(False)  # 默认禁用

        # Footer
        self.label_footer = QtWidgets.QLabel(f"3D Assistant Tools v{CURRENT_VERSION}")
        self.label_footer.setAlignment(QtCore.Qt.AlignCenter)
        self.label_footer.setStyleSheet("color: gray;")

        # Apply button styles
        all_buttons = [
            self.btn_merge_center, self.btn_target_weld, self.btn_connect_vertices,
            self.btn_delete_vertices, self.btn_bridge_edges, self.btn_insert_edge_loop,
            self.btn_multi_cut, self.btn_fill_hole, self.btn_bevel_edges, self.btn_extrude_faces,
            self.btn_separate_objects, self.btn_combine_objects, self.btn_detach_faces,
            self.btn_open_hypershade, self.btn_custom_color,
            self.btn_create_persp_cam, self.btn_save_snapshot, self.btn_restore_snapshot,
            self.btn_delete_snapshot,
            self.btn_area_light, self.btn_sky_dome,
            self.btn_open_render_view
        ]
        
        for btn in all_buttons:
            btn.setFont(font)
            btn.setStyleSheet(self.btn_style)
        
        # 更新按钮使用特殊样式
        self.btn_check_updates.setFont(font)
        self.btn_check_updates.setStyleSheet(self.check_update_btn_style)  # 绿色
        self.btn_update.setFont(font)
        self.btn_update.setStyleSheet(self.update_btn_style_disabled)  # 初始为禁用样式（深灰色）

    def create_layout(self):
        """布局UI控件"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(8)  # 减少主布局间距
        main_layout.addWidget(self.banner_label)
        main_layout.addWidget(self.tabs)
        
        # 更新按钮并列显示
        update_layout = QtWidgets.QHBoxLayout()
        update_layout.addWidget(self.btn_check_updates)
        update_layout.addWidget(self.btn_update)
        main_layout.addLayout(update_layout)
        
        main_layout.addWidget(self.label_footer)

        # 创建网格布局的辅助函数
        def create_grid_layout(buttons, columns=2):
            layout = QtWidgets.QGridLayout()
            layout.setSpacing(6)  # 减少网格间距
            row, col = 0, 0
            for i, button in enumerate(buttons):
                layout.addWidget(button, row, col)
                col += 1
                if col >= columns:
                    col = 0
                    row += 1
            return layout

        # 建模选项卡
        modeling_layout = QtWidgets.QVBoxLayout()
        modeling_layout.setSpacing(8)  # 减少组间距
        
        # 通用操作组
        universal_group = QtWidgets.QGroupBox("通用操作")
        universal_layout = QtWidgets.QVBoxLayout()
        universal_layout.addWidget(self.btn_merge_center)
        universal_group.setLayout(universal_layout)
        
        # 顶点操作组
        vertex_group = QtWidgets.QGroupBox("顶点操作")
        vertex_layout = create_grid_layout([
            self.btn_target_weld, self.btn_connect_vertices,
            self.btn_delete_vertices
        ])
        vertex_group.setLayout(vertex_layout)
        
        # 边操作组
        edge_group = QtWidgets.QGroupBox("边操作")
        edge_layout = create_grid_layout([
            self.btn_bridge_edges, self.btn_insert_edge_loop,
            self.btn_multi_cut, self.btn_fill_hole,
            self.btn_bevel_edges
        ])
        edge_group.setLayout(edge_layout)
        
        # 面操作组 - 使用网格布局使按钮样式一致
        face_group = QtWidgets.QGroupBox("面操作")
        face_layout = create_grid_layout([self.btn_extrude_faces])
        face_group.setLayout(face_layout)
        
        # 对象操作组
        object_group = QtWidgets.QGroupBox("对象操作")
        object_layout = create_grid_layout([
            self.btn_separate_objects, self.btn_combine_objects,
            self.btn_detach_faces
        ])
        object_group.setLayout(object_layout)
        
        modeling_layout.addWidget(universal_group)
        modeling_layout.addWidget(vertex_group)
        modeling_layout.addWidget(edge_group)
        modeling_layout.addWidget(face_group)
        modeling_layout.addWidget(object_group)
        modeling_layout.addStretch()  # 添加伸缩空间使下半部分留白
        
        modeling_page = QtWidgets.QWidget()
        modeling_page.setLayout(modeling_layout)

        # 材质选项卡
        mat_layout = QtWidgets.QVBoxLayout()
        mat_layout.setSpacing(8)  # 减少间距
        
        # 颜色预设组
        color_group = QtWidgets.QGroupBox("颜色预设")
        color_layout = QtWidgets.QVBoxLayout()
        color_layout.setSpacing(5)  # 减少间距
        
        # 颜色按钮网格布局
        color_grid = QtWidgets.QGridLayout()
        color_grid.setSpacing(4)  # 减少按钮间距
        for i, btn in enumerate(self.color_buttons):
            row = i // 5
            col = i % 5
            color_grid.addWidget(btn, row, col)
        
        color_layout.addLayout(color_grid)
        
        # 提示标签
        tip_label = QtWidgets.QLabel("提示: 选择对象后点击颜色按钮赋予材质")
        tip_label.setStyleSheet("color: #888888; font-style: italic;")
        tip_label.setAlignment(QtCore.Qt.AlignCenter)
        color_layout.addWidget(tip_label)
        
        # 自定义颜色按钮
        color_layout.addWidget(self.btn_custom_color)
        
        color_group.setLayout(color_layout)
        
        # 工具组
        util_group = QtWidgets.QGroupBox("工具")
        util_layout = QtWidgets.QVBoxLayout()
        util_layout.addWidget(self.btn_open_hypershade)
        util_group.setLayout(util_layout)
        
        mat_layout.addWidget(color_group)
        mat_layout.addWidget(util_group)
        mat_layout.addStretch()  # 添加伸缩空间使下半部分留白
        
        mat_page = QtWidgets.QWidget()
        mat_page.setLayout(mat_layout)

        # 相机选项卡
        cam_layout = QtWidgets.QVBoxLayout()
        cam_layout.setSpacing(8)  # 减少间距
        
        # 相机创建组
        cam_create_group = QtWidgets.QGroupBox("相机")
        cam_create_layout = QtWidgets.QVBoxLayout()
        cam_create_layout.addWidget(self.btn_create_persp_cam)
        cam_create_group.setLayout(cam_create_layout)
        
        # 快照组
        snapshot_group = QtWidgets.QGroupBox("相机快照")
        snapshot_layout = QtWidgets.QVBoxLayout()
        snapshot_layout.setSpacing(5)  # 减少间距
        
        # 快照按钮水平布局
        snapshot_btn_layout = QtWidgets.QHBoxLayout()
        snapshot_btn_layout.addWidget(self.btn_save_snapshot)
        snapshot_btn_layout.addWidget(self.btn_restore_snapshot)
        snapshot_btn_layout.addWidget(self.btn_delete_snapshot)
        
        snapshot_layout.addLayout(snapshot_btn_layout)
        
        # 快照列表
        snapshot_list_label = QtWidgets.QLabel("保存的快照:")
        snapshot_layout.addWidget(snapshot_list_label)
        snapshot_layout.addWidget(self.list_snapshots)
        
        snapshot_group.setLayout(snapshot_layout)
        
        cam_layout.addWidget(cam_create_group)
        cam_layout.addWidget(snapshot_group)
        cam_layout.addStretch()  # 添加伸缩空间使下半部分留白
        
        cam_page = QtWidgets.QWidget()
        cam_page.setLayout(cam_layout)

        # 灯光选项卡 - 组名改为"灯光创建"
        light_layout = QtWidgets.QVBoxLayout()
        light_layout.setSpacing(8)  # 减少间距
        
        light_group = QtWidgets.QGroupBox("灯光创建")  # 修改组名
        light_group_layout = QtWidgets.QHBoxLayout()  # 水平布局
        light_group_layout.addWidget(self.btn_area_light)
        light_group_layout.addWidget(self.btn_sky_dome)
        light_group.setLayout(light_group_layout)
        
        light_layout.addWidget(light_group)
        light_layout.addStretch()  # 添加伸缩空间使下半部分留白
        
        light_page = QtWidgets.QWidget()
        light_page.setLayout(light_layout)

        # 渲染选项卡
        render_layout = QtWidgets.QVBoxLayout()
        render_layout.setSpacing(8)  # 减少间距
        
        render_group = QtWidgets.QGroupBox("渲染")
        render_group_layout = QtWidgets.QVBoxLayout()
        render_group_layout.addWidget(self.btn_open_render_view)
        render_group.setLayout(render_group_layout)
        
        render_layout.addWidget(render_group)
        render_layout.addStretch()  # 添加伸缩空间使下半部分留白
        
        render_page = QtWidgets.QWidget()
        render_page.setLayout(render_layout)

        # 添加选项卡
        self.tabs.addTab(modeling_page, "建模")
        self.tabs.addTab(cam_page, "相机")
        self.tabs.addTab(mat_page, "材质")
        self.tabs.addTab(light_page, "灯光")
        self.tabs.addTab(render_page, "渲染")

    def create_connections(self):
        """连接信号与槽"""
        # Modeling connections
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

        # Material connections
        self.btn_open_hypershade.clicked.connect(open_hypershade)
        self.btn_custom_color.clicked.connect(assign_custom_color_to_selection)
        for i, btn in enumerate(self.color_buttons):
            btn.clicked.connect(lambda checked=False, idx=i: assign_material_to_selection(COLOR_PRESETS[idx]))

        # Camera connections
        self.btn_create_persp_cam.clicked.connect(create_perspective_camera)
        self.btn_save_snapshot.clicked.connect(
            lambda: save_camera_snapshot(self.camera_snapshots, self.list_snapshots)
        )
        self.btn_restore_snapshot.clicked.connect(
            lambda: restore_camera_snapshot(self.camera_snapshots, self.list_snapshots)
        )
        self.btn_delete_snapshot.clicked.connect(
            lambda: delete_camera_snapshot(self.camera_snapshots, self.list_snapshots)
        )
        
        # Lighting connections
        self.btn_area_light.clicked.connect(create_area_light)
        self.btn_sky_dome.clicked.connect(create_sky_dome_light)
        
        # Rendering connections
        self.btn_open_render_view.clicked.connect(open_arnold_render_view)
        
        # Update connections
        self.btn_check_updates.clicked.connect(check_for_updates)
        self.btn_update.clicked.connect(update_tool)
        
        # Banner click connection
        self.banner_label.clicked.connect(self.open_github_page)
    
    def open_github_page(self):
        """打开GitHub页面"""
        webbrowser.open(GITHUB_PAGE_URL)

# =============================================
# 工具调用
# =============================================
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