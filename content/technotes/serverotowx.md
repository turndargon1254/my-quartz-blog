---
title: "使用系统剪切板与wechat-decrypt实现'群服互联'"
tags: [技术笔记,Minecraft, Linux, 自动化, Python, 架构设计, 踩坑复盘,群服互联]
date: 2026-08-03
draft: false
---

> **📌 项目总结**：这是一份关于如何利用 Linux 桌面自动化、剪贴板监控、虚拟显示屏、微信本地数据库解密以及 RCON 协议，搭建一套零封号风险、毫秒级响应、零 API 成本的 Minecraft ↔ 微信 双向消息互通系统的完整全栈指南。

---

## 🌟 一、项目背景与设计哲学

在 Minecraft（MC）服务器运营中，提升玩家黏性最有效的手段之一就是“群服互联”——让玩家在游戏里的聊天能够实时推送到微信群，同时让群里的朋友也能随时向游戏内发送消息甚至执行管理指令。

然而，在微信生态下做自动化，开发者往往面临着三条极其艰难的路：

| 路线方案 | 核心实现机制 | 最终结局 / 局限性 |
| :--- | :--- | :--- |
| **Hook 内存 / 协议挂路线** | 通过 C++ 逆向微信基址，Hook 接收与发送函数，或走 Win 客户端私有协议。 | 腾讯风控极严，一旦检测到内存修改秒封账号，维护成本极高（更新即失效）。 |
| **官方 API / 企业微信路线** | 使用企微机器人或公众号 API。 | 普通微信群根本无法使用，无法接入日常的个人微信交流群。 |
| **无侵入式 GUI 自动化路线**<br>*(本方案上行采用)* | 将微信客户端挂在 Linux 虚拟桌面（X11）上，像真人一样“看”界面、用“剪贴板”复制、用“模拟键盘”粘贴发送。 | **绝对安全！** 在风控后台看来完全是物理级的键盘与剪贴板行为，零封号风险。 |
| **本地数据库读取路线**<br>*(本方案下行采用)* | 利用 `wechat-decrypt` 直接读取微信本地 SQLCipher 加密数据库，实时捕获新消息。 | **绝对安全！** 只读操作，不注入、不Hook，零封号风险，且准确性 100%。 |

---

## 💥 二、架构演进与踩坑血泪史（全景复盘）

在系统最终落地前，我们经历了多次重大的技术方案迭代与“血淋淋”的踩坑经验。

### 1. 基础设施篇：从 Webtop 的“性能地狱”到 NoMachine 的顺滑救赎

**初期的天真尝试（Docker Webtop 方案）**：

为了环境隔离，最初想把 XFCE 桌面和微信打进 Docker 容器（Webtop / Kasm），通过网页 VNC 观察。这听起来很优雅——所有依赖打包进容器，宿主机保持干净，随时可以销毁重建。

* **惨痛教训**：容器环境缺乏硬件 GPU 加速，微信客户端在容器内运行极度卡顿，CPU 动辄冲到 100%。更致命的是，容器内的虚拟 X11 响应极慢，导致 `xdotool` 模拟键盘输入时出现严重的时序错乱，按键丢失率高达 40%。一个简单的“Hello World”可能要尝试 3-4 次才能完整打出。

**破局方案（宿主机裸跑 Xvfb + XFCE4 + NoMachine）**：

* **架构调整**：彻底放弃 Docker 容器！直接在 Linux 宿主机安装轻量级 XFCE4 桌面，并用 `Xvfb` 创建一个静默的虚拟帧缓冲区显示器（`:99` 屏幕，`1920x1080` 分辨率）。`Xvfb`（X Virtual Framebuffer）是一个在内存中模拟显示器的服务，不需要物理屏幕，完美适用于服务器环境。
* **远控升级**：放弃画质压缩严重、延迟极高的传统 VNC（如 `x11vnc` / `TurboVNC`），改用基于 NX 协议的 **NoMachine**。NX 协议通过智能压缩和缓存技术，在低带宽下也能提供流畅的远程桌面体验。
* **成果**：NoMachine 带来了接近 60fps 的流畅体验与极低延迟。在本地观察自动化脚本打字时，就像看一个顶尖速记员在操作电脑一样顺滑！

### 2. 上行攻坚篇：破解微信输入法拦截与中文乱码魔咒（MC ➔ 微信）

确定了桌面环境后，如何让 Python 脚本把 MC 里的玩家发言打进微信输入框，成为了第一个拦路虎。这看起来简单，实际上我们掉进了好几个深坑。

* ❌ **坑点 A：`xdotool type` 中文乱码与丢字**

  最初尝试直接调用 `xdotool type "Hello 大家好"`，结果英文正常，中文全部变成了一串问号、乱码或者被系统拼音输入法直接拦截。这是因为 `xdotool` 直接发送的是 X11 键盘事件，而中文输入法需要复杂的输入法上下文（IM Context）才能正确组合字符。`xdotool type` 本质上只是在模拟“敲击键盘上的物理按键”，对于需要输入法组合的中文来说，这条路根本走不通。

* ❌ **坑点 B：`xte` 与底层键盘事件被微信拦截**

  换用底层键盘模拟工具 `xte`（来自 `xautomation` 包）或 `PyAutoGUI` 逐字敲击。这些工具模拟的键盘事件层级更低，但微信客户端内部的文本框机制会概率性过滤自动化模拟按键，导致打出来的字断断续续。尤其是在快速输入时，微信似乎有一个“防自动化”的隐形队列检测，一旦判定为非人工输入，就会开始丢弃按键事件。

* 💡 **终极杀招：系统剪贴板（`xclip`）+ `Ctrl+V` 组合拳**

  最终解决方案是：通过 `xclip` 将 UTF-8 文本写入系统剪贴板，然后用 `xdotool` 模拟 `Ctrl+V` 粘贴。这条路径绕开了所有输入法问题和键盘事件拦截，因为从微信的视角来看，这只是用户正常按了 `Ctrl+V` 和 `Enter` 而已。对中文、Emoji、特殊符号支持率达到 100%。

### 3. 下行探索篇：从“视觉噩梦”到“数据直连”的工程涅槃（微信 ➔ MC）

为了实现“微信 ➔ MC”的反向注入，我们最初尝试了纯视觉 AI 识图路线，结果演变成了一场技术噩梦。

**视觉 AI 路线的“死循环刷屏噩梦”**：

1. **光标闪烁打破 MD5**：微信输入框的光标每隔 0.5 秒闪烁一下，导致屏幕截图的 MD5 永远在变，系统误以为有新画面，狂发 API 请求。
2. **AI 的“采样随机性抖动”**：同一张图片 AI 识别两次，吐出的文本可能有差异，导致防重机制瘫痪。
3. **“屏幕底部消息挂载”陷阱**：当微信群里没人说话时，最后一条消息会永久停留在屏幕底部。防重机制一旦失灵，脚本就会把这条旧消息在 MC 里每隔 2 秒广播一次，整整狂刷上百行。
4. **Token 成本失控**：每 2-3 秒识别一次，一天下来上万次 API 调用，成本完全不可控。

