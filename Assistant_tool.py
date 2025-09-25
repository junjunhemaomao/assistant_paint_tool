from maya import cmds, mel
from PySide2 import QtWidgets, QtCore, QtGui
from shiboken2 import wrapInstance
import maya.OpenMayaUI as omui
import os, shutil, sys, threading, time, webbrowser, re, json, ssl, urllib.request, urllib.error

# ========================
# 全局变量和配置
# ========================
modeling_tools_dialog = None
CACHE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "PolyHaven_HDRI")
SUPPORTED_RES = ["1k", "2k", "4k", "8k"] 
SUPPORTED_FMT = ["hdr", "exr"]
DL_HOST = "https://dl.polyhaven.org"
TIMEOUT = 60
SSL_CTX = ssl.create_default_context()
CURRENT_VERSION = "1.1"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/version.txt"
GITHUB_SCRIPT_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/Assistant_tool.py"
GITHUB_BANNER_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/3D_Modeling_Assistant.png"
GITHUB_PAGE_URL = "https://github.com/junjunhemaomao/assistant_paint_tool"
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
COLOR_MAP_PATH = ""
OPACITY_MAP_PATH = ""

# ========================
# 文件系统工具函数
# ========================
def ensure_dir(path):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)
    return path

def build_cache_path(asset, res, fmt):
    """构建缓存文件路径"""
    ensure_dir(CACHE_DIR)
    return os.path.join(CACHE_DIR, f"{asset}_{res}.{fmt}")

# ========================
# URL解析工具函数
# ========================
RES_SET = {"1k", "2k", "4k", "8k", "16k"}

def strip_trailing_res(slug):
    """去除URL中的分辨率后缀"""
    m = re.match(r'^(.+?)_([0-9]+k)$', slug)
    return m.group(1) if m and m.group(2).lower() in RES_SET else slug

def parse_polyhaven_dl_url(text):
    """解析PolyHaven下载URL"""
    m = re.search(r'/HDRIs/(hdr|exr)/([0-9]+k)/([a-zA-Z0-9_\-]+)_([0-9]+k)\.(hdr|exr)$', text)
    return (strip_trailing_res(m.group(3)), m.group(2).lower(), m.group(5).lower()) if m else (None, None, None)

def parse_input(text):
    """解析用户输入"""
    if not text: return None, None, None
    text = text.strip()
    
    if "dl.polyhaven.org/file/ph-assets/HDRIs" in text:
        return parse_polyhaven_dl_url(text)
    
    m = re.search(r'/a/([a-zA-Z0-9_\-]+)', text)
    if m: return m.group(1), None, None
    
    if re.match(r'^[a-zA-Z0-9_\-]+$', text): return strip_trailing_res(text), None, None
    m2 = re.search(r'/([a-zA-Z0-9_\-]+)(?:\.[a-zA-Z0-9]+)?$', text)
    return (strip_trailing_res(m2.group(1)), None, None) if m2 else (None, None, None)

# ========================
# HTTP客户端
# ========================
class HttpClient:
    """处理HTTP请求的客户端"""
    def __init__(self):
        try:
            self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=SSL_CTX))
        except ssl.SSLError:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
            cmds.warning("SSL certificate verification disabled (fallback mode)")

    def open(self, url, method="GET", timeout=TIMEOUT, headers=None):
        """打开URL连接"""
        req = urllib.request.Request(url, method=method, headers={"User-Agent": "Maya-PolyHaven-Integration", **(headers or {})})
        return self.opener.open(req, timeout=timeout)

    def try_head_or_range(self, url, timeout=15):
        """尝试HEAD请求或范围请求"""
        try:
            with self.open(url, method="HEAD", timeout=timeout) as resp:
                return 200 <= getattr(resp, "status", 200) < 400
        except Exception:
            try:
                with self.open(url, timeout=timeout, headers={"Range": "bytes=0-64"}) as resp:
                    code = getattr(resp, "status", 200)
                    return (200 <= code < 400) or code == 206
            except Exception:
                return False

    def download(self, url, save_path, progress_cb=None):
        """下载文件并保存"""
        tmp_path = save_path + ".part"
        try:
            with self.open(url) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                with open(tmp_path, "wb") as f:
                    read = 0
                    while True:
                        data = resp.read(262144)
                        if not data: break
                        f.write(data)
                        read += len(data)
                        if progress_cb and total: progress_cb(read, total)
            shutil.move(tmp_path, save_path)
            return save_path
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

# ========================
# HDRI相关功能
# ========================
def get_asset_category(client, asset):
    """获取资产类别"""
    try:
        with client.open(f"https://api.polyhaven.com/id/{asset}", timeout=8) as resp:
            return json.load(resp).get("category", "").lower() or None
    except Exception:
        return None

def query_hdri_files(client, asset):
    """查询HDRI文件信息"""
    try:
        with client.open(f"https://api.polyhaven.com/files/hdris/{asset}", timeout=12) as resp:
            data = json.load(resp)
            return {
                fmt: {res: DL_HOST + rel for res, rel in res_map.items() if rel}
                for fmt, res_map in data.items() if fmt in ("hdr", "exr")
            }
    except Exception:
        return {}

