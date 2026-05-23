from maya import cmds, mel
from PySide2 import QtWidgets, QtCore, QtGui
from shiboken2 import wrapInstance
import maya.OpenMayaUI as omui
import os, shutil, sys, webbrowser, re, json, ssl, urllib.request
import importlib

# ========================
# 全局变量和配置
# ========================
modeling_tools_dialog = None

def _maya_user_dir():
    """获取Maya用户目录，非主线程时cmds.internalVar可能返回空，fallback到~/Documents/maya"""
    try:
        d = cmds.internalVar(userAppDir=True)
        if d:
            return d
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Documents", "maya")

CACHE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "PolyHaven_HDRI")
BANNER_CACHE = os.path.join(_maya_user_dir(), "assistant_paint_tool", "banner_cache.png")
BANNER_META = os.path.join(_maya_user_dir(), "assistant_paint_tool", "banner_meta.txt")
LANG = "en"
TEXTS = {
    # Window
    "3D Assistant Tools": "3D 助手工具",
    # Tabs
    "Modeling": "建模", "Camera": "相机", "Material": "材质", "Lighting": "灯光", "Rendering": "渲染",
    # Modeling groups
    "Mirror Geometry": "镜像几何体",
    "Mirror Axis": "选择镜像轴", "Choose mirror axis:": "选择镜像轴：",
    "Universal Operations": "通用操作", "Vertex Operations": "顶点操作",
    "Edge Operations": "边操作", "Face Operations": "面操作", "Object Operations": "对象操作",
    # Modeling buttons
    "Merge to Center": "合并到中心", "Target Weld": "目标焊接",
    "Connect Vertices": "连接顶点", "Delete Vertices": "删除顶点",
    "Bridge Edges": "桥接边", "Insert Edge Loop": "插入循环边",
    "Multi-Cut": "多切割", "Fill Hole": "填充洞",
    "Bevel Edges": "倒角边", "Extrude Faces": "挤出面",
    "Separate Objects": "分离对象", "Combine Objects": "合并对象",
    "Detach Selected Faces": "分离选中面",
    "Freeze Transforms": "冻结变换", "Center Pivot": "居中枢轴",
    "Pivot to Origin": "枢轴归原点",
    # Geometry tooltips
    "Create Cube": "创建立方体", "Create Sphere": "创建球体",
    "Create Cylinder": "创建圆柱体", "Create Cone": "创建圆锥体",
    "Create Plane": "创建平面", "Create Torus": "创建圆环",
    # Material
    "Color Presets": "颜色预设",
    "Tip: Select objects then click color button to assign material": "提示：选择对象后点击颜色按钮即可分配材质",
    "Custom Color": "自定义颜色",
    "Transparency Material": "透明材质",
    "Color Map:": "颜色贴图：", "Opacity Map:": "不透明度贴图：",
    "No color map selected": "未选择颜色贴图", "No opacity map selected": "未选择不透明度贴图",
    "Select Color Map": "选择颜色贴图", "Select Opacity Map": "选择不透明度贴图",
    "Assign Transparency Material": "分配透明材质",
    "Tools": "工具", "Open Hypershade": "打开Hypershade",
    # Camera
    "Create Perspective Cam": "创建透视相机",
    "Camera Snapshots": "相机快照",
    "Save Snapshot": "保存快照", "Restore Snapshot": "恢复快照", "Delete Snapshot": "删除快照",
    "Saved Snapshots:": "已保存的快照：",
    # Lighting
    "Light Creation": "灯光创建", "Area Light": "区域光", "Sky Dome Light": "天空球灯光",
    "Open Arnold RenderView": "打开Arnold渲染视图",
    "Resource": "资源", "Asset/URL:": "资产/URL：",
    "Resolution:": "分辨率：", "Format:": "格式：",
    "Open Poly Haven HDRIs": "打开Poly Haven HDRI",
    "Cache": "缓存", "Cache Location:": "缓存位置：", "Change Cache Location": "更改缓存位置",
    "Download": "下载", "Download and Apply": "下载并应用",
    "Skydome Control": "天空球控制",
    "Exposure:": "曝光度：", "Intensity:": "强度：", "Rotation:": "旋转：",
    "Visible to Camera": "相机可见",
    # Update
    "Check for Updates": "检查更新", "Update": "更新",
    # Dialog messages
    "Update Available": "发现新版本",
    "New version {v} available!\nCurrent version: {c}": "新版本 {v} 可用！\n当前版本: {c}",
    "Up to Date": "已是最新",
    "You are using the latest version.": "您正在使用最新版本。",
    "Network Error": "网络错误",
    "Failed to check for updates. Please check your network.": "检查更新失败，请检查网络连接。",
    "Update Complete": "更新完成",
    "Tool updated successfully. UI will restart automatically.": "工具更新成功，UI 将自动重启。",
    "Update Failed": "更新失败",
    "Failed to download update. Please check your network.": "下载更新失败，请检查网络连接。",
    # HDRI Download dialogs
    "HDRI Download": "HDRI 下载",
    "Unable to parse input": "无法解析输入",
    "Asset category: {cat}\nStill try to download as HDRI?": "资源类别: {cat}\n仍然尝试作为 HDRI 下载？",
    "Download and apply successful!\n{res} {fmt}": "下载并应用成功！\n{res} {fmt}",
    "Download failed\nTried URLs:\n": "下载失败\n已尝试 URL:\n",
    "Select Cache Location": "选择缓存位置",
}
SUPPORTED_RES = ["1k", "2k", "4k", "8k"] 
SUPPORTED_FMT = ["hdr", "exr"]
DL_HOST = "https://dl.polyhaven.org"
TIMEOUT = 60
SSL_CTX = ssl.create_default_context()
CURRENT_VERSION = "1.3"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/version.txt"
GITHUB_SCRIPT_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/Assistant_tool.py"
GITHUB_BANNER_URL = "https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/3D_Modeling_Assistant.png"
GITHUB_PAGE_URL = "https://junjunhemaomao.github.io/Art_web_public/"