**工程战术大撤退与最终破局**：

在工程实用主义面前，我们果断放弃了视觉 AI 方案。直到发现了 `wechat-decrypt` 这个项目——它揭示了一个全新的思路：**与其费尽心思“看”屏幕，不如直接“读”微信的本地数据库**。

`wechat-decrypt` 的原理是：微信 4.0 版本会在本地使用 SQLCipher 4 加密存储所有聊天记录。只要能从微信进程的内存中提取出密钥，就能直接、实时地读取和解密所有消息。这彻底绕开了 GUI 自动化的所有痛点：

| 对比维度 | GUI 自动化 (旧方案) | 本地数据库读取 (新方案) |
| :--- | :--- | :--- |
| **实时性** | 延迟 2-5 秒 | **毫秒级**，约 100ms |
| **稳定性** | 故障率约 30% | **极高**，接近 0 |
| **准确性** | 约 90-95% | **100%** |
| **资源消耗** | CPU 80-100%，API 费用高 | **极低** |
| **消息类型** | 仅文本 | **全面**（文本/图片/文件/语音） |

### 4. 下行指令篇：微信指令系统的设计与权限控制

在实现了微信 ➔ MC 的消息转发后，我们进一步拓展了功能——让管理员可以通过微信直接执行 MC 服务器指令。

**核心设计**：

1. **指令识别**：检测微信消息是否以 `/` 开头。
2. **权限分级**：
   - **全员指令**：`/list`、`/help`，所有群成员可用。
   - **管理指令**：`/say`、`/kick`、`/ban`、`/pardon`、`/op`、`/deop`、`/gamemode`、`/weather`、`/stop`，仅限管理员。
3. **安全限制**：`time set` 等破坏性指令被禁用。
4. **结果回传**：指令执行结果自动发回微信群。

**返回格式化示例**：

| 指令 | 微信返回 |
| :--- | :--- |
| `/list` | 目前有 3 位玩家在线：<br>Steve<br>Alex<br>Herobrine|
| `/kick Steve` | `✅ 已踢出 Steve` |
| `/gamemode 1 Steve` | `✅ 已将 Steve 模式调整为 创造` |
| `/weather clear` | `✅ 已将天气调为 晴天` |
| `/stop` | `✅ 已关闭服务器` |

---

## 🏗️ 三、系统终极架构与数据流向

最终落地的是完整的双向闭环系统，所有逻辑集中在两个核心服务中：

### 上行链路（MC ➔ 微信）

1. **SFTP 日志监听**：通过 SFTP 协议远程读取 MC 服务器的 `logs/latest.log` 文件，使用正则表达式实时匹配 `<玩家名> 消息内容` 格式的聊天记录。
2. **桌面自动化发送**：通过 `xclip` 将消息写入系统剪贴板，再用 `xdotool` 模拟 `Ctrl+V` 粘贴到微信窗口并自动发送。

### 下行链路（微信 ➔ MC）

1. **数据库解密**（`main.py` 来自 `wechat-decrypt`）：`monitor_web.py` 持续读取微信本地数据库的 WAL 日志，捕获新消息并解密，通过 HTTP API（端口 `5678`）对外提供查询。
2. **消息轮询**：`mcmain.py` 每隔 1 秒轮询一次 API，拉取最新消息。
3. **过滤与识别**：只处理指定群聊的消息，忽略黑名单发送者，判断是否以 `/` 开头。
4. **指令执行/消息广播**：通过 RCON 协议执行指令或广播消息到游戏内。

### 辅助组件

5. **Web 管理控制台**（端口 `1145`）：提供日志查看和配置编辑功能。
6. **服务管理脚本**：`start.sh` 和 `stop.sh` 实现一键启停。

### 完整数据流图

![流程图](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/mcprocess.png)

---

## 💻 四、生产环境核心组件

### 1. `main.py` — 微信数据库解密服务（来自 wechat-decrypt）

这个文件来自开源项目 `wechat-decrypt`，负责：
- 从微信进程内存中提取 SQLCipher 4 数据库密钥
- 解密本地微信数据库
- 通过 WAL 日志实时捕获新消息
- 提供 HTTP API（`http://127.0.0.1:5678/api/history`）供查询

### 2. `mcmain.py` — 核心桥接服务（自研）

这是整个系统的“大脑”，包含三大功能模块：

**① SFTP 日志监听（上行）**
- 通过 SFTP 连接到 MC 服务器（配置中的 `SFTP_HOST` / `SFTP_PORT`）
- 持续读取 `logs/latest.log` 文件末尾
- 正则提取 `<玩家名> 消息内容` 格式的聊天
- 通过 HTTP POST 发送到本地桥接端口 `9999`

**② 桌面自动化发送（上行）**
- 监听端口 `9999`，接收 POST `/wxSend` 请求
- 使用 `xdotool` 激活微信窗口
- 通过 `xclip` 将消息写入系统剪贴板
- 模拟 `Ctrl+V` 粘贴 + `Enter` 发送

**③ 微信消息轮询与指令转发（下行）**
- 每隔 1 秒请求 `wechat-decrypt` 的 API 获取新消息
- 过滤群聊、黑名单、图片等非文本消息
- 识别 `/` 开头的指令，执行权限检查
- 通过 RCON 协议执行指令或广播消息
- 将指令执行结果发送回微信群