def build_direct_url(asset, res, fmt):
    """构建直接下载URL"""
    return f"{DL_HOST}/file/ph-assets/HDRIs/{fmt}/{res}/{asset}_{res}.{fmt}"

def try_download(client, asset, pref_res, pref_fmt, progress_cb=None):
    """尝试下载HDRI文件"""
    files = query_hdri_files(client, asset)
    res_order = [pref_res] + [r for r in ["16k", "8k", "4k", "2k", "1k"] if r != pref_res]
    fmt_order = [pref_fmt] + [f for f in ("hdr", "exr") if f != pref_fmt]
    tried = []

    for fmt in fmt_order:
        for res in res_order:
            url = files.get(fmt, {}).get(res) if files else build_direct_url(asset, res, fmt)
            if not url: continue
            tried.append(url)
            save_path = build_cache_path(asset, res, fmt)
            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                return save_path, res, fmt, tried
            if not files and not client.try_head_or_range(url): continue
            try:
                client.download(url, save_path, progress_cb)
                return save_path, res, fmt, tried
            except Exception:
                continue
    return None, None, None, tried

def get_existing_skydome():
    """获取现有的天空球灯光"""
    existing = next((s for s in cmds.ls(type="aiSkyDomeLight") or [] if cmds.listRelatives(s, parent=True)), None)
    if existing:
        return cmds.listRelatives(existing, parent=True)[0], existing
    return None, None

def create_sky_dome_light():
    """创建新的天空球灯光"""
    shape = cmds.shadingNode("aiSkyDomeLight", asLight=True, name="HDR_SkyDomeShape")
    transform = cmds.listRelatives(shape, parent=True)[0]
    cmds.rename(transform, "HDR_SkyDome")
    return transform, shape

def connect_file_to_skydome(image_path):
    """连接文件到天空球灯光"""
    t, s = get_existing_skydome()
    if not t or not s:
        t, s = create_sky_dome_light()
        cmds.warning("No existing skydome light found, created a new one.")
    
    file_node = cmds.ls("HDRI_file", type="file")[0] if cmds.ls("HDRI_file", type="file") else cmds.shadingNode("file", asTexture=True, name="HDRI_file")
    cmds.setAttr(f"{file_node}.fileTextureName", image_path.replace("\\", "/"), type="string")
    cmds.connectAttr(f"{file_node}.outColor", f"{s}.color", force=True)
    return t, s, file_node

def set_skydome_attr(attr, value):
    """设置天空球属性"""
    try:
        t, s = get_existing_skydome()
        if not s:
            cmds.warning("No skydome light found. Please create one first.")
            return
        cmds.setAttr(f"{s}.{attr}", float(value))
    except Exception as e:
        cmds.warning(f"Failed to set skydome attribute: {e}")

def set_skydome_rotation(value):
    """设置天空球旋转"""
    try:
        t, s = get_existing_skydome()
        if not t:
            cmds.warning("No skydome light found. Please create one first.")
            return
        cmds.setAttr(f"{t}.rotateY", float(value))
    except Exception as e:
        cmds.warning(f"Failed to rotate skydome: {e}")

def set_skydome_camera(enabled):
    """设置天空球对相机可见"""
    try:
        t, s = get_existing_skydome()
        if not s:
            cmds.warning("No skydome light found. Please create one first.")
            return
        cmds.setAttr(f"{s}.camera", 1 if enabled else 0)
    except Exception as e:
        cmds.warning(f"Failed to set skydome visibility: {e}")

# ========================
# 建模工具函数
# ========================
def universal_merge_to_center():
    """合并到中心点"""
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

def target_weld():
    """目标焊接"""
    sel = cmds.ls(orderedSelection=True, flatten=True)
    if len(sel) < 2:
        cmds.warning("Please select two vertices or objects for target weld")
        return
    src, tgt = sel[0], sel[1]
    pos = cmds.pointPosition(tgt, world=True)
    cmds.move(pos[0], pos[1], pos[2], src, worldSpace=True, absolute=True)
    mel.eval('polyMergeVertex -d 0.000001 -ch 1;')
    cmds.select(clear=True)

def connect_vertices(): 
    """连接顶点"""
    mel.eval('polyConnectComponents;')

def delete_vertices(): 
    """删除顶点"""
    mel.eval('DeleteVertex;')

def bridge_edges(): 
    """桥接边"""
    mel.eval('polyBridgeEdge -divisions 0 -ch 1;')

def insert_edge_loop(): 
    """插入循环边"""
    mel.eval('InsertEdgeLoopTool;')

def fill_hole(): 
    """填充洞"""
    mel.eval('polyCloseBorder -ch 1;')

def multi_cut(): 
    """多切割"""
    mel.eval('MultiCutTool;')

def extrude_faces(): 
    """挤出面"""
    mel.eval('PolyExtrude;')

def bevel_edges(): 
    """倒角边"""
    mel.eval('BevelPolygon;')

def separate_objects():
    """分离对象"""
    sel = cmds.ls(selection=True)
    if not sel: return
    new_objs = mel.eval('polySeparate;')
    for obj in new_objs:
        cmds.delete(obj, ch=True)
        cmds.centerPivot(obj)
    cmds.select(clear=True)