UPDATE_HOST = "http://139.155.152.122:8080"
SERVER_VERSION_URL = f"{UPDATE_HOST}/version.txt"
SERVER_SCRIPT_URL = f"{UPDATE_HOST}/Assistant_tool.py"
SERVER_BANNER_URL = f"{UPDATE_HOST}/3D_Modeling_Assistant.png"
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
    """确保目录存在，始终使用绝对路径避免权限错误"""
    if not os.path.isabs(path):
        path = os.path.join(os.path.expanduser("~"), path)
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

def mirror_geometry():
    """镜像几何体（弹出轴选择）"""
    sel = cmds.ls(selection=True)
    if not sel:
        cmds.warning("Please select objects to mirror")
        return

    parent = maya_main_window()
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle(_t("Mirror Axis"))
    dlg.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.WindowCloseButtonHint)
    dlg.setFixedSize(200, 90)
    layout = QtWidgets.QVBoxLayout(dlg)
    layout.addWidget(QtWidgets.QLabel(_t("Choose mirror axis:")))
    btn_row = QtWidgets.QHBoxLayout()
    result = {"axis": None}

    for axis in ("X", "Y", "Z"):
        btn = QtWidgets.QPushButton(axis)
        btn.setFixedSize(50, 28)
        btn.clicked.connect(lambda checked=False, a=axis: _on_mirror_axis(a, result, dlg))
        btn_row.addWidget(btn)
    layout.addLayout(btn_row)
    dlg.exec_()

    if result["axis"] is None:
        return

    axis_map = {"X": "scaleX", "Y": "scaleY", "Z": "scaleZ"}
    attr = axis_map[result["axis"]]

    for obj in sel:
        dup = cmds.duplicate(obj, name=f"{obj}_Mirror")[0]
        cmds.setAttr(f"{dup}.{attr}", -1)
        cmds.xform(dup, centerPivots=True)
    cmds.select(cl=True)

def _on_mirror_axis(axis, result, dlg):
    result["axis"] = axis
    dlg.accept()

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

def freeze_transforms():
    """冻结变换"""
    sel = cmds.ls(selection=True)
    if not sel:
        cmds.warning("Please select objects to freeze transforms")
        return
    cmds.makeIdentity(apply=True, translate=True, rotate=True, scale=True)

def center_pivot():
    """居中枢轴"""
    sel = cmds.ls(selection=True)
    if not sel:
        cmds.warning("Please select objects to center pivot")
        return
    cmds.xform(centerPivots=True)