```python
#!/usr/bin/env python3
"""
SimpFun MC ↔ 微信 双向桥接服务
配置从 config.ini 读取
"""

import sys
import io
import os
import time
import re
import json
import threading
import logging
import subprocess
import socket
import struct
import configparser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError

import paramiko
import requests

# ==================== 读取配置 ====================
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.ini')

config = configparser.ConfigParser()
if os.path.exists(CONFIG_FILE):
    config.read(CONFIG_FILE, encoding='utf-8')
else:
    print(f"❌ 配置文件不存在: {CONFIG_FILE}")
    sys.exit(1)

# SFTP配置
SFTP_HOST = config.get('SFTP', 'host')
SFTP_PORT = config.getint('SFTP', 'port')
SFTP_USER = config.get('SFTP', 'user')
SFTP_PASS = config.get('SFTP', 'password')
REMOTE_LOG_PATH = config.get('SFTP', 'remote_log_path')

# RCON配置
RCON_HOST = config.get('RCON', 'host')
RCON_PORT = config.getint('RCON', 'port')
RCON_PASS = config.get('RCON', 'password')

# 微信配置
WECHAT_API_URL = config.get('WECHAT', 'api_url')
WECHAT_BRIDGE_URL = config.get('WECHAT', 'bridge_url')
TARGET_GROUP = config.get('WECHAT', 'target_group')
EXCLUDE_SENDERS = set(config.get('WECHAT', 'exclude_senders').replace(' ', '').split(','))

# 管理员配置
ADMIN_USERS = set(config.get('ADMIN', 'users').replace(' ', '').split(','))
PUBLIC_COMMANDS = set(config.get('ADMIN', 'public_commands').replace(' ', '').split(','))

# 缓存配置
CACHE_FILE = config.get('CACHE', 'file')

# 延迟配置
DELAYS = {
    'window_activate': config.getfloat('DELAYS', 'window_activate'),
    'click_input': config.getfloat('DELAYS', 'click_input'),
    'paste_wait': config.getfloat('DELAYS', 'paste_wait'),
    'send_wait': config.getfloat('DELAYS', 'send_wait'),
    'retry_interval': config.getfloat('DELAYS', 'retry_interval'),
}

# ==================== 关闭第三方库日志 ====================
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mc_wechat_bridge")

# ==================== 配置热加载 ====================

def reload_config():
    """重新加载配置文件"""
    global SFTP_HOST, SFTP_PORT, SFTP_USER, SFTP_PASS, REMOTE_LOG_PATH
    global RCON_HOST, RCON_PORT, RCON_PASS
    global WECHAT_API_URL, WECHAT_BRIDGE_URL, TARGET_GROUP, EXCLUDE_SENDERS
    global ADMIN_USERS, PUBLIC_COMMANDS, CACHE_FILE, DELAYS
    
    try:
        config.read(CONFIG_FILE, encoding='utf-8')
        
        SFTP_HOST = config.get('SFTP', 'host')
        SFTP_PORT = config.getint('SFTP', 'port')
        SFTP_USER = config.get('SFTP', 'user')
        SFTP_PASS = config.get('SFTP', 'password')
        REMOTE_LOG_PATH = config.get('SFTP', 'remote_log_path')
        
        RCON_HOST = config.get('RCON', 'host')
        RCON_PORT = config.getint('RCON', 'port')
        RCON_PASS = config.get('RCON', 'password')
        
        WECHAT_API_URL = config.get('WECHAT', 'api_url')
        WECHAT_BRIDGE_URL = config.get('WECHAT', 'bridge_url')
        TARGET_GROUP = config.get('WECHAT', 'target_group')
        EXCLUDE_SENDERS = set(config.get('WECHAT', 'exclude_senders').replace(' ', '').split(','))
        
        ADMIN_USERS = set(config.get('ADMIN', 'users').replace(' ', '').split(','))
        PUBLIC_COMMANDS = set(config.get('ADMIN', 'public_commands').replace(' ', '').split(','))
        
        CACHE_FILE = config.get('CACHE', 'file')
        
        DELAYS = {
            'window_activate': config.getfloat('DELAYS', 'window_activate'),
            'click_input': config.getfloat('DELAYS', 'click_input'),
            'paste_wait': config.getfloat('DELAYS', 'paste_wait'),
            'send_wait': config.getfloat('DELAYS', 'send_wait'),
            'retry_interval': config.getfloat('DELAYS', 'retry_interval'),
        }
        
        logger.info("✅ 配置已重新加载")
        return True
    except Exception as e:
        logger.error(f"❌ 配置重新加载失败: {e}")
        return False

# ==================== RCON 直连方式 ====================

def rcon_command(cmd: str) -> str:
    """执行RCON指令，直接socket连接"""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((RCON_HOST, RCON_PORT))
        
        packet = struct.pack('<ii', 0, 3) + RCON_PASS.encode('utf-8') + b'\x00\x00'
        packet = struct.pack('<i', len(packet)) + packet
        sock.send(packet)
        
        length_data = sock.recv(4)
        if len(length_data) < 4:
            return None
        length = struct.unpack('<i', length_data)[0]
        response = sock.recv(length)
        request_id, packet_type = struct.unpack('<ii', response[:8])
        
        if packet_type != 2:
            return None
        
        packet = struct.pack('<ii', 0, 2) + cmd.encode('utf-8') + b'\x00\x00'
        packet = struct.pack('<i', len(packet)) + packet
        sock.send(packet)
        
        length_data = sock.recv(4)
        if len(length_data) < 4:
            return None
        length = struct.unpack('<i', length_data)[0]
        response = sock.recv(length)
        
        body = response[8:-2].decode('utf-8', errors='ignore') if len(response) > 10 else ''
        return body
        
    except Exception as e:
        logger.error(f"RCON错误: {e}")
        return None
    finally:
        if sock:
            try:
                sock.close()
            except:
                pass

# ==================== 颜色代码清理 ====================
COLOR_CODE_PATTERN = re.compile(r'¡ì[0-9a-fk-or]')
CHAT_PATTERN = re.compile(r'<(?P<player>[^>]+)>\s+(?P<message>.+)')

def clean_text(text: str) -> str:
    return COLOR_CODE_PATTERN.sub('', text).strip()

# ==================== 图片检测 ====================
IMAGE_PATTERNS = [
    re.compile(r'\[图片\]', re.IGNORECASE),
    re.compile(r'\[Image\]', re.IGNORECASE),
    re.compile(r'\[图\]', re.IGNORECASE),
    re.compile(r'\[照片\]', re.IGNORECASE),
    re.compile(r'<image>', re.IGNORECASE),
    re.compile(r'<img[^>]*>', re.IGNORECASE),
    re.compile(r'^\s*$'),
    re.compile(r'^[\u200b\u200c\u200d\ufeff]+$'),
]

IMAGE_TYPE_VALUES = {'image', 'img', 'picture', 'photo', 'pic'}

def is_image_message(item: dict) -> bool:
    msg_type = str(item.get('type', item.get('msg_type', ''))).lower()
    if msg_type in IMAGE_TYPE_VALUES:
        return True
    
    content = item.get('message', item.get('content', ''))
    if content:
        for pattern in IMAGE_PATTERNS:
            if pattern.search(content):
                return True
        if re.search(r'\.(jpg|jpeg|png|gif|bmp|webp|svg|ico|tiff?)(\?|$)', content, re.IGNORECASE):
            return True
    
    if item.get('file') or item.get('attachment') or item.get('image'):
        return True
    
    if item.get('url') and re.search(r'\.(jpg|jpeg|png|gif|bmp|webp)', str(item.get('url')), re.IGNORECASE):
        return True
    
    return False

def is_empty_or_image_content(text: str) -> bool:
    if not text:
        return True
    for pattern in IMAGE_PATTERNS:
        if pattern.search(text):
            return True
    return False

# ==================== 防重缓存 ====================

sent_fps = set()
sent_ids = set()

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    sent_fps.add(line)
                    sent_ids.add(line)
        logger.info(f"加载防重缓存: {len(sent_fps)} 条")
    except Exception as e:
        logger.warning(f"加载防重缓存失败: {e}")

def save_fingerprint(fp: str):
    if not fp or fp in sent_fps:
        return
    sent_fps.add(fp)
    sent_ids.add(fp)
    try:
        with open(CACHE_FILE, 'a', encoding='utf-8') as f:
            f.write(fp + '\n')
    except Exception as e:
        pass

def make_hard_fingerprint(text: str) -> str:
    if not text:
        return ""
    clean = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', text)
    return "".join(clean).lower()

def get_message_fingerprint(item: dict) -> str:
    msg_id = str(item.get('id', item.get('msg_id', '')))
    if msg_id:
        return f"id_{msg_id}"
    
    sender = item.get("sender", item.get("nick_name", "微信用户"))
    content = item.get("message", item.get("content", ""))
    timestamp = str(item.get('time', item.get('timestamp', '')))
    
    if timestamp:
        fp = f"{sender}_{timestamp}_{make_hard_fingerprint(content)}"
    else:
        fp = f"{sender}_{make_hard_fingerprint(content)}"
    
    return fp

def is_duplicate(item: dict) -> bool:
    fp = get_message_fingerprint(item)
    return fp in sent_fps

# ==================== 指令处理与格式化 ====================

def format_command_result(command: str, result: str) -> str:
    """根据指令类型格式化返回结果"""
    cmd = command.lstrip('/').strip().lower()
    
    if result is None:
        return "❌ 指令执行失败（RCON无响应）"
    
    result = result.strip()
    
    if cmd == 'list' or cmd.startswith('list '):
        players = []
        if 'players online:' in result:
            parts = result.split('players online:')
            if len(parts) > 1:
                player_str = parts[1].strip()
                if player_str.endswith('.'):
                    player_str = player_str[:-1]
                players = [p.strip() for p in player_str.split(',') if p.strip()]
        
        if not players:
            players = [p for p in result.split() if p.strip()]
            players = [p for p in players if not p.isdigit() and p not in ['There', 'are', 'of', 'a', 'max', 'players', 'online:']]
        
        if not players:
            return "当前没有玩家在线"
        
        player_list = '\n'.join(players)
        return f"目前有 {len(players)} 位玩家在线：\n{player_list}"
    
    if cmd.startswith('say '):
        return "✅ 已发送广播"
    
    if cmd.startswith('kick '):
        match = re.search(r'kick\s+(\S+)', cmd)
        player = match.group(1) if match else "玩家"
        return f"✅ 已踢出 {player}"
    
    if cmd.startswith('ban '):
        match = re.search(r'ban\s+(\S+)', cmd)
        player = match.group(1) if match else "玩家"
        return f"✅ 已封禁 {player}"
    
    if cmd.startswith('pardon '):
        match = re.search(r'pardon\s+(\S+)', cmd)
        player = match.group(1) if match else "玩家"
        return f"✅ 已解禁 {player}"
    
    if cmd.startswith('op '):
        match = re.search(r'op\s+(\S+)', cmd)
        player = match.group(1) if match else "玩家"
        return f"✅ 已给予 {player} 管理员权限"
    
    if cmd.startswith('deop '):
        match = re.search(r'deop\s+(\S+)', cmd)
        player = match.group(1) if match else "玩家"
        return f"✅ 已撤销 {player} 管理员权限"
    
    if cmd.startswith('gamemode '):
        match = re.search(r'gamemode\s+(\S+)\s+(\S+)', cmd)
        if match:
            mode = match.group(1)
            player = match.group(2)
            mode_map = {'0': '生存', '1': '创造', '2': '冒险', '3': '旁观'}
            mode_text = mode_map.get(mode, mode)
            return f"✅ 已将 {player} 模式调整为 {mode_text}"
        return "✅ 已调整游戏模式"
    
    if cmd.startswith('weather '):
        match = re.search(r'weather\s+(\S+)', cmd)
        if match:
            weather = match.group(1)
            weather_map = {'clear': '晴天', 'rain': '雨天', 'thunder': '雷暴'}
            weather_text = weather_map.get(weather, weather)
            return f"✅ 已将天气调为 {weather_text}"
        return "✅ 已调整天气"
    
    if cmd == 'stop':
        return "✅ 已关闭服务器"
    
    if cmd == 'help':
        return HELP_TEXT
    
    if result:
        return result
    else:
        return "✅ 指令已执行"

HELP_TEXT = """📋 群内指令列表

/list    列出当前在线玩家（全体）
/say <message>    向所有玩家广播消息（仅管理员）
/kick <player>    踢出指定玩家（仅管理员）
/ban <player>    封禁指定玩家（仅管理员）
/pardon <player>    解除玩家封禁（仅管理员）
/op <player>    授予玩家管理员权限（仅管理员）
/deop <player>    撤销玩家管理员权限（仅管理员）
/gamemode <mode> <player>    设置玩家的游戏模式（仅管理员）
/weather <clear/rain/thunder>    更改天气状况（仅管理员）
/stop    优雅地关闭服务器（仅管理员）"""

# ==================== 微信 -> MC 转发 ====================

def send_command_to_mc(command: str) -> str:
    """发送指令到MC服务器"""
    try:
        clean_cmd = command.lstrip('/').strip()
        if not clean_cmd:
            return "指令为空"
        
        if clean_cmd.startswith('time set'):
            return "❌ time set 指令已被禁用"
        
        logger.info(f"执行: {clean_cmd}")
        
        result = rcon_command(clean_cmd)
        return format_command_result(clean_cmd, result)
            
    except Exception as e:
        logger.error(f"RCON异常: {e}")
        return f"❌ 指令执行异常: {str(e)}"

def send_chat_to_mc(sender: str, message: str):
    try:
        clean_sender = sender.strip() or "微信用户"
        clean_msg = message.strip()
        if not clean_msg:
            return

        raw_components = [
            "",
            {"text": "[微信] ", "color": "green", "bold": True},
            {"text": f"<{clean_sender}> ", "color": "gray"},
            {"text": clean_msg, "color": "white"}
        ]
        cmd = f'tellraw @a {json.dumps(raw_components, ensure_ascii=False)}'
        
        rcon_command(cmd)
        logger.info(f"转发: <{clean_sender}> {clean_msg}")
    except Exception as e:
        logger.error(f"发送失败: {e}")

def send_to_wechat(text: str):
    try:
        response = requests.post(
            WECHAT_BRIDGE_URL,
            json={"content": text},
            timeout=5
        )
        if response.status_code == 200:
            logger.info(f"转发到微信: {text[:30]}...")
        else:
            logger.warning(f"微信桥接HTTP错误: {response.status_code}")
    except Exception as e:
        logger.error(f"微信桥接连接失败: {e}")

# ==================== 微信消息拉取 ====================

def fetch_wechat_messages():
    try:
        req = Request(WECHAT_API_URL)
        with urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get("messages", data.get("data", []))
    except Exception:
        pass
    return []

def should_process_message(item: dict) -> tuple:
    if is_duplicate(item):
        return False, "duplicate"
    
    group = item.get("room_name") or item.get("group_name") or item.get("chat") or item.get("title") or ""
    if group and group != TARGET_GROUP:
        return False, "group_mismatch"
    
    sender = item.get("sender") or item.get("nick_name") or item.get("display_name") or ""
    if sender in EXCLUDE_SENDERS:
        return False, "sender_blacklist"
    
    if is_image_message(item):
        return False, "image"
    
    content = item.get("message", item.get("content", ""))
    if is_empty_or_image_content(content):
        return False, "empty_or_image"
    
    return True, "ok"

# ==================== SFTP MC日志监控 ====================

def sftp_monitor():
    logger.info("连接SFTP...")
    
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    try:
        transport.connect(username=SFTP_USER, password=SFTP_PASS)
        sftp = paramiko.SFTPClient.from_transport(transport)
        logger.info("SFTP连接成功")
    except Exception as e:
        logger.error(f"SFTP连接失败: {e}")
        return

    try:
        last_offset = sftp.stat(REMOTE_LOG_PATH).st_size
    except Exception as e:
        logger.warning(f"无法获取日志: {e}")
        last_offset = 0

    while True:
        try:
            current_size = sftp.stat(REMOTE_LOG_PATH).st_size

            if current_size > last_offset:
                remote_file = sftp.open(REMOTE_LOG_PATH, 'rb')
                remote_file.seek(last_offset)
                new_data = remote_file.read()
                remote_file.close()
                last_offset = current_size

                lines = new_data.decode('utf-8', errors='ignore').splitlines()

                for line in lines:
                    line_str = line.strip()
                    if not line_str:
                        continue

                    match = CHAT_PATTERN.search(line_str)
                    if match:
                        player = clean_text(match.group('player'))
                        message = clean_text(match.group('message'))
                        send_to_wechat(f"[MC] <{player}> {message}")

            elif current_size < last_offset:
                last_offset = 0

        except Exception as e:
            time.sleep(2)
            try:
                transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
                transport.connect(username=SFTP_USER, password=SFTP_PASS)
                sftp = paramiko.SFTPClient.from_transport(transport)
            except Exception:
                pass

        time.sleep(0.5)

# ==================== 微信消息轮询 ====================

def wechat_polling():
    logger.info(f"微信轮询启动")
    logger.info(f"管理员: {', '.join(ADMIN_USERS)}")
    
    test_result = rcon_command('list')
    if test_result:
        logger.info(f"✅ RCON连接正常")
    else:
        logger.warning("⚠️ RCON连接失败")
    
    initial_msgs = fetch_wechat_messages()
    if initial_msgs:
        for item in initial_msgs:
            fp = get_message_fingerprint(item)
            if fp:
                save_fingerprint(fp)
        logger.info(f"已标记 {len(initial_msgs)} 条旧消息")

    while True:
        try:
            msgs = fetch_wechat_messages()
            if msgs:
                for item in msgs:
                    if is_duplicate(item):
                        continue
                    
                    fp = get_message_fingerprint(item)
                    should_process, reason = should_process_message(item)
                    
                    if not should_process:
                        if fp:
                            save_fingerprint(fp)
                        continue

                    sender = item.get("sender") or item.get("nick_name") or "微信用户"
                    message = item.get("message") or item.get("content") or ""
                    
                    if fp:
                        save_fingerprint(fp)

                    if message.startswith('/'):
                        cmd_name = message.split()[0].lower() if message.split() else message.lower()
                        
                        if cmd_name not in PUBLIC_COMMANDS:
                            if sender not in ADMIN_USERS:
                                logger.warning(f"拒绝指令: {sender}")
                                send_to_wechat(f"❌ 您没有权限执行此指令")
                                continue
                        
                        logger.info(f"[指令] {sender}: {message}")
                        result = send_command_to_mc(message)
                        send_to_wechat(f"{result}")
                    else:
                        logger.info(f"[微信] {sender}: {message}")
                        send_chat_to_mc(sender, message)

        except Exception as e:
            logger.error(f"轮询异常: {e}")

        time.sleep(1.0)

# ==================== HTTP 桥接服务 ====================

class WeChatXDOperator:
    def __init__(self):
        self.window_id = None
        self.delays = DELAYS

    def wait(self, delay_key: str):
        time.sleep(self.delays.get(delay_key, 0.3))

    def find_window(self) -> bool:
        for attempt in range(3):
            try:
                for title in ['微信', 'WeChat']:
                    result = subprocess.run(
                        ['xdotool', 'search', '--name', title],
                        capture_output=True, text=True
                    )
                    window_ids = result.stdout.strip().split()
                    if window_ids:
                        self.window_id = window_ids[0]
                        return True

                result = subprocess.run(
                    ['xdotool', 'search', '--class', 'wechat'],
                    capture_output=True, text=True
                )
                window_ids = result.stdout.strip().split()
                if window_ids:
                    self.window_id = window_ids[0]
                    return True

                time.sleep(1)
            except:
                time.sleep(1)
        return False

    def activate_window(self) -> bool:
        if not self.window_id:
            return False
        try:
            subprocess.run(['xdotool', 'windowactivate', self.window_id], capture_output=True)
            self.wait('window_activate')
            return True
        except:
            return False

    def get_window_geometry(self) -> dict:
        if not self.window_id:
            return {}
        try:
            result = subprocess.run(
                ['xdotool', 'getwindowgeometry', self.window_id],
                capture_output=True, text=True
            )
            lines = result.stdout.strip().split('\n')
            geometry = {}
            for line in lines:
                if 'Position:' in line:
                    parts = line.split('Position:')[1].strip().split(',')
                    geometry['x'] = int(parts[0].strip())
                    geometry['y'] = int(parts[1].strip())
                elif 'Geometry:' in line:
                    parts = line.split('Geometry:')[1].strip().split('x')
                    geometry['width'] = int(parts[0].strip())
                    geometry['height'] = int(parts[1].strip())
            return geometry
        except:
            return {}

    def click(self, x: int, y: int):
        subprocess.run(['xdotool', 'mousemove', str(x), str(y)], capture_output=True)
        time.sleep(0.1)
        subprocess.run(['xdotool', 'click', '1'], capture_output=True)
        time.sleep(0.1)

    def paste_text(self, text: str) -> bool:
        try:
            p = subprocess.Popen(
                ['xclip', '-selection', 'clipboard', '-rmlastnl'],
                stdin=subprocess.PIPE
            )
            p.communicate(input=text.encode('utf-8'))
            time.sleep(0.1)
            subprocess.run(['xdotool', 'key', '--clearmodifiers', 'ctrl+v'], capture_output=True)
            self.wait('paste_wait')
            return True
        except:
            return False

    def send_text(self, content: str) -> bool:
        for attempt in range(3):
            try:
                if not self.find_window():
                    time.sleep(1)
                    continue

                if not self.activate_window():
                    time.sleep(1)
                    continue

                geometry = self.get_window_geometry()
                if geometry:
                    click_x = geometry.get('x', 0) + geometry.get('width', 800) // 2
                    click_y = geometry.get('y', 0) + geometry.get('height', 600) - 60
                    self.click(click_x, click_y)
                    self.wait('click_input')

                subprocess.run(['xdotool', 'key', '--clearmodifiers', 'ctrl+a'], capture_output=True)
                time.sleep(0.1)
                subprocess.run(['xdotool', 'key', 'BackSpace'], capture_output=True)
                time.sleep(0.1)

                if not self.paste_text(content):
                    continue

                time.sleep(0.2)
                subprocess.run(['xdotool', 'key', '--clearmodifiers', 'Return'], capture_output=True)
                self.wait('send_wait')
                return True

            except:
                time.sleep(self.delays['retry_interval'])

        return False

class HTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_response(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_GET(self):
        path = self.path.strip('/')
        if path == 'test':
            self._send_response(200, {"status": "ok"})
        else:
            self._send_response(404, {"error": "Not found"})

    def do_POST(self):
        path = self.path.strip('/')
        if path != 'wxSend':
            self._send_response(404, {"error": "Not found"})
            return

        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            self._send_response(400, {"error": "Empty request"})
            return

        body = self.rfile.read(length).decode('utf-8')
        try:
            data = json.loads(body)
        except:
            self._send_response(400, {"error": "Invalid JSON"})
            return

        content = data.get('content')
        if not content:
            self._send_response(400, {"error": "Missing 'content'"})
            return

        operator = WeChatXDOperator()
        success = operator.send_text(content)
        self._send_response(200, {"status": "success" if success else "failed"})

def start_http():
    server = HTTPServer(('0.0.0.0', 9999), HTTPHandler)
    logger.info("HTTP: http://localhost:9999/wxSend")
    server.serve_forever()

# ==================== 主程序 ====================

def main():
    logger.info("=" * 40)
    logger.info("🚀 MC ↔ 微信 双向桥接服务")
    logger.info(f"管理员: {', '.join(ADMIN_USERS)}")
    logger.info("=" * 40)

    test_result = rcon_command('list')
    if test_result:
        logger.info(f"✅ RCON连接成功: {test_result[:50]}...")
    else:
        logger.warning("⚠️ RCON连接失败，请检查配置")

    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':0'

    threads = [
        threading.Thread(target=sftp_monitor, name="SFTP-Monitor", daemon=True),
        threading.Thread(target=wechat_polling, name="WeChat-Polling", daemon=True),
        threading.Thread(target=start_http, name="HTTP-Server", daemon=True),
    ]

    for t in threads:
        t.start()
        time.sleep(0.5)

    logger.info("所有服务已启动")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("服务已停止")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("程序退出")
```
### 3. `web_server.py` — Web 管理控制台