def combine_objects():
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

def detach_selected_faces():
    """分离选中的面"""
    orig_face_sel = cmds.filterExpand(sm=34, ex=1)
    if not orig_face_sel: return
    orig_obj = cmds.listRelatives(orig_face_sel[0], parent=True, fullPath=True)[0]
    face_num = [face.split(".")[1] for face in orig_face_sel]
    new_obj = cmds.duplicate(orig_obj, un=True)[0]
    cmds.delete(new_obj, ch=True)
    new_face_sel = [f"{new_obj}.{f}" for f in face_num]
    cmds.delete(orig_face_sel)
    all_faces = cmds.ls(f"{new_obj}.f[*]", flatten=True)
    cmds.delete(list(set(all_faces) - set(new_face_sel)))
    cmds.select(new_obj)

# ========================
# 材质工具函数
# ========================
def create_arnold_material(color_info):
    """创建Arnold材质"""
    name, rgb = color_info["name"], color_info["rgb"]
    material = cmds.shadingNode('aiStandardSurface', asShader=True, name=f'{name}_mat')
    cmds.setAttr(material + '.base', 1.0)
    cmds.setAttr(material + '.baseColor', *rgb, type='double3')
    
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
    """将材质分配给选中的对象"""
    selected = cmds.ls(selection=True)
    if not selected: return
    shading_group = create_arnold_material(color_info)
    cmds.sets(selected, forceElement=shading_group)

def assign_custom_color_to_selection():
    """分配自定义颜色材质"""
    selected = cmds.ls(selection=True)
    if not selected: return
    result = cmds.colorEditor()
    if cmds.colorEditor(query=True, result=True):
        rgb = cmds.colorEditor(query=True, rgb=True)
        custom_color = {"name": f"Custom({rgb[0]:.2f},{rgb[1]:.2f},{rgb[2]:.2f})", "rgb": rgb}
        shading_group = create_arnold_material(custom_color)
        cmds.sets(selected, forceElement=shading_group)

def open_hypershade():
    """打开Hypershade窗口"""
    if cmds.window('hyperShadePanel', exists=True):
        cmds.showWindow('hyperShadePanel')
    else:
        cmds.HypershadeWindow()

def create_transparency_material(color_info, color_map_path=None, opacity_map_path=None):
    """创建透明材质"""
    name, rgb = color_info["name"], color_info["rgb"]
    material = cmds.shadingNode('aiStandardSurface', asShader=True, name=f'{name}_transparency_mat')
    
    cmds.setAttr(material + '.base', 1.0)
    cmds.setAttr(material + '.specular', 0.0)  

    if color_map_path and os.path.exists(color_map_path):
        color_file_node = cmds.shadingNode('file', asTexture=True, name=f'{name}_color_file')
        cmds.setAttr(color_file_node + '.fileTextureName', color_map_path.replace("\\", "/"), type='string')
        cmds.connectAttr(color_file_node + '.outColor', material + '.baseColor', force=True)
        cmds.setAttr(color_file_node + '.colorSpace', 'sRGB', type='string')
    else:
        cmds.setAttr(material + '.baseColor', *rgb, type='double3')

    if opacity_map_path and os.path.exists(opacity_map_path):
        opacity_file_node = cmds.shadingNode('file', asTexture=True, name=f'{name}_opacity_file')
        cmds.setAttr(opacity_file_node + '.fileTextureName', opacity_map_path.replace("\\", "/"), type='string')
        cmds.connectAttr(opacity_file_node + '.outColor', material + '.opacity', force=True)
        cmds.setAttr(opacity_file_node + '.colorSpace', 'Raw', type='string')
    
    shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=material+'SG')
    cmds.connectAttr(material + '.outColor', shading_group + '.surfaceShader', force=True)
    return shading_group

def assign_transparency_material():
    """分配透明材质"""
    selected = cmds.ls(selection=True)
    if not selected:
        cmds.warning("Please select objects to assign material")
        return False

    base_color = {"name": "Transparency", "rgb": (0.7, 0.7, 0.7)}

    shading_group = create_transparency_material(
        base_color, 
        COLOR_MAP_PATH, 
        OPACITY_MAP_PATH
    )

    cmds.sets(selected, forceElement=shading_group)

    if cmds.objExists('hardwareRenderingGlobals'):
        cmds.setAttr('hardwareRenderingGlobals.transparencyAlgorithm', 5)
    
    return True

def select_color_map():
    """选择颜色贴图"""
    global COLOR_MAP_PATH
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        None, 
        "Select Color Map", 
        "", 
        "Image Files (*.png *.jpg *.jpeg *.tga *.tif *.tiff *.exr)"
    )
    
    if file_path:
        COLOR_MAP_PATH = file_path
        return True
    return False

def select_opacity_map():
    """选择不透明度贴图"""
    global OPACITY_MAP_PATH
    file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
        None, 
        "Select Opacity Map", 
        "", 
        "Image Files (*.png *.jpg *.jpeg *.tga *.tif *.tiff *.exr)"
    )
    
    if file_path:
        OPACITY_MAP_PATH = file_path
        return True
    return False

