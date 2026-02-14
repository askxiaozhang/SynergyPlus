# SynergyPlus

局域网鼠标键盘远程控制系统 - 通过Master控制多个Server的鼠标和键盘

## 功能特性

- ✨ **Master-Server架构**: 一个Master端可以连接并控制多个Server端
- 🖱️ **完整的鼠标控制**: 移动、点击（左/右/中键）、滚轮
- ⌨️ **完整的键盘控制**: 所有按键支持，包括特殊键和组合键
- 🎨 **图形界面**: 简洁易用的GUI界面
- ⚙️ **可视化配置**: 支持端口、自动启动、热键、服务器列表等配置
- 💾 **配置持久化**: 自动保存配置到JSON文件
- 🔒 **安全控制**: Server端支持IP白名单功能
- 🔌 **TCP Socket通信**: 稳定的网络连接
- 📦 **跨平台支持**: 支持macOS和Linux
- 🚀 **独立可执行文件**: 使用PyInstaller打包，无需Python环境

## 系统要求

- Python 3.9+（开发运行，macOS上pyobjc依赖要求）
- macOS 10.12+ 或 Linux（Ubuntu 18.04+, Fedora 30+等）
- 局域网网络连接

## 快速开始

### 方式一：源码运行

1. **克隆或下载项目**
   ```bash
   cd /Users/zhangchang/gitlab/SynergyPlus
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **启动Server端（被控制端）**
   ```bash
   python server.py
   ```
   - 在GUI中点击"Start Server"
   - 记住显示的端口号（默认9999）

4. **启动Master端（控制端）**
   ```bash
   python master.py
   ```
   - 输入Server的IP地址和端口号
   - 点击"Connect"连接到Server
   - 选择Server并点击"Set Active"
   - 点击"Enable Control"开始控制

### 方式二：使用打包的可执行文件

1. **打包应用**
   ```bash
   python build.py
   ```

2. **运行可执行文件**
   ```bash
   # Server端
   ./dist/SynergyPlus-Server/SynergyPlus-Server
   
   # Master端
   ./dist/SynergyPlus-Master/SynergyPlus-Master
   ```

## 使用说明

### Server端

1. 启动应用
2. (可选) 点击"Settings"配置：
   - 监听端口
   - 自动启动选项
   - IP白名单（安全功能）
3. 点击"Start Server"开始监听
4. 等待Master连接

**配置文件位置**: `~/.synergyplus/server_config.json`

### Master端

1. 启动应用
2. (可选) 点击"Settings"配置：
   - 默认端口
   - 连接超时
   - 自动连接选项
   - 热键设置
3. 添加Server：
   - 输入Server的IP地址（如192.168.1.100）
   - 输入Server的端口号（默认9999）
   - 点击"Connect"
4. 设置活动Server：
   - 在服务器列表中选择一个Server
   - 点击"Set Active"
5. 开始控制：
   - 点击"Enable Control"
   - 现在你的鼠标键盘操作会被转发到Server端

**配置文件位置**: `~/.synergyplus/master_config.json`

**注意**: 
- Master端会自动保存已连接的服务器列表
- Server端可以配置IP白名单，例如：
  - 单个IP: `192.168.1.100`
  - 网段: `192.168.1.0/24`

### 多Server控制

- 可以连接多个Server
- 同一时间只能控制一个Server（活动Server）
- 通过"Set Active"切换控制目标
- 切换前会自动禁用当前控制

## 项目结构

```
SynergyPlus/
├── config.py              # 配置文件和ConfigManager
├── config_dialog.py       # 配置对话框
├── protocol.py            # 通信协议
├── input_controller.py    # 输入控制器
├── server.py             # Server端应用
├── master.py             # Master端应用
├── requirements.txt      # Python依赖
├── build.py              # 打包脚本
└── README.md             # 本文件
```

## 技术架构

### 通信协议

- **传输层**: TCP Socket
- **消息格式**: JSON + 长度前缀
- **消息类型**: 
  - `mouse_move`: 鼠标移动
  - `mouse_click`: 鼠标点击
  - `mouse_scroll`: 鼠标滚轮
  - `key_press`: 键盘按下
  - `key_release`: 键盘释放
  - `heartbeat`: 心跳保活

### 核心依赖

- **pynput**: 跨平台的鼠标键盘监听和控制库
- **tkinter**: Python标准GUI库
- **PyInstaller**: Python应用打包工具

## 权限要求

### macOS

在首次运行时，需要授予以下权限：

1. **辅助功能权限**（Accessibility）
   - 系统偏好设置 → 安全性与隐私 → 隐私 → 辅助功能
   - 添加Terminal或应用程序到允许列表

### Linux

某些Linux发行版可能需要：

```bash
# 添加用户到input组
sudo usermod -a -G input $USER

# 重新登录以应用更改
```

## 安全提示

> ⚠️ **重要安全提示**
> - 此工具仅用于局域网内的合法设备控制
> - 当前版本**没有加密和身份认证机制**
> - **请勿在不受信任的网络中使用**
> - 建议在防火墙中限制端口访问范围
> - 仅在可信赖的设备之间使用

## 常见问题

### 1. 无法连接到Server

- 检查Server是否已启动并显示"Running"状态
- 确认IP地址和端口号正确
- 检查防火墙设置，确保端口未被阻止
- 确保Master和Server在同一局域网内

### 2. 鼠标/键盘控制无响应

- 检查是否已点击"Enable Control"
- 确认权限设置（macOS需要辅助功能权限）
- 查看Server端日志是否有错误信息

### 3. 打包后的应用无法启动

- macOS: 首次打开可能需要在"系统偏好设置 → 安全性与隐私"中允许
- 检查是否授予了必要的权限

### 4. 如何获取Server的IP地址

```bash
# macOS/Linux
ifconfig | grep inet

# 或者
ip addr show
```

## 开发与贡献

### 开发环境搭建

```bash
# 克隆项目
cd /Users/zhangchang/gitlab/SynergyPlus

# 安装开发依赖
pip install -r requirements.txt

# 运行测试
python server.py
python master.py
```

### 构建说明

```bash
# 安装PyInstaller
pip install pyinstaller

# 运行构建脚本
python build.py
```

## 许可证

本项目遵循MIT许可证。

## 联系方式

如有问题或建议，请提交Issue。

---

**享受远程控制的乐趣！** 🚀