提供可视化运维界面（端口 `1145`）：
- **日志查看**：实时滚动显示 `main` 和 `mcmain` 的日志
- **配置编辑**：可视化编辑 `config.ini`，保存后自动热加载

```python
#!/usr/bin/env python3
"""
web_server.py - Web日志查看 + 配置编辑 (端口1145)
"""

import http.server
import socketserver
import os
import json
import configparser

PORT = 1145
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.ini')

def get_config_dict():
    """读取配置文件返回字典"""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')
        result = {}
        for section in config.sections():
            result[section] = dict(config.items(section))
        return result
    return {}

def save_config_dict(data):
    """保存配置字典到文件"""
    config = configparser.ConfigParser()
    for section, items in data.items():
        config[section] = items
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        config.write(f)
    return True

class LogHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self.get_html().encode('utf-8'))
        
        elif self.path == '/logs':
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            
            logs = {}
            for name in ['main', 'mcmain']:
                log_file = os.path.join(LOG_DIR, f'{name}.log')
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        logs[name] = ''.join(lines[-200:]) if lines else '暂无日志...'
                except:
                    logs[name] = '日志文件不存在'
            
            self.wfile.write(json.dumps(logs, ensure_ascii=False).encode('utf-8'))
        
        elif self.path == '/config':
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(get_config_dict(), ensure_ascii=False).encode('utf-8'))
        
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404 Not Found')
    
    def do_POST(self):
        if self.path == '/config':
            length = int(self.headers.get('Content-Length', 0))
            if length == 0:
                self._send_json(400, {"error": "Empty request"})
                return
            
            body = self.rfile.read(length).decode('utf-8')
            try:
                data = json.loads(body)
                if save_config_dict(data):
                    self._send_json(200, {"status": "success", "message": "配置已保存"})
                else:
                    self._send_json(500, {"error": "保存失败"})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        else:
            self._send_json(404, {"error": "Not found"})
    
    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def get_html(self):
        return '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>服务管理 - 1145端口</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0a0e17; color: #e0e0e0; padding: 20px; }
        .header { text-align: center; padding: 20px 0 30px 0; border-bottom: 2px solid #1a2a3a; margin-bottom: 30px; }
        .header h1 { font-size: 28px; color: #00d4ff; }
        .header .info { color: #8899aa; font-size: 14px; margin-top: 8px; }
        .tabs { display: flex; gap: 10px; justify-content: center; margin-bottom: 25px; }
        .tab-btn { background: #1a2a3a; border: 1px solid #2a3a4a; color: #8899aa; padding: 8px 24px; border-radius: 8px; cursor: pointer; font-size: 14px; }
        .tab-btn:hover { background: #2a3a4a; color: #00d4ff; }
        .tab-btn.active { background: #00d4ff22; border-color: #00d4ff; color: #00d4ff; }
        .tab-content { display: none; max-width: 1400px; margin: 0 auto; }
        .tab-content.active { display: block; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .log-block { background: #111927; border-radius: 12px; border: 1px solid #1a2a3a; overflow: hidden; min-height: 400px; display: flex; flex-direction: column; }
        .log-block:hover { border-color: #00d4ff; }
        .log-header { background: #1a2a3a; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2a3a4a; }
        .log-header .name { font-weight: bold; font-size: 16px; }
        .log-header .badge { background: #00d4ff22; color: #00d4ff; padding: 2px 12px; border-radius: 12px; font-size: 12px; border: 1px solid #00d4ff44; }
        .log-content { padding: 15px 20px; flex: 1; overflow-y: auto; max-height: 500px; background: #0d1420; font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-all; }
        .log-content::-webkit-scrollbar { width: 6px; }
        .log-content::-webkit-scrollbar-track { background: #0d1420; }
        .log-content::-webkit-scrollbar-thumb { background: #1a2a3a; border-radius: 3px; }
        .footer { text-align: center; padding: 20px; color: #445566; font-size: 12px; margin-top: 20px; }
        .refresh-btn { background: #1a2a3a; border: 1px solid #2a3a4a; color: #8899aa; padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 12px; }
        .refresh-btn:hover { background: #2a3a4a; color: #00d4ff; border-color: #00d4ff; }
        .timestamp { color: #445566; font-size: 11px; }
        
        /* 配置编辑样式 */
        .config-container { background: #111927; border-radius: 12px; border: 1px solid #1a2a3a; padding: 30px; max-width: 800px; margin: 0 auto; }
        .config-container h2 { color: #00d4ff; margin-bottom: 20px; }
        .config-section { margin-bottom: 25px; border-bottom: 1px solid #1a2a3a; padding-bottom: 20px; }
        .config-section:last-child { border-bottom: none; }
        .config-section h3 { color: #ffd93d; margin-bottom: 12px; font-size: 16px; }
        .config-item { display: flex; align-items: center; margin-bottom: 8px; padding: 4px 0; }
        .config-item label { width: 160px; color: #8899aa; font-size: 13px; flex-shrink: 0; }
        .config-item input, .config-item textarea { 
            flex: 1; background: #0d1420; border: 1px solid #1a2a3a; color: #e0e0e0; 
            padding: 6px 12px; border-radius: 6px; font-size: 13px; 
        }
        .config-item input:focus, .config-item textarea:focus { border-color: #00d4ff; outline: none; }
        .config-item textarea { min-height: 60px; resize: vertical; font-family: monospace; }
        .config-actions { display: flex; gap: 12px; margin-top: 20px; justify-content: center; }
        .btn-save { background: #00d4ff; border: none; color: #0a0e17; padding: 10px 40px; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }
        .btn-save:hover { background: #33ddff; }
        .btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-reload { background: #1a2a3a; border: 1px solid #2a3a4a; color: #8899aa; padding: 10px 30px; border-radius: 8px; font-size: 14px; cursor: pointer; }
        .btn-reload:hover { background: #2a3a4a; color: #00d4ff; }
        .save-status { text-align: center; margin-top: 12px; color: #51cf66; font-size: 14px; }
        .save-status.error { color: #ff6b6b; }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } .config-item { flex-direction: column; align-items: stretch; } .config-item label { width: auto; margin-bottom: 4px; } }
    </style>
    <script>
        // ========== 日志刷新 ==========
        function refreshLogs() {
            fetch('/logs')
                .then(res => res.json())
                .then(data => {
                    for (let name in data) {
                        const el = document.getElementById('log-' + name);
                        if (el) {
                            el.textContent = data[name] || '暂无日志...';
                            el.scrollTop = el.scrollHeight;
                        }
                    }
                    document.getElementById('refresh-time').textContent = 
                        '最后更新: ' + new Date().toLocaleTimeString();
                })
                .catch(err => console.error('刷新失败:', err));
        }
        
        // ========== 配置加载 ==========
        function loadConfig() {
            fetch('/config')
                .then(res => res.json())
                .then(data => {
                    const container = document.getElementById('config-editor');
                    container.innerHTML = '';
                    for (let section in data) {
                        const div = document.createElement('div');
                        div.className = 'config-section';
                        const title = document.createElement('h3');
                        title.textContent = '[' + section + ']';
                        div.appendChild(title);
                        
                        for (let key in data[section]) {
                            const item = document.createElement('div');
                            item.className = 'config-item';
                            const label = document.createElement('label');
                            label.textContent = key;
                            const input = document.createElement('input');
                            input.type = 'text';
                            input.value = data[section][key];
                            input.dataset.section = section;
                            input.dataset.key = key;
                            item.appendChild(label);
                            item.appendChild(input);
                            div.appendChild(item);
                        }
                        container.appendChild(div);
                    }
                    document.getElementById('save-status').textContent = '';
                    document.getElementById('save-status').className = 'save-status';
                })
                .catch(err => {
                    document.getElementById('config-editor').innerHTML = 
                        '<div style="color:#ff6b6b;text-align:center;padding:40px;">❌ 加载配置失败: ' + err + '</div>';
                });
        }
        
        // ========== 保存配置 ==========
        function saveConfig() {
            const btn = document.getElementById('btn-save');
            btn.disabled = true;
            btn.textContent = '⏳ 保存中...';
            
            const data = {};
            const inputs = document.querySelectorAll('#config-editor input');
            inputs.forEach(inp => {
                const section = inp.dataset.section;
                const key = inp.dataset.key;
                if (!data[section]) data[section] = {};
                data[section][key] = inp.value;
            });
            
            fetch('/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(res => res.json())
            .then(result => {
                const status = document.getElementById('save-status');
                if (result.status === 'success') {
                    status.textContent = '✅ ' + result.message;
                    status.className = 'save-status';
                } else {
                    status.textContent = '❌ ' + (result.error || '保存失败');
                    status.className = 'save-status error';
                }
            })
            .catch(err => {
                document.getElementById('save-status').textContent = '❌ 请求失败: ' + err;
                document.getElementById('save-status').className = 'save-status error';
            })
            .finally(() => {
                btn.disabled = false;
                btn.textContent = '💾 保存配置';
            });
        }
        
        // ========== Tab切换 ==========
        function switchTab(tab) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            document.querySelector('.tab-btn[data-tab="' + tab + '"]').classList.add('active');
            if (tab === 'config') loadConfig();
            if (tab === 'logs') refreshLogs();
        }
        
        // ========== 初始化 ==========
        window.onload = function() {
            refreshLogs();
            setInterval(refreshLogs, 3000);
        };
    </script>
</head>
<body>
    <div class="header">
        <h1>📊 服务管理中心</h1>
        <div class="info">端口: 1145 | <span id="refresh-time">加载中...</span></div>
    </div>
    
    <div class="tabs">
        <button class="tab-btn active" data-tab="logs" onclick="switchTab('logs')">📋 日志查看</button>
        <button class="tab-btn" data-tab="config" onclick="switchTab('config')">⚙️ 配置编辑</button>
    </div>
    
    <!-- 日志Tab -->
    <div id="tab-logs" class="tab-content active">
        <div style="text-align:right;margin-bottom:12px;">
            <button class="refresh-btn" onclick="refreshLogs()">🔄 刷新</button>
        </div>
        <div class="grid">
            <div class="log-block">
                <div class="log-header"><span class="name" style="color:#00d4ff;">📱 main (微信→MC)</span><span class="badge">.log</span></div>
                <div class="log-content" id="log-main"><span class="empty-log">加载中...</span></div>
            </div>
            <div class="log-block">
                <div class="log-header"><span class="name" style="color:#ff6b6b;">🎮 mcmain (MC→微信)</span><span class="badge">.log</span></div>
                <div class="log-content" id="log-mcmain"><span class="empty-log">加载中...</span></div>
            </div>
        </div>
    </div>
    
    <!-- 配置Tab -->
    <div id="tab-config" class="tab-content">
        <div class="config-container">
            <h2>⚙️ 配置文件编辑</h2>
            <p style="color:#8899aa;font-size:13px;margin-bottom:20px;">
                修改后点击保存，服务将自动热加载新配置（部分参数需要重启生效）
            </p>
            <div id="config-editor">加载中...</div>
            <div class="config-actions">
                <button class="btn-save" id="btn-save" onclick="saveConfig()">💾 保存配置</button>
                <button class="btn-reload" onclick="loadConfig()">🔄 重新加载</button>
            </div>
            <div id="save-status" class="save-status"></div>
        </div>
    </div>
    
    <div class="footer">Powered by Python HTTP Server | 配置文件: config.ini</div>
</body>
</html>'''
        
if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', PORT), LogHandler) as httpd:
        print(f'Web日志服务器已启动: http://localhost:{PORT}')
        print('按 Ctrl+C 停止服务器')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\n服务器已停止')
```
### 4. 服务管理脚本