# ========================
# 相机工具函数
# ========================
def create_perspective_camera():
    """创建透视相机"""
    cam, shape = cmds.camera()

def save_camera_snapshot(snapshot_dict, list_widget):
    """保存相机快照"""
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
    """恢复相机快照"""
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
    """删除相机快照"""
    item = list_widget.currentItem()
    if not item: return
    name = item.text()
    if name in snapshot_dict: del snapshot_dict[name]
    list_widget.takeItem(list_widget.currentRow())

# ========================
# 灯光工具函数
# ========================
def create_area_light(): 
    """创建区域光"""
    cmds.shadingNode('areaLight', asLight=True)

def open_arnold_render_view(): 
    """打开Arnold渲染视图"""
    mel.eval("RenderGlobalsWindow;")

# ========================
# 更新功能
# ========================
def check_for_updates():
    """检查更新"""
    global modeling_tools_dialog
    try:
        req = urllib.request.Request(GITHUB_VERSION_URL, headers={"User-Agent": "Maya-PolyHaven-Integration"})
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=TIMEOUT) as resp:
            if resp.getcode() == 200:
                latest_version = resp.read().decode("utf-8").strip()
                if latest_version != CURRENT_VERSION:
                    cmds.confirmDialog(title="Update Available", message=f"New version {latest_version} available!", button=["OK"])
                    modeling_tools_dialog.btn_update.setEnabled(True)
                    modeling_tools_dialog.btn_update.setStyleSheet(modeling_tools_dialog.update_btn_style_enabled)
                else:
                    cmds.confirmDialog(title="Up to Date", message="You are using the latest version.", button=["OK"])
    except Exception as e:
        cmds.warning(f"Check update failed: {str(e)}")

def update_tool(*args):
    """更新工具"""
    global modeling_tools_dialog
    try:
        req = urllib.request.Request(GITHUB_SCRIPT_URL, headers={"User-Agent": "Maya-PolyHaven-Integration"})
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=TIMEOUT) as resp:
            if resp.getcode() == 200:
                tmp_path = LOCAL_SCRIPT_PATH + ".tmp"
                with open(tmp_path, "wb") as f:
                    f.write(resp.read())
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
    except Exception as e:
        cmds.warning(f"Error updating tool: {e}")

# ========================
# UI相关函数
# ========================
def maya_main_window():
    """获取Maya主窗口"""
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)

class ClickableLabel(QtWidgets.QLabel):
    """可点击的标签"""
    clicked = QtCore.Signal()
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.clicked.emit()