def pivot_to_origin():
    """将枢轴移到世界原点"""
    sel = cmds.ls(selection=True)
    if not sel:
        cmds.warning("Please select objects to move pivot to origin")
        return
    cmds.xform(ws=True, pivots=(0, 0, 0))

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
    cam = cmds.camera()[0]
    cam = cmds.rename(cam, "PerspCam")
    cmds.select(cam)

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
    """检查更新（服务器优先，GitHub备用）"""
    global modeling_tools_dialog
    data, _ = _fetch_url(SERVER_VERSION_URL, GITHUB_VERSION_URL, timeout=8)
    if data:
        latest_version = data.decode("utf-8").strip()
        cmds.warning(f"Current version: {CURRENT_VERSION}, Latest version: {latest_version}")

        if latest_version != CURRENT_VERSION:
            cmds.confirmDialog(
                title=_t("Update Available"),
                message=_t("New version {v} available!\nCurrent version: {c}", v=latest_version, c=CURRENT_VERSION),
                button=["OK"]
            )
            modeling_tools_dialog.btn_update.setEnabled(True)
            modeling_tools_dialog.btn_update.setStyleSheet(modeling_tools_dialog.update_btn_style_enabled)
            return True
        else:
            cmds.confirmDialog(
                title=_t("Up to Date"),
                message=_t("You are using the latest version."),
                button=["OK"]
            )
    else:
        cmds.confirmDialog(
            title=_t("Network Error"),
            message=_t("Failed to check for updates. Please check your network."),
            button=["OK"]
        )
    return False

def update_tool(*args):
    """更新工具（服务器优先，GitHub备用）"""
    global modeling_tools_dialog
    data, _ = _fetch_url(SERVER_SCRIPT_URL, GITHUB_SCRIPT_URL, timeout=12)
    if data:
        tmp_path = LOCAL_SCRIPT_PATH + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(data)
        shutil.move(tmp_path, LOCAL_SCRIPT_PATH)

        cmds.confirmDialog(
            title=_t("Update Complete"),
            message=_t("Tool updated successfully. UI will restart automatically."),
            button=["OK"]
        )

        try:
            modeling_tools_dialog.close()
            modeling_tools_dialog.deleteLater()
        except Exception as e:
            cmds.warning(f"Error closing dialog: {str(e)}")

        def reload_ui():
            script_dir = os.path.dirname(LOCAL_SCRIPT_PATH)
            if script_dir not in sys.path:
                sys.path.append(script_dir)
            module_name = os.path.splitext(os.path.basename(LOCAL_SCRIPT_PATH))[0]
            try:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                else:
                    importlib.import_module(module_name)
            finally:
                showUI()

        cmds.evalDeferred(reload_ui)
        return True
    else:
        cmds.confirmDialog(
            title=_t("Network Error"),
            message=_t("Failed to download update. Please check your network."),
            button=["OK"]
        )
    return False

# ========================
# UI相关函数
# ========================
def _fetch_url(primary_url, fallback_url, timeout=8):
    """先尝试主URL，失败则用备用URL。返回 (data, headers) 或 (None, None)"""
    for url in (primary_url, fallback_url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Maya-PolyHaven-Integration"})
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=timeout) as resp:
                if resp.getcode() == 200:
                    return resp.read(), resp.headers
        except Exception:
            continue
    return None, None

def load_banner_image():
    """加载banner图，优先使用本地缓存"""
    if os.path.exists(BANNER_CACHE) and os.path.getsize(BANNER_CACHE) > 0:
        pixmap = QtGui.QPixmap(BANNER_CACHE)
        if not pixmap.isNull():
            cmds.evalDeferred(_check_and_update_banner)
            return pixmap

    return _download_banner()

def _download_banner():
    """下载banner并缓存（服务器优先，GitHub备用）"""
    ensure_dir(os.path.dirname(BANNER_CACHE))
    data, headers = _fetch_url(SERVER_BANNER_URL, GITHUB_BANNER_URL, timeout=8)
    if data:
        _save_banner(data, headers.get("Content-Length", ""))
        pixmap = QtGui.QPixmap()
        pixmap.loadFromData(data)
        return pixmap
    return None

def _save_banner(data, content_length):
    """保存banner数据和元信息"""
    with open(BANNER_CACHE, "wb") as f:
        f.write(data)
    with open(BANNER_META, "w") as f:
        f.write(content_length)