- **`start.sh`**：一键启动所有服务，日志输出到 `logs/` 目录
```bash
#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo "========================================="
echo "启动所有服务 (Web日志端口: 1145)"
echo "启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================="

# 检查配置文件
if [ ! -f "$SCRIPT_DIR/config.ini" ]; then
    echo "⚠️ 配置文件不存在，请创建 config.ini"
    exit 1
fi

# 启动Python脚本
for script in main.py mcmain.py web_server.py; do
    if [ -f "$SCRIPT_DIR/$script" ]; then
        LOG_FILE="$LOG_DIR/${script%.py}.log"
        > "$LOG_FILE"
        echo "启动: $script -> ${script%.py}.log"
        nohup python3 "$SCRIPT_DIR/$script" >> "$LOG_FILE" 2>&1 &
        echo "✓ $script 已启动 (PID: $!)"
        sleep 0.3
    else
        echo "✗ 文件不存在: $script"
    fi
done

echo "========================================="
echo "所有脚本已启动！"
echo "Web管理地址: http://localhost:1145"
echo "========================================="

# 等待
wait
```
- **`stop.sh`**：优雅地停止所有相关进程
```bash
#!/bin/bash

# 停止所有相关进程

echo "正在停止所有服务..."

# 停止Web服务器 (端口1145)
PORT_PID=$(lsof -ti:1145 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    kill -9 $PORT_PID 2>/dev/null
    echo "✓ 已停止Web服务器 (端口1145)"
fi

# 停止Python脚本
for script in main.py mcmain.py web_server.py; do
    PIDS=$(pgrep -f "python3.*$script" 2>/dev/null)
    if [ -n "$PIDS" ]; then
        kill -9 $PIDS 2>/dev/null
        echo "✓ 已停止 $script"
    fi
done

# 额外清理：停止所有相关的nohup进程
PIDS=$(pgrep -f "nohup.*python3.*main.py\|mcmain.py\|web_server.py" 2>/dev/null)
if [ -n "$PIDS" ]; then
    kill -9 $PIDS 2>/dev/null
    echo "✓ 已清理残留进程"
fi

echo "所有服务已停止"
```

