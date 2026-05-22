# 服务器部署与维护手册

## 服务器信息

| 项目 | 值 |
|------|-----|
| IP | 139.155.152.122 |
| 系统 | Ubuntu Server 24.04 LTS |
| Web 服务 | nginx 1.24 |
| 插件更新端口 | 8080 |
| 文件目录 | /var/www/assistant-paint-tool/ |
| nginx 配置 | /etc/nginx/sites-available/assistant-paint-tool |

## 同服务器其他服务

| 项目 | 值 |
|------|-----|
| 项目名 | ComicMaster-V2 |
| 路径 | /opt/ComicMaster-V2/ |
| 框架 | Flask 3.1.3 |
| 入口 | wsgi:app（Gunicorn） |
| Python | .venv 虚拟环境 |
| 进程 | Gunicorn 2 workers |
| 端口 | 5001 |

> 插件更新（nginx 8080）和网站（Gunicorn 5000）是独立进程、独立端口，互不影响。

## 访问地址

| 文件 | URL |
|------|-----|
| version.txt | http://139.155.152.122:8080/version.txt |
| Assistant_tool.py | http://139.155.152.122:8080/Assistant_tool.py |
| banner 图 | http://139.155.152.122:8080/3D_Modeling_Assistant.png |

---

## 日常发版流程

本地代码改完后：

```bash
# 1. 推 GitHub
git add . && git commit -m "描述改动" && git push

# 2. SSH 到服务器拉取更新
ssh ubuntu@139.155.152.122
sudo wget -4 -O /var/www/assistant-paint-tool/Assistant_tool.py https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/Assistant_tool.py
sudo wget -4 -O /var/www/assistant-paint-tool/version.txt https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/version.txt

# 3. banner 图更新了才需要拉
sudo wget -4 -O /var/www/assistant-paint-tool/3D_Modeling_Assistant.png https://raw.githubusercontent.com/junjunhemaomao/assistant_paint_tool/main/3D_Modeling_Assistant.png

# 4. 验证
curl http://127.0.0.1:8080/version.txt
```

> 注意：`version.txt` 内容必须和插件代码里的 `CURRENT_VERSION` 同步。

---

## 新增插件仓库

以新增 `face-rig-tool` 插件为例：

### 步骤 1：SSH 到服务器，创建目录

```bash
ssh ubuntu@139.155.152.122
sudo mkdir -p /var/www/face-rig-tool
```

### 步骤 2：添加 nginx 子路径

在现有配置中加一个 location：

```bash
sudo nano /etc/nginx/sites-available/assistant-paint-tool
```

在 `server` 块内添加：

```nginx
location /face-rig-tool/ {
    alias /var/www/face-rig-tool/;
    add_header Access-Control-Allow-Origin "*";
    location ~* \.(txt|py|png)$ {}
    location / { return 403; }
}
```

保存后验证并重载：

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 步骤 3：拉取文件

```bash
sudo wget -4 -O /var/www/face-rig-tool/version.txt https://raw.githubusercontent.com/junjunhemaomao/face-rig-tool/main/version.txt
sudo wget -4 -O /var/www/face-rig-tool/FaceRigTool.py https://raw.githubusercontent.com/junjunhemaomao/face-rig-tool/main/FaceRigTool.py
sudo wget -4 -O /var/www/face-rig-tool/banner.png https://raw.githubusercontent.com/junjunhemaomao/face-rig-tool/main/banner.png
```

### 步骤 4：验证

```bash
curl http://127.0.0.1:8080/face-rig-tool/version.txt
```

外网访问：`http://139.155.152.122:8080/face-rig-tool/version.txt`

### 新插件的代码端

在插件 Python 代码里加上对应的 URL 回退机制（参考 Assistant_tool.py 的模式）：

```python
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/junjunhemaomao/face-rig-tool/main/version.txt"
SERVER_VERSION_URL = "http://139.155.152.122:8080/face-rig-tool/version.txt"
# ... 以此类推
```

---

## 目录结构总览

```
/var/www/
├── assistant-paint-tool/     ← 3D 绘画助手
│   ├── version.txt
│   ├── Assistant_tool.py
│   └── 3D_Modeling_Assistant.png
│
└── face-rig-tool/            ← 未来新插件
    ├── version.txt
    ├── FaceRigTool.py
    └── banner.png
```

访问示例：

```
http://139.155.152.122:8080/assistant-paint-tool/version.txt   （不写路径也行，看配置）
http://139.155.152.122:8080/face-rig-tool/version.txt
```

---

## 止损备忘

| 问题 | 处理 |
|------|------|
| 服务器挂了 | GitHub 自动回退，用户无感知 |
| nginx 挂了 | `sudo systemctl restart nginx` |
| 8080 不通 | 检查腾讯云控制台防火墙规则 + `sudo iptables -L` |
| GitHub 拉不下来 | 加 `-4` 参数强制 IPv4 |
| 配置改错了 | `sudo nginx -t` 会指出具体错误行 |