def _check_and_update_banner():
    """后台检查banner更新，有则下载供下次启动使用"""
    try:
        cached_size = ""
        if os.path.exists(BANNER_META):
            with open(BANNER_META, "r") as f:
                cached_size = f.read().strip()

        for url in (SERVER_BANNER_URL, GITHUB_BANNER_URL):
            try:
                req = urllib.request.Request(url, method="HEAD",
                    headers={"User-Agent": "Maya-PolyHaven-Integration"})
                with urllib.request.urlopen(req, context=SSL_CTX, timeout=5) as resp:
                    remote_size = resp.headers.get("Content-Length", "")
                    if remote_size and remote_size != cached_size:
                        _download_banner()
                    return
            except Exception:
                continue
    except Exception:
        pass

def _t(text, **kwargs):
    """翻译文本，kwargs 用于格式化动态内容"""
    result = TEXTS.get(text, text) if LANG == "zh" else text
    if kwargs:
        result = result.format(**kwargs)
    return result

def _apply_language_to_dialog(dialog):
    """递归更新对话框中所有控件的文本"""
    dialog.setWindowTitle(f"{_t('3D Assistant Tools')} v{CURRENT_VERSION}")
    _walk_widget(dialog)

def _walk_widget(widget):
    """递归遍历控件树更新文本"""
    rev = {v: k for k, v in TEXTS.items()}
    for child in widget.children():
        if isinstance(child, QtWidgets.QPushButton):
            cur = child.text()
            if LANG == "zh" and cur in TEXTS:
                child.setText(TEXTS[cur])
            elif LANG == "en" and cur in rev:
                child.setText(rev[cur])
        elif isinstance(child, QtWidgets.QLabel):
            cur = child.text()
            if LANG == "zh" and cur in TEXTS:
                child.setText(TEXTS[cur])
            elif LANG == "en" and cur in rev:
                child.setText(rev[cur])
        elif isinstance(child, QtWidgets.QGroupBox):
            cur = child.title()
            if LANG == "zh" and cur in TEXTS:
                child.setTitle(TEXTS[cur])
            elif LANG == "en" and cur in rev:
                child.setTitle(rev[cur])
        elif isinstance(child, QtWidgets.QCheckBox):
            cur = child.text()
            if LANG == "zh" and cur in TEXTS:
                child.setText(TEXTS[cur])
            elif LANG == "en" and cur in rev:
                child.setText(rev[cur])
        elif isinstance(child, QtWidgets.QTabWidget):
            for i in range(child.count()):
                cur = child.tabText(i)
                if LANG == "zh" and cur in TEXTS:
                    child.setTabText(i, TEXTS[cur])
                elif LANG == "en" and cur in rev:
                    child.setTabText(i, rev[cur])
        # 更新 tooltip
        if isinstance(child, QtWidgets.QWidget):
            tip = child.toolTip()
            if tip:
                if LANG == "zh" and tip in TEXTS:
                    child.setToolTip(TEXTS[tip])
                elif LANG == "en" and tip in rev:
                    child.setToolTip(rev[tip])
        _walk_widget(child)

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
        global LANG
        LANG = cmds.optionVar(query="assistantPaintLang") if cmds.optionVar(exists="assistantPaintLang") else "en"
        self.setWindowTitle(f"{_t('3D Assistant Tools')} v{CURRENT_VERSION}")
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
        pixmap = load_banner_image()
        if pixmap:
            pixmap = pixmap.scaledToWidth(550, QtCore.Qt.SmoothTransformation)
            self.banner_label.setPixmap(pixmap)

        lang_btn_style = """
            QPushButton { background: transparent; border: 1px solid #555; border-radius: 3px;
                color: #aaa; font-size: 11px; padding: 2px 6px; }
            QPushButton:hover { border-color: #3498db; color: #3498db; }
            QPushButton[active="true"] { border-color: #3498db; color: #3498db; background: #1a3a5c; }
        """
        self.btn_lang_zh = QtWidgets.QPushButton("中")
        self.btn_lang_en = QtWidgets.QPushButton("EN")
        self.btn_lang_zh.setFixedSize(28, 20)
        self.btn_lang_en.setFixedSize(28, 20)
        self.btn_lang_zh.setStyleSheet(lang_btn_style)
        self.btn_lang_en.setStyleSheet(lang_btn_style)
        self.btn_lang_zh.setProperty("active", LANG == "zh")
        self.btn_lang_en.setProperty("active", LANG == "en")
        self.btn_lang_zh.setStyleSheet(lang_btn_style)
        self.btn_lang_en.setStyleSheet(lang_btn_style)

        self.tabs = QtWidgets.QTabWidget()

        # 灯光组件
        self.btn_area_light = QtWidgets.QPushButton(_t("Area Light"))
        self.btn_sky_dome = QtWidgets.QPushButton(_t("Sky Dome Light"))
        self.btn_open_render_view = QtWidgets.QPushButton(_t("Open Arnold RenderView"))

        # HDRI组件
        self.hdri_open_btn = QtWidgets.QPushButton(_t("Open Poly Haven HDRIs"))
        self.hdri_asset_edit = QtWidgets.QLineEdit("https://polyhaven.com/a/zawiszy_czarnego")
        self.hdri_res_combo = QtWidgets.QComboBox()
        self.hdri_res_combo.addItems(SUPPORTED_RES)
        self.hdri_res_combo.setCurrentText("4k")
        self.hdri_fmt_combo = QtWidgets.QComboBox()
        self.hdri_fmt_combo.addItems(SUPPORTED_FMT)
        self.hdri_fmt_combo.setCurrentText("exr")
        self.hdri_cache_label = QtWidgets.QLabel(CACHE_DIR)
        self.hdri_cache_btn = QtWidgets.QPushButton(_t("Change Cache Location"))
        self.hdri_download_btn = QtWidgets.QPushButton(_t("Download and Apply"))
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
        
        self.hdri_camera_cb = QtWidgets.QCheckBox(_t("Visible to Camera"))
        self.hdri_camera_cb.setChecked(True)

        # 建模工具按钮
        self.btn_merge_center = QtWidgets.QPushButton(_t("Merge to Center"))
        self.btn_mirror = QtWidgets.QPushButton(_t("Mirror Geometry"))
        self.btn_target_weld = QtWidgets.QPushButton(_t("Target Weld"))
        self.btn_connect_vertices = QtWidgets.QPushButton(_t("Connect Vertices"))
        self.btn_delete_vertices = QtWidgets.QPushButton(_t("Delete Vertices"))
        self.btn_bridge_edges = QtWidgets.QPushButton(_t("Bridge Edges"))
        self.btn_insert_edge_loop = QtWidgets.QPushButton(_t("Insert Edge Loop"))
        self.btn_multi_cut = QtWidgets.QPushButton(_t("Multi-Cut"))
        self.btn_fill_hole = QtWidgets.QPushButton(_t("Fill Hole"))
        self.btn_bevel_edges = QtWidgets.QPushButton(_t("Bevel Edges"))
        self.btn_extrude_faces = QtWidgets.QPushButton(_t("Extrude Faces"))
        self.btn_separate_objects = QtWidgets.QPushButton(_t("Separate Objects"))
        self.btn_combine_objects = QtWidgets.QPushButton(_t("Combine Objects"))
        self.btn_detach_faces = QtWidgets.QPushButton(_t("Detach Selected Faces"))
        self.btn_freeze_transforms = QtWidgets.QPushButton(_t("Freeze Transforms"))
        self.btn_center_pivot = QtWidgets.QPushButton(_t("Center Pivot"))
        self.btn_pivot_origin = QtWidgets.QPushButton(_t("Pivot to Origin"))
        self.btn_open_hypershade = QtWidgets.QPushButton(_t("Open Hypershade"))
        self.btn_custom_color = QtWidgets.QPushButton(_t("Custom Color"))

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
        self.btn_transparency = QtWidgets.QPushButton(_t("Assign Transparency Material"))
        self.btn_select_color_map = QtWidgets.QPushButton(_t("Select Color Map"))
        self.btn_select_opacity_map = QtWidgets.QPushButton(_t("Select Opacity Map"))

        # 路径标签
        self.label_color_path = QtWidgets.QLabel(_t("No color map selected"))
        self.label_opacity_path = QtWidgets.QLabel(_t("No opacity map selected"))
        self.label_color_path.setStyleSheet("color: #888888;")
        self.label_opacity_path.setStyleSheet("color: #888888;")
        self.label_color_path.setWordWrap(True)
        self.label_opacity_path.setWordWrap(True)
        
        # 相机按钮
        self.btn_create_persp_cam = QtWidgets.QPushButton(_t("Create Perspective Cam"))
        self.btn_save_snapshot = QtWidgets.QPushButton(_t("Save Snapshot"))
        self.btn_restore_snapshot = QtWidgets.QPushButton(_t("Restore Snapshot"))
        self.btn_delete_snapshot = QtWidgets.QPushButton(_t("Delete Snapshot"))
        self.list_snapshots = QtWidgets.QListWidget()
        self.list_snapshots.setFixedHeight(180)

        # 更新按钮
        self.btn_check_updates = QtWidgets.QPushButton(_t("Check for Updates"))
        self.btn_update = QtWidgets.QPushButton(_t("Update"))
        self.btn_update.setEnabled(False)
        self.label_footer = QtWidgets.QLabel(f"{_t('3D Assistant Tools')} v{CURRENT_VERSION}")
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
            btn.setToolTip(_t(f"Create {geom_name}"))
            btn.setIcon(QtGui.QIcon(icon_path))
            btn.setIconSize(QtCore.QSize(32, 32))
            self.geometry_buttons.append(btn)

    def create_layout(self):
        """布局UI组件"""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.addWidget(self.banner_label)

        lang_row = QtWidgets.QHBoxLayout()
        lang_row.addStretch()
        lang_row.addWidget(self.btn_lang_zh)
        lang_row.addWidget(self.btn_lang_en)
        main_layout.addLayout(lang_row)

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

        modeling_layout.addWidget(create_group(_t("Universal Operations"), [self.btn_merge_center, self.btn_mirror]))
        modeling_layout.addWidget(create_group(_t("Vertex Operations"), [
            self.btn_target_weld, self.btn_connect_vertices, self.btn_delete_vertices
        ]))
        modeling_layout.addWidget(create_group(_t("Edge Operations"), [
            self.btn_bridge_edges, self.btn_insert_edge_loop, 
            self.btn_multi_cut, self.btn_fill_hole, self.btn_bevel_edges
        ]))
        modeling_layout.addWidget(create_group(_t("Face Operations"), [
            self.btn_extrude_faces
        ]))
        modeling_layout.addWidget(create_group(_t("Object Operations"), [
            self.btn_separate_objects, self.btn_combine_objects, self.btn_detach_faces,
            self.btn_freeze_transforms, self.btn_center_pivot, self.btn_pivot_origin
        ]))
        modeling_layout.addStretch()
 
        # 材质页布局
        mat_page = QtWidgets.QWidget()
        mat_layout = QtWidgets.QVBoxLayout(mat_page)
        mat_layout.setSpacing(6)  
        
        color_group = QtWidgets.QGroupBox(_t("Color Presets"))
        color_layout = QtWidgets.QVBoxLayout()

        color_grid = QtWidgets.QGridLayout()
        for i, btn in enumerate(self.color_buttons):
            color_grid.addWidget(btn, i//5, i%5)
        color_layout.addLayout(color_grid)

        tip_label = QtWidgets.QLabel(_t("Tip: Select objects then click color button to assign material"))
        tip_label.setStyleSheet("color: #888888; font-style: italic;")
        tip_label.setAlignment(QtCore.Qt.AlignCenter)
        color_layout.addWidget(tip_label)
        color_layout.addWidget(self.btn_custom_color)
        color_group.setLayout(color_layout)
        mat_layout.addWidget(color_group)

        transparency_group = QtWidgets.QGroupBox(_t("Transparency Material"))
        transparency_layout = QtWidgets.QVBoxLayout(transparency_group)

        color_map_layout = QtWidgets.QVBoxLayout()
        color_map_layout.addWidget(QtWidgets.QLabel(_t("Color Map:")))
        color_map_layout.addWidget(self.label_color_path)
        color_map_layout.addWidget(self.btn_select_color_map)
        transparency_layout.addLayout(color_map_layout)

        transparency_layout.addSpacing(10)

        opacity_map_layout = QtWidgets.QVBoxLayout()
        opacity_map_layout.addWidget(QtWidgets.QLabel(_t("Opacity Map:")))
        opacity_map_layout.addWidget(self.label_opacity_path)
        opacity_map_layout.addWidget(self.btn_select_opacity_map)
        transparency_layout.addLayout(opacity_map_layout)

        transparency_layout.addSpacing(15)
 
        transparency_layout.addWidget(self.btn_transparency)
        
        mat_layout.addWidget(transparency_group)
        
        util_group = QtWidgets.QGroupBox(_t("Tools"))
        util_layout = QtWidgets.QVBoxLayout()
        util_layout.addWidget(self.btn_open_hypershade)
        util_group.setLayout(util_layout)
        mat_layout.addWidget(util_group)
        mat_layout.addStretch()

        # 相机页布局
        cam_page = QtWidgets.QWidget()
        cam_layout = QtWidgets.QVBoxLayout(cam_page)
        cam_layout.setSpacing(6)

        cam_create_group = QtWidgets.QGroupBox(_t("Camera"))
        cam_create_layout = QtWidgets.QVBoxLayout()
        cam_create_layout.addWidget(self.btn_create_persp_cam)
        cam_create_group.setLayout(cam_create_layout)
        cam_layout.addWidget(cam_create_group)

        snapshot_group = QtWidgets.QGroupBox(_t("Camera Snapshots"))
        snapshot_layout = QtWidgets.QVBoxLayout()

        snapshot_btn_layout = QtWidgets.QHBoxLayout()
        snapshot_btn_layout.addWidget(self.btn_save_snapshot)
        snapshot_btn_layout.addWidget(self.btn_restore_snapshot)
        snapshot_btn_layout.addWidget(self.btn_delete_snapshot)
        snapshot_layout.addLayout(snapshot_btn_layout)

        snapshot_layout.addWidget(QtWidgets.QLabel(_t("Saved Snapshots:")))
        snapshot_layout.addWidget(self.list_snapshots)
        snapshot_group.setLayout(snapshot_layout)
        cam_layout.addWidget(snapshot_group)
        cam_layout.addStretch()

        # 灯光页布局
        light_page = QtWidgets.QWidget()
        light_layout = QtWidgets.QVBoxLayout(light_page)
        light_layout.setSpacing(6)  
        
        light_group = QtWidgets.QGroupBox(_t("Light Creation"))
        light_group_layout = QtWidgets.QGridLayout()
        light_group_layout.addWidget(self.btn_area_light, 0, 0)
        light_group_layout.addWidget(self.btn_sky_dome, 0, 1)
        light_group_layout.addWidget(self.btn_open_render_view, 1, 0, 1, 2)
        light_group.setLayout(light_group_layout)
        light_layout.addWidget(light_group)

        resource_group = QtWidgets.QGroupBox(_t("Resource"))
        resource_layout = QtWidgets.QVBoxLayout(resource_group)
        
        url_layout = QtWidgets.QHBoxLayout()
        url_layout.addWidget(QtWidgets.QLabel(_t("Asset/URL:")))
        url_layout.addWidget(self.hdri_asset_edit)
        resource_layout.addLayout(url_layout)

        res_fmt_layout = QtWidgets.QHBoxLayout()
        res_fmt_layout.addWidget(QtWidgets.QLabel(_t("Resolution:")))
        res_fmt_layout.addWidget(self.hdri_res_combo)
        res_fmt_layout.addSpacing(5)
        res_fmt_layout.addWidget(QtWidgets.QLabel(_t("Format:")))
        res_fmt_layout.addWidget(self.hdri_fmt_combo)
        resource_layout.addLayout(res_fmt_layout)
        
        resource_layout.addWidget(self.hdri_open_btn)
        light_layout.addWidget(resource_group)

        cache_group = QtWidgets.QGroupBox(_t("Cache"))
        cache_layout = QtWidgets.QVBoxLayout(cache_group)
        cache_layout.addWidget(QtWidgets.QLabel(_t("Cache Location:")))
        cache_layout.addWidget(self.hdri_cache_label)

        cache_btn_layout = QtWidgets.QHBoxLayout()
        cache_btn_layout.addWidget(self.hdri_cache_btn)
        cache_layout.addLayout(cache_btn_layout)
        light_layout.addWidget(cache_group)

        download_group = QtWidgets.QGroupBox(_t("Download"))
        download_layout = QtWidgets.QVBoxLayout(download_group)

        download_btn_layout = QtWidgets.QHBoxLayout()
        download_btn_layout.addStretch()
        download_btn_layout.addWidget(self.hdri_download_btn)
        download_btn_layout.addStretch()
        download_layout.addLayout(download_btn_layout)
        download_layout.addWidget(self.hdri_progress)
        light_layout.addWidget(download_group)

        skydome_group = QtWidgets.QGroupBox(_t("Skydome Control"))
        skydome_layout = QtWidgets.QVBoxLayout(skydome_group)

        def create_slider_row(label, slider, value_label):
            """创建带标签的滑块行"""
            layout = QtWidgets.QHBoxLayout()
            layout.addWidget(QtWidgets.QLabel(label))
            layout.addWidget(slider)
            layout.addWidget(value_label)
            return layout

        skydome_layout.addLayout(create_slider_row(_t("Exposure:"), self.hdri_exposure_slider, self.hdri_exposure_label))
        skydome_layout.addLayout(create_slider_row(_t("Intensity:"), self.hdri_intensity_slider, self.hdri_intensity_label))
        skydome_layout.addLayout(create_slider_row(_t("Rotation:"), self.hdri_rotate_slider, self.hdri_rotate_label))
        
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
        
        render_group = QtWidgets.QGroupBox(_t("Rendering"))
        render_group_layout = QtWidgets.QVBoxLayout()
        render_group_layout.addWidget(self.btn_open_render_view)
        render_group.setLayout(render_group_layout)
        render_layout.addWidget(render_group)
        render_layout.addStretch()

        # 添加标签页
        self.tabs.addTab(modeling_page, _t("Modeling"))
        self.tabs.addTab(cam_page, _t("Camera"))
        self.tabs.addTab(mat_page, _t("Material"))
        self.tabs.addTab(light_page, _t("Lighting"))
        self.tabs.addTab(render_page, _t("Rendering"))

    def create_connections(self):
        """连接信号和槽"""
        self.btn_lang_zh.clicked.connect(lambda: self.set_lang("zh"))
        self.btn_lang_en.clicked.connect(lambda: self.set_lang("en"))

        # 建模工具连接
        self.btn_merge_center.clicked.connect(universal_merge_to_center)
        self.btn_mirror.clicked.connect(mirror_geometry)
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
        self.btn_freeze_transforms.clicked.connect(freeze_transforms)
        self.btn_center_pivot.clicked.connect(center_pivot)
        self.btn_pivot_origin.clicked.connect(pivot_to_origin)
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

    def set_lang(self, lang):
        """切换语言"""
        global LANG
        LANG = lang
        cmds.optionVar(sv=("assistantPaintLang", lang))
        self.btn_lang_zh.setProperty("active", lang == "zh")
        self.btn_lang_en.setProperty("active", lang == "en")
        for btn in (self.btn_lang_zh, self.btn_lang_en):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        _apply_language_to_dialog(self)

    # HDRI相关方法
    def choose_cache_dir(self):
        """选择缓存目录"""
        global CACHE_DIR
        d = QtWidgets.QFileDialog.getExistingDirectory(self, _t("Select Cache Location"), CACHE_DIR)
        if d:
            CACHE_DIR = d
            ensure_dir(CACHE_DIR)
            self.hdri_cache_label.setText(CACHE_DIR)

    def on_download_apply(self):
        """下载并应用HDRI"""
        text = self.hdri_asset_edit.text().strip()
        asset, url_res, url_fmt = parse_input(text)
        if not asset:
            QtWidgets.QMessageBox.warning(self, _t("HDRI Download"), _t("Unable to parse input"))
            return

        pref_res = url_res or self.hdri_res_combo.currentText()
        pref_fmt = url_fmt or self.hdri_fmt_combo.currentText()
        client = HttpClient()

        cat = get_asset_category(client, asset)
        if cat and cat != "hdris" and QtWidgets.QMessageBox.question(
            self, _t("HDRI Download"), _t("Asset category: {cat}\nStill try to download as HDRI?", cat=cat)
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
                QtWidgets.QMessageBox.information(self, _t("HDRI Download"), _t("Download and apply successful!\n{res} {fmt}", res=res, fmt=fmt))
            else:
                QtWidgets.QMessageBox.warning(self, _t("HDRI Download"), _t("Download failed\nTried URLs:\n") + "\n".join(tried))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, _t("HDRI Download"), f"Error: {e}")
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
            self.label_color_path.setText(_t("No color map selected"))
            self.label_color_path.setStyleSheet("color: #888888;")

    def on_select_opacity_map(self):
        """选择不透明度贴图"""
        if select_opacity_map():
            self.label_opacity_path.setText(OPACITY_MAP_PATH)
            self.label_opacity_path.setStyleSheet("color: #2ecc71;")
        else:
            self.label_opacity_path.setText(_t("No opacity map selected"))
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