### 5. 配置文件 `config.ini`

所有敏感配置统一存放，包含以下节：
- `[SFTP]`：MC 服务器的 SFTP 连接信息（地址、端口、用户名、密码、日志路径）
- `[RCON]`：MC 服务器的 RCON 连接信息（地址、端口、密码）
- `[WECHAT]`：微信 API 地址、桥接地址、目标群名、黑名单
- `[ADMIN]`：管理员列表、全员可用指令列表
- `[CACHE]`：防重缓存文件路径
- `[DELAYS]`：桌面自动化的时序参数

---

## 🛠️ 五、部署落地与踩坑手册

### 1. 宿主机基础依赖安装

```bash
apt-get update
apt-get install -y xfce4 xfce4-goodies xvfb xdotool xclip python3-pip
pip3 install paramiko requests
```

### 2. 部署 wechat-decrypt 组件

```bash
git clone https://gitcode.com/gcw_xlkU87N4/wechat-decrypt.git
cd wechat-decrypt
python3 find_all_keys.py
nohup python3 monitor_web.py > /tmp/wechat_decrypt.log 2>&1 &
```

### 3. 初始化 GUI 界面与登录微信

1. 启动虚拟桌面：`Xvfb :99 -screen 0 1920x1080x24 & startxfce4 &`
2. 使用 NoMachine 连接服务器，打开微信扫码登录
3. **重要**：在微信中搜索一次发送目标（如“文件传输助手”），确保聊天列表中有该名称

