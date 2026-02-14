# SynergyPlus

局域网多屏协同工具 — 一套键鼠控制多台电脑，鼠标跨屏幕无缝切换

## ✨ 功能特性

- 🖥️ **扩展显示模式**: 鼠标移到屏幕边缘自动切换到另一台电脑（类似 Synergy / Barrier）
- 🖱️ **完整输入控制**: 鼠标移动、点击、滚轮、键盘全按键支持
- 📋 **共享剪贴板**: 在一台电脑复制，另一台电脑直接粘贴
- 📁 **小文件传输**: 复制文件自动传输到另一台电脑（默认限制 100MB）
- 🌐 **Web 管理界面**: 通过浏览器管理连接和配置，支持拖拽式屏幕布局编辑器
- 🔒 **安全控制**: Server 端支持 IP 白名单
- � **配置持久化**: 自动保存到 JSON 文件
- 📦 **跨平台**: 支持 macOS 和 Linux

## 系统要求

- Python 3.9+
- macOS 10.12+ 或 Linux（Ubuntu 18.04+）
- 局域网连接

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 Server 端（被控制的电脑）

```bash
python server.py
```

打开浏览器访问 `http://localhost:5003`，点击 **Start Server**。

### 3. 启动 Master 端（控制端电脑）

```bash
python master.py
```

打开浏览器访问 `http://localhost:5001`：

1. 输入 Server 的 IP 和端口 → 点击 **Connect**
2. 在屏幕布局编辑器中拖拽 Server 屏幕到 Master 屏幕旁边 → **Save Layout**
3. 点击 **Enable Control** → 将鼠标移到配置好的屏幕边缘即可跨屏！

## 使用说明

### 扩展显示模式

鼠标移到 Master 屏幕边缘时，自动切换到对应方向的 Server 屏幕：

```
┌──────────┐┌──────────┐
│  Master  ││  Server  │  ← 鼠标向右移出 Master 边缘，自动进入 Server
│  (本机)   ││  (远程)   │  ← 鼠标向左移出 Server 边缘，自动回到 Master
└──────────┘└──────────┘
```

- 切换后，键盘和鼠标**只**作用于当前活动屏幕
- 支持上下左右四个方向布局

### 共享剪贴板

- 在任意屏幕 `Cmd+C` / `Ctrl+C` 复制文本 → 自动同步到另一台电脑
- 直接 `Cmd+V` / `Ctrl+V` 粘贴即可
- Finder/文件管理器中复制文件 → 自动传输到 `~/SynergyPlus_Files/`

### 屏幕布局编辑器

Web 界面提供可视化的拖拽式布局编辑器：

- 蓝色方块 = Master（本机），绿色方块 = Server（远程）
- 拖拽 Server 方块到 Master 任意一侧
- 自动吸附对齐
- 支持多 Server 布局

### 配置文件

| 配置文件 | 路径 |
|---------|------|
| Master | `~/.synergyplus/master_config.json` |
| Server | `~/.synergyplus/server_config.json` |

**剪贴板配置示例**（在配置文件中）：
```json
{
  "clipboard": {
    "enabled": true,
    "max_file_size": 104857600
  }
}
```
`max_file_size` 单位为字节，默认 100MB（104857600）。

## 项目结构

```
SynergyPlus/
├── master.py              # Master 端 Flask 应用
├── server.py              # Server 端 Flask 应用
├── protocol.py            # 通信协议（消息类型、序列化）
├── input_controller.py    # 输入控制（鼠标/键盘模拟与监听）
├── clipboard_sync.py      # 剪贴板同步与文件传输
├── config.py              # 配置管理
├── templates/
│   ├── index.html         # Server Web UI
│   └── master.html        # Master Web UI
├── static/
│   ├── css/
│   │   ├── style.css      # 通用样式
│   │   └── master.css     # Master 专用样式
│   └── js/
│       ├── app.js         # Server 前端逻辑
│       └── master.js      # Master 前端逻辑（拖拽布局）
├── requirements.txt       # Python 依赖
├── build.py               # PyInstaller 打包脚本
└── README.md
```

## 通信协议

| 消息类型 | 方向 | 用途 |
|---------|------|------|
| `screen_info` | Server → Master | 报告屏幕分辨率 |
| `enter_screen` | Master → Server | 鼠标进入 Server 屏幕 |
| `leave_screen` | Server → Master | 鼠标离开 Server 屏幕 |
| `mouse_move` | Master → Server | 鼠标移动 |
| `mouse_click` | Master → Server | 鼠标点击 |
| `mouse_scroll` | Master → Server | 滚轮滚动 |
| `key_press/release` | Master → Server | 键盘按键 |
| `clipboard_sync` | 双向 | 剪贴板文本同步 |
| `file_transfer_*` | 双向 | 文件分块传输 |
| `heartbeat/ack` | 双向 | 心跳保活 |

## 权限要求

### macOS

首次运行需要授予**辅助功能权限**：

> 系统设置 → 隐私与安全性 → 辅助功能 → 添加你的终端应用

⚠️ 开启输入抑制（suppress）模式也需要此权限。

### Linux

```bash
sudo usermod -a -G input $USER
# 重新登录生效
```

## ⚠️ 安全提示

- 仅用于局域网内可信设备之间
- 当前版本**未加密**通信内容
- 请勿在公共网络中使用
- 建议通过防火墙限制端口访问

## 常见问题

**Q: 无法连接到 Server**
- 确认 Server 已启动且显示 Running
- 检查 IP 和端口是否正确
- 确认防火墙未阻止端口（默认 9999）

**Q: 鼠标无法跨屏**
- 确认已在布局编辑器中将 Server 拖到 Master 旁边并保存
- 确认已点击 Enable Control
- 检查 macOS 辅助功能权限

**Q: 键盘在两台电脑上同时响应**
- 确认 macOS 辅助功能权限已开启（需要支持 suppress 模式）

**Q: 剪贴板不同步**
- 检查配置文件中 `clipboard.enabled` 是否为 `true`
- 文件传输检查文件大小是否超过 `max_file_size` 限制

## 许可证

MIT License

---

**享受多屏协同的乐趣！** 🚀