class ModelingToolsUI(QtWidgets.QDialog):
    """3D助手工具UI"""
    def __init__(self, parent=maya_main_window()):
        super(ModelingToolsUI, self).__init__(parent)
        self.setWindowTitle(f"3D Assistant Tools v{CURRENT_VERSION}")
        self.setFixedWidth(600)
        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.camera_snapshots = {}
        self.create_widgets()
        self.create_layout()
        self.create_connections()

    def create_widgets(self):
        """创建UI组件"""
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
        
        self.banner_label = ClickableLabel()
        self.banner_label.setAlignment(QtCore.Qt.AlignCenter)
        self.banner_label.setCursor(QtCore.Qt.PointingHandCursor)
        try:
            req = urllib.request.Request(GITHUB_BANNER_URL, headers={"User-Agent": "Maya-PolyHaven-Integration"})
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=TIMEOUT) as resp:
                if resp.getcode() == 200:
                    pixmap = QtGui.QPixmap()
                    pixmap.loadFromData(resp.read())
                    pixmap = pixmap.scaledToWidth(550, QtCore.Qt.SmoothTransformation)
                    self.banner_label.setPixmap(pixmap)
        except Exception as e:
            cmds.warning(f"Failed to load banner: {str(e)}")

        self.tabs = QtWidgets.QTabWidget()

        # 灯光组件
        self.btn_area_light = QtWidgets.QPushButton("Area Light")
        self.btn_sky_dome = QtWidgets.QPushButton("Sky Dome Light")
        self.btn_open_render_view = QtWidgets.QPushButton("Open Arnold RenderView")

        # HDRI组件
        self.hdri_open_btn = QtWidgets.QPushButton("Open Poly Haven HDRIs")
        self.hdri_asset_edit = QtWidgets.QLineEdit("https://polyhaven.com/a/zawiszy_czarnego")
        self.hdri_res_combo = QtWidgets.QComboBox()
        self.hdri_res_combo.addItems(SUPPORTED_RES)
        self.hdri_res_combo.setCurrentText("4k")
        self.hdri_fmt_combo = QtWidgets.QComboBox()
        self.hdri_fmt_combo.addItems(SUPPORTED_FMT)
        self.hdri_fmt_combo.setCurrentText("exr")
        self.hdri_cache_label = QtWidgets.QLabel(CACHE_DIR)
        self.hdri_cache_btn = QtWidgets.QPushButton("Change Cache Location")
        self.hdri_download_btn = QtWidgets.QPushButton("Download and Apply")
        self.hdri_progress = QtWidgets.QProgressBar()
        self.hdri_progress.setRange(0, 100)

        # HDRI控制组件
        SLIDER_WIDTH = 300
        self.hdri_exposure_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.hdri_exposure_slider.setRange(-40, 80)
        self.hdri_exposure_slider.setFixedWidth(SLIDER_WIDTH)
        self.hdri_exposure_label = QtWidgets.QLabel("0.0")
        
        self.hdri_intensity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.hdri_intensity_slider.setRange(0, 1000)
        self.hdri_intensity_slider.setFixedWidth(SLIDER_WIDTH)
        self.hdri_intensity_label = QtWidgets.QLabel("1.0")
        
        self.hdri_rotate_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.hdri_rotate_slider.setRange(0, 360)
        self.hdri_rotate_slider.setFixedWidth(SLIDER_WIDTH)
        self.hdri_rotate_label = QtWidgets.QLabel("0°")
        
        self.hdri_camera_cb = QtWidgets.QCheckBox("Visible to Camera")
        self.hdri_camera_cb.setChecked(True)

        # 建模工具按钮
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

        # 颜色按钮
        self.color_buttons = []
        for color in COLOR_PRESETS:
            btn = QtWidgets.QPushButton()
            style = f"background-color: rgb({int(color['rgb'][0]*255)}, {int(color['rgb'][1]*255)}, {int(color['rgb'][2]*255)});"
            if "Dark" in color["name"] or "Charcoal" in color["name"]: style += "color: white;"
            btn.setStyleSheet(style)
            btn.setFixedSize(70, 30)
            btn.setToolTip(color["name"])
            self.color_buttons.append(btn)

        # 透明材质按钮
        self.btn_transparency = QtWidgets.QPushButton("Assign Transparency Material")
        self.btn_select_color_map = QtWidgets.QPushButton("Select Color Map")
        self.btn_select_opacity_map = QtWidgets.QPushButton("Select Opacity Map")

        # 路径标签
        self.label_color_path = QtWidgets.QLabel("No color map selected")
        self.label_opacity_path = QtWidgets.QLabel("No opacity map selected")
        self.label_color_path.setStyleSheet("color: #888888;")
        self.label_opacity_path.setStyleSheet("color: #888888;")
        self.label_color_path.setWordWrap(True)
        self.label_opacity_path.setWordWrap(True)
        
        # 相机按钮
        self.btn_create_persp_cam = QtWidgets.QPushButton("Create Perspective Cam")
        self.btn_save_snapshot = QtWidgets.QPushButton("Save Snapshot")
        self.btn_restore_snapshot = QtWidgets.QPushButton("Restore Snapshot")
        self.btn_delete_snapshot = QtWidgets.QPushButton("Delete Snapshot")
        self.list_snapshots = QtWidgets.QListWidget()
        self.list_snapshots.setFixedHeight(180)

        # 更新按钮
        self.btn_check_updates = QtWidgets.QPushButton("Check for Updates")
        self.btn_update = QtWidgets.QPushButton("Update")
        self.btn_update.setEnabled(False)
        self.label_footer = QtWidgets.QLabel(f"3D Assistant Tools v{CURRENT_VERSION}")
        self.label_footer.setAlignment(QtCore.Qt.AlignCenter)
        self.label_footer.setStyleSheet("color: gray;")
        
        # 几何体按钮
        self.geometry_buttons = []
        geometry_types = [
            ("Cube", "polyCube", ":polyCube.png"),
            ("Sphere", "polySphere", ":polySphere.png"),
            ("Cylinder", "polyCylinder", ":polyCylinder.png"),
            ("Cone", "polyCone", ":polyCone.png"),
            ("Plane", "polyPlane", ":polyPlane.png"),
            ("Torus", "polyTorus", ":polyTorus.png")
        ]
        
        for geom_name, mel_cmd, icon_path in geometry_types:
            btn = QtWidgets.QPushButton()
            btn.setFixedSize(40, 40)
            btn.setToolTip(f"Create {geom_name}")
            btn.setIcon(QtGui.QIcon(icon_path))
            btn.setIconSize(QtCore.QSize(32, 32))
            self.geometry_buttons.append(btn)

    def create_layout(self):
        """布局UI组件"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(6) 
        main_layout.addWidget(self.banner_label)
        main_layout.addWidget(self.tabs)
        
        update_layout = QtWidgets.QHBoxLayout()
        update_layout.addWidget(self.btn_check_updates)
        update_layout.addWidget(self.btn_update)
        main_layout.addLayout(update_layout)
        main_layout.addWidget(self.label_footer)

        # 建模页布局
        modeling_page = QtWidgets.QWidget()
        modeling_layout = QtWidgets.QVBoxLayout(modeling_page)
        modeling_layout.setSpacing(6)
        
        geometry_row = QtWidgets.QHBoxLayout()
        geometry_row.setAlignment(QtCore.Qt.AlignCenter)
        for btn in self.geometry_buttons:
            geometry_row.addWidget(btn)
        modeling_layout.addLayout(geometry_row)

        def create_group(title, widgets):
            """创建带标题的组件组"""
            group = QtWidgets.QGroupBox(title)
            layout = QtWidgets.QGridLayout()
            for i, widget in enumerate(widgets):
                layout.addWidget(widget, i//2, i%2)
            group.setLayout(layout)
            return group

        modeling_layout.addWidget(create_group("Universal Operations", [self.btn_merge_center]))
        modeling_layout.addWidget(create_group("Vertex Operations", [
            self.btn_target_weld, self.btn_connect_vertices, self.btn_delete_vertices
        ]))
        modeling_layout.addWidget(create_group("Edge Operations", [
            self.btn_bridge_edges, self.btn_insert_edge_loop, 
            self.btn_multi_cut, self.btn_fill_hole, self.btn_bevel_edges
        ]))
        modeling_layout.addWidget(create_group("Face Operations", [
            self.btn_extrude_faces
        ]))
        modeling_layout.addWidget(create_group("Object Operations", [
            self.btn_separate_objects, self.btn_combine_objects, self.btn_detach_faces
        ]))
        modeling_layout.addStretch()
 
        # 材质页布局
        mat_page = QtWidgets.QWidget()
        mat_layout = QtWidgets.QVBoxLayout(mat_page)
        mat_layout.setSpacing(6)  
        
        color_group = QtWidgets.QGroupBox("Color Presets")
        color_layout = QtWidgets.QVBoxLayout()
        
        color_grid = QtWidgets.QGridLayout()
        for i, btn in enumerate(self.color_buttons):
            color_grid.addWidget(btn, i//5, i%5)
        color_layout.addLayout(color_grid)
        
        tip_label = QtWidgets.QLabel("Tip: Select objects then click color button to assign material")
        tip_label.setStyleSheet("color: #888888; font-style: italic;")
        tip_label.setAlignment(QtCore.Qt.AlignCenter)
        color_layout.addWidget(tip_label)
        color_layout.addWidget(self.btn_custom_color)
        color_group.setLayout(color_layout)
        mat_layout.addWidget(color_group)

        transparency_group = QtWidgets.QGroupBox("Transparency Material")
        transparency_layout = QtWidgets.QVBoxLayout(transparency_group)
 
        color_map_layout = QtWidgets.QVBoxLayout()
        color_map_layout.addWidget(QtWidgets.QLabel("Color Map:"))
        color_map_layout.addWidget(self.label_color_path)
        color_map_layout.addWidget(self.btn_select_color_map)
        transparency_layout.addLayout(color_map_layout)

        transparency_layout.addSpacing(10)
  
        opacity_map_layout = QtWidgets.QVBoxLayout()
        opacity_map_layout.addWidget(QtWidgets.QLabel("Opacity Map:"))
        opacity_map_layout.addWidget(self.label_opacity_path)
        opacity_map_layout.addWidget(self.btn_select_opacity_map)
        transparency_layout.addLayout(opacity_map_layout)

        transparency_layout.addSpacing(15)
 
        transparency_layout.addWidget(self.btn_transparency)
        
        mat_layout.addWidget(transparency_group)
        
        util_group = QtWidgets.QGroupBox("Tools")
        util_layout = QtWidgets.QVBoxLayout()
        util_layout.addWidget(self.btn_open_hypershade)
        util_group.setLayout(util_layout)
        mat_layout.addWidget(util_group)
        mat_layout.addStretch()

        # 相机页布局
        cam_page = QtWidgets.QWidget()
        cam_layout = QtWidgets.QVBoxLayout(cam_page)
        cam_layout.setSpacing(6) 
        
        cam_create_group = QtWidgets.QGroupBox("Camera")
        cam_create_layout = QtWidgets.QVBoxLayout()
        cam_create_layout.addWidget(self.btn_create_persp_cam)
        cam_create_group.setLayout(cam_create_layout)
        cam_layout.addWidget(cam_create_group)
        
        snapshot_group = QtWidgets.QGroupBox("Camera Snapshots")
        snapshot_layout = QtWidgets.QVBoxLayout()
        
        snapshot_btn_layout = QtWidgets.QHBoxLayout()
        snapshot_btn_layout.addWidget(self.btn_save_snapshot)
        snapshot_btn_layout.addWidget(self.btn_restore_snapshot)
        snapshot_btn_layout.addWidget(self.btn_delete_snapshot)
        snapshot_layout.addLayout(snapshot_btn_layout)
        
        snapshot_layout.addWidget(QtWidgets.QLabel("Saved Snapshots:"))
        snapshot_layout.addWidget(self.list_snapshots)
        snapshot_group.setLayout(snapshot_layout)
        cam_layout.addWidget(snapshot_group)
        cam_layout.addStretch()

        # 灯光页布局
        light_page = QtWidgets.QWidget()
        light_layout = QtWidgets.QVBoxLayout(light_page)
        light_layout.setSpacing(6)  
        
        light_group = QtWidgets.QGroupBox("Light Creation")
        light_group_layout = QtWidgets.QGridLayout()
        light_group_layout.addWidget(self.btn_area_light, 0, 0)
        light_group_layout.addWidget(self.btn_sky_dome, 0, 1)
        light_group_layout.addWidget(self.btn_open_render_view, 1, 0, 1, 2)
        light_group.setLayout(light_group_layout)
        light_layout.addWidget(light_group)

        resource_group = QtWidgets.QGroupBox("Resource")
        resource_layout = QtWidgets.QVBoxLayout(resource_group)
        
        url_layout = QtWidgets.QHBoxLayout()
        url_layout.addWidget(QtWidgets.QLabel("Asset/URL:"))
        url_layout.addWidget(self.hdri_asset_edit)
        resource_layout.addLayout(url_layout)
        
        res_fmt_layout = QtWidgets.QHBoxLayout()
        res_fmt_layout.addWidget(QtWidgets.QLabel("Resolution:"))
        res_fmt_layout.addWidget(self.hdri_res_combo)
        res_fmt_layout.addSpacing(5)
        res_fmt_layout.addWidget(QtWidgets.QLabel("Format:"))
        res_fmt_layout.addWidget(self.hdri_fmt_combo)
        resource_layout.addLayout(res_fmt_layout)
        
        resource_layout.addWidget(self.hdri_open_btn)
        light_layout.addWidget(resource_group)

        cache_group = QtWidgets.QGroupBox("Cache")
        cache_layout = QtWidgets.QVBoxLayout(cache_group)
        cache_layout.addWidget(QtWidgets.QLabel("Cache Location:"))
        cache_layout.addWidget(self.hdri_cache_label)
        
        cache_btn_layout = QtWidgets.QHBoxLayout()
        cache_btn_layout.addWidget(self.hdri_cache_btn)
        cache_layout.addLayout(cache_btn_layout)
        light_layout.addWidget(cache_group)

        download_group = QtWidgets.QGroupBox("Download")
        download_layout = QtWidgets.QVBoxLayout(download_group)
        
        download_btn_layout = QtWidgets.QHBoxLayout()
        download_btn_layout.addStretch()
        download_btn_layout.addWidget(self.hdri_download_btn)
        download_btn_layout.addStretch()
        download_layout.addLayout(download_btn_layout)
        download_layout.addWidget(self.hdri_progress)
        light_layout.addWidget(download_group)

        skydome_group = QtWidgets.QGroupBox("Skydome Control")
        skydome_layout = QtWidgets.QVBoxLayout(skydome_group)
        
        def create_slider_row(label, slider, value_label):
            """创建带标签的滑块行"""
            layout = QtWidgets.QHBoxLayout()
            layout.addWidget(QtWidgets.QLabel(label))
            layout.addWidget(slider)
            layout.addWidget(value_label)
            return layout
        
        skydome_layout.addLayout(create_slider_row("Exposure:", self.hdri_exposure_slider, self.hdri_exposure_label))
        skydome_layout.addLayout(create_slider_row("Intensity:", self.hdri_intensity_slider, self.hdri_intensity_label))
        skydome_layout.addLayout(create_slider_row("Rotation:", self.hdri_rotate_slider, self.hdri_rotate_label))
        
        camera_layout = QtWidgets.QHBoxLayout()
        camera_layout.addWidget(self.hdri_camera_cb)
        camera_layout.addStretch()
        skydome_layout.addLayout(camera_layout)
        light_layout.addWidget(skydome_group)
        light_layout.addStretch()

        # 渲染页布局
        render_page = QtWidgets.QWidget()
        render_layout = QtWidgets.QVBoxLayout(render_page)
        render_layout.setSpacing(6)  
        
        render_group = QtWidgets.QGroupBox("Rendering")
        render_group_layout = QtWidgets.QVBoxLayout()
        render_group_layout.addWidget(self.btn_open_render_view)
        render_group.setLayout(render_group_layout)
        render_layout.addWidget(render_group)
        render_layout.addStretch()

        # 添加标签页
        self.tabs.addTab(modeling_page, "Modeling")
        self.tabs.addTab(cam_page, "Camera")
        self.tabs.addTab(mat_page, "Material")
        self.tabs.addTab(light_page, "Lighting")
        self.tabs.addTab(render_page, "Rendering")

    def create_connections(self):
        """连接信号和槽"""
        # 建模工具连接
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
        
        # 颜色按钮连接
        for i, btn in enumerate(self.color_buttons):
            btn.clicked.connect(lambda checked=False, idx=i: assign_material_to_selection(COLOR_PRESETS[idx]))

        # 相机工具连接
        self.btn_create_persp_cam.clicked.connect(create_perspective_camera)
        self.btn_save_snapshot.clicked.connect(lambda: save_camera_snapshot(self.camera_snapshots, self.list_snapshots))
        self.btn_restore_snapshot.clicked.connect(lambda: restore_camera_snapshot(self.camera_snapshots, self.list_snapshots))
        self.btn_delete_snapshot.clicked.connect(lambda: delete_camera_snapshot(self.camera_snapshots, self.list_snapshots))

        # 灯光工具连接
        self.btn_area_light.clicked.connect(create_area_light)
        self.btn_sky_dome.clicked.connect(create_sky_dome_light)
        self.btn_open_render_view.clicked.connect(open_arnold_render_view)
        
        # HDRI工具连接
        self.hdri_open_btn.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://polyhaven.com/hdris")))
        self.hdri_cache_btn.clicked.connect(self.choose_cache_dir)
        self.hdri_download_btn.clicked.connect(self.on_download_apply)
        self.hdri_exposure_slider.valueChanged.connect(self.on_exposure_changed)
        self.hdri_intensity_slider.valueChanged.connect(self.on_intensity_changed)
        self.hdri_rotate_slider.valueChanged.connect(self.on_rotate_changed)
        self.hdri_camera_cb.toggled.connect(set_skydome_camera)

        # 更新功能连接
        self.btn_check_updates.clicked.connect(check_for_updates)
        self.btn_update.clicked.connect(update_tool)
        self.banner_label.clicked.connect(lambda: webbrowser.open(GITHUB_PAGE_URL))

        # 透明材质连接
        self.btn_transparency.clicked.connect(assign_transparency_material)
        self.btn_select_color_map.clicked.connect(self.on_select_color_map)
        self.btn_select_opacity_map.clicked.connect(self.on_select_opacity_map)
        
        # 几何体按钮连接
        geometry_commands = [cmds.polyCube, cmds.polySphere, cmds.polyCylinder, 
                            cmds.polyCone, cmds.polyPlane, cmds.polyTorus]
        for i, btn in enumerate(self.geometry_buttons):
            btn.clicked.connect(geometry_commands[i])

    # HDRI相关方法
    def choose_cache_dir(self):
        """选择缓存目录"""
        global CACHE_DIR
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Cache Location", CACHE_DIR)
        if d:
            CACHE_DIR = d
            ensure_dir(CACHE_DIR)
            self.hdri_cache_label.setText(CACHE_DIR)

    def on_download_apply(self):
        """下载并应用HDRI"""
        text = self.hdri_asset_edit.text().strip()
        asset, url_res, url_fmt = parse_input(text)
        if not asset:
            QtWidgets.QMessageBox.warning(self, "HDRI Download", "Unable to parse input")
            return

        pref_res = url_res or self.hdri_res_combo.currentText()
        pref_fmt = url_fmt or self.hdri_fmt_combo.currentText()
        client = HttpClient()
        
        cat = get_asset_category(client, asset)
        if cat and cat != "hdris" and QtWidgets.QMessageBox.question(
            self, "HDRI Download", f"Asset category: {cat}\nStill try to download as HDRI?"
        ) != QtWidgets.QMessageBox.Yes:
            return

        self.hdri_progress.setValue(0)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            save_path, res, fmt, tried = try_download(
                client, asset, pref_res, pref_fmt, self.set_progress
            )
            if save_path:
                connect_file_to_skydome(save_path)
                self.hdri_progress.setValue(100)
                QtWidgets.QMessageBox.information(self, "HDRI Download", f"Download and apply successful!\n{res} {fmt}")
            else:
                QtWidgets.QMessageBox.warning(self, "HDRI Download", "Download failed\nTried URLs:\n" + "\n".join(tried))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "HDRI Download", f"Error: {e}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def set_progress(self, read, total):
        """设置下载进度"""
        self.hdri_progress.setValue(int(read * 100 / max(total, 1)))
        
    def on_exposure_changed(self, value):
        """曝光值改变处理"""
        exposure = value / 4.0
        self.hdri_exposure_label.setText(f"{exposure:.2f}")
        set_skydome_attr("aiExposure", exposure)
        
    def on_intensity_changed(self, value):
        """强度值改变处理"""
        intensity = value / 10.0
        self.hdri_intensity_label.setText(f"{intensity:.2f}")
        set_skydome_attr("intensity", intensity)
        
    def on_rotate_changed(self, value):
        """旋转值改变处理"""
        self.hdri_rotate_label.setText(f"{value}°")
        set_skydome_rotation(value)
        
    # 透明材质方法
    def on_select_color_map(self):
        """选择颜色贴图"""
        if select_color_map():
            self.label_color_path.setText(COLOR_MAP_PATH)
            self.label_color_path.setStyleSheet("color: #2ecc71;")
        else:
            self.label_color_path.setText("No color map selected")
            self.label_color_path.setStyleSheet("color: #888888;")

    def on_select_opacity_map(self):
        """选择不透明度贴图"""
        if select_opacity_map():
            self.label_opacity_path.setText(OPACITY_MAP_PATH)
            self.label_opacity_path.setStyleSheet("color: #2ecc71;")
        else:
            self.label_opacity_path.setText("No opacity map selected")
            self.label_opacity_path.setStyleSheet("color: #888888;")

# ========================
# 主函数
# ========================
def showUI():
    """显示UI"""
    global modeling_tools_dialog
    try:
        modeling_tools_dialog.close()
        modeling_tools_dialog.deleteLater()
    except: pass
    modeling_tools_dialog = ModelingToolsUI()
    modeling_tools_dialog.show()

# 初始化脚本路径
try:
    LOCAL_SCRIPT_PATH = os.path.abspath(__file__)
except NameError:
    LOCAL_SCRIPT_PATH = os.path.abspath(sys.argv[0])

# 启动UI
showUI()