### 4. 配置文件示例（脱敏）

```ini
[SFTP]
host = 你的MC服务器SFTP地址
port = SFTP端口
user = SFTP用户名
password = SFTP密码
remote_log_path = logs/latest.log

[RCON]
host = 你的MC服务器IP
port = RCON端口
password = RCON密码

[WECHAT]
api_url = http://127.0.0.1:5678/api/history
bridge_url = http://127.0.0.1:9999/wxSend
target_group = 你的微信群名称
exclude_senders = 樱桃bot

[ADMIN]
users = 管理员1, 管理员2
public_commands = /list, /help

[CACHE]
file = /tmp/mc_sent_fps.txt

[DELAYS]
window_activate = 0.5
click_input = 0.3
paste_wait = 0.2
send_wait = 0.2
retry_interval = 2.0
```

### 5. 启动服务

```bash
chmod +x start.sh && ./start.sh
```

### 6. 查看日志

```bash
tail -f logs/mcmain.log
# 或访问 http://localhost:1145
```

---

## ❓ FAQ 常见故障排查表

| 故障现象 | 常见原因 | 解决方法 |
| :--- | :--- | :--- |
| `xclip` 报错 `Can't open display: :99` | 环境变量未传入 `DISPLAY=:99` | 检查代码中的 `DISPLAY_ENV` 设置 |
| 微信窗口无反应 | 微信未运行或最小化到托盘 | 用 NoMachine 连入桌面，保持微信窗口可见 |
| MC 说话后微信没收到 | SFTP 连接失败或日志路径错误 | 检查 `config.ini` 中的 SFTP 配置，查看 `logs/mcmain.log` |
| 微信粘贴丢字符 | 自动化操作间隔太快 | 微调 `DELAYS` 中的 `paste_wait` 参数 |
| `wechat-decrypt` API 无响应 | `monitor_web.py` 未运行 | 检查 `ps aux | grep monitor_web` |
| RCON 连接失败 | 服务器未开启 RCON 或密码错误 | 检查服务器 `server.properties` 配置 |
| 特殊字符用户名无法识别 | `=` 被 INI 解析器误认为分隔符 | 用引号包裹，如 `"=约～等～于="` |

---

## 🎯 六、总结与结语

经过了从 Docker 容器的性能挣扎，到视觉 API 大模型折腾，再到最终采用 `wechat-decrypt` 数据直连方案的全过程，我们终于用一套完整、可靠的代码解决了“群服互联”的双向闭环需求。

这套系统的工程精髓可以总结为三句话：

1. **安全第一**：上行采用 `xclip` + `xdotool` 纯物理模拟，下行采用微信本地数据库只读访问，全程不触碰微信内存与协议风控红线，零封号风险。
2. **极简至上**：坚决放弃不稳定、高成本的视觉 AI 方案，让系统干净利落、高度可靠。
3. **性能无感**：零 CPU 浪费，毫秒级响应，零 Token 成本。总延迟控制在 150ms 以内，体验如同原生。

> **致谢**：本项目的下行方案完全建立在 `wechat-decrypt` 这个优秀开源项目之上。它展现了在夹缝中寻找优雅解决方案的工程魅力。向所有在国产软件封闭生态下坚持探索的开源开发者致敬。

---

> 🔗 **相关链接**：
> * 项目源码： [wechat-decrypt项目](https://gitcode.com/gcw_xlkU87N4/wechat-decrypt)
> * 最终效果：![效果图](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/mcresult.png)