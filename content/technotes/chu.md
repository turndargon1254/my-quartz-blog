---
title: "CHUNITHM使用ZeroTier进行店内联机配置教程"
tags: [知识图谱, 中二节奏, 技术]
draft: false
---



> **PS**：原教程创作于 SDHD 2.20 时代，现已针对当前版本重新优化。  
> 祝各位顺顺利利！远程对战快乐！如遇问题请多检查配置，不喜勿喷~

---

## ⚠️ 核心注意事项与前置准备（必读）

* **同版本联机原则**：联机各方**必须保持游戏版本一致**（本教程以 **SDHD 2.47** 为例）。建议直接使用同一个本体进行分享；若 opt 文件不齐或版本有差异，可能导致从机选曲后基准机无法读取等问题。
* **网络限制**：原则上**同一个虚拟网络内只能存在一台基准机**！在不想联机玩时，请务必**退出 ZeroTier 或改回从机/单机状态**（否则可能会卡验证无法进游戏）。
* **组别与机台分配（强烈建议提前配置）**：
  * 在开始以下步骤前，建议先进入游戏 **TEST 模式**（修改灵敏度处，按下 `Test` 键，选择第 3 个选项）。
  * 将所有设备的**店内设置分配为同一个组**（例如：A组 4 人）。
  * 明确设置好谁是 **1P（基准机）**，谁是 **2P、3P、4P（从机）**。
  * **提前改好可大幅避免后续各种繁琐报错！**

| 设备角色 | 说明 |
| :--- | :--- |
| **1P（基准机）** | 一台主电脑 <br> ![基准机设置](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/jizhunji.png) |
| **2P / 3P / 4P（从机）** | 其他联机电脑 <br> ![从机设置](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/congji.png) |

---

## 🛠️ 联机网络与文件配置步骤

### 第一步：安装 ZeroTier 客户端
所有需要参与联机的设备（1P、2P、3P、4P）均需下载并安装客户端。
* **下载链接**：[ZeroTier_ne.msi 下载](https://download.zerotier.com/dist/ZeroTier%20One.msi)
* **说明**：保持默认设置安装即可。安装完毕后打开软件，暂时先不管它。

---

### 第二步：注册并登陆 ZeroTier 账号
1. 打开 ZeroTier 虚拟局域网官网：[https://my.zerotier.com/network/](https://my.zerotier.com/network/)
2. 注册账号（可以使用 QQ 邮箱注册，看不懂英文可借助网页翻译）。
3. **建议由 1P（基准机玩家）统一进行服务器管理。**
4. 进入网页后若提示选择 `Central` 或 `Legacy`，随手点一个，随后重新打开页面，即可进入控制台。

---

### 第三步：创建私人虚拟局域网
1. 点击创建属于你们的**私人虚拟局域网**。  
   ![创建虚拟网](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/create.png)
   > **建议 4 人为一组**加入服务器，避免多玩家导致的冲突。
2. **请牢记生成的“服务器序列 ID”（Network ID）**，后续所有设备加入时都需要输入此 ID。  
   ![管理员后台界面](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/administration.png)
3. 进入第二个目录 **Advanced**，按照截图方式自定义 IP 地址，最后点击 **Submit** 保存。  
   ![自定义 IP 教程](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/advanced.png)

---

### 第四步：固定 IP 地址分配
往下滑动页面，按照截图填写静态 IP：  
![填写静态 IP](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/ipv4.png)
* **尾数范围**：只能设置为 **0 ~ 24** 之间的数值。
* 此设置相当于把各台电脑的局域网 IP 分配固定死。

---

### 第五步：所有设备加入虚拟局域网
完成网络组建后，需要将所有联机电脑接入此网络：
1. 打开 Windows 右下角任务栏托盘，找到 **ZeroTier 黄色图标**。  
   ![ZeroTier托盘图标](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/zerotier.png)
2. 右键图标，点击 **Join New Network**。
3. 输入刚才记下的 **服务器 ID**（乱码串），点击 **Join**。  
   ![加入网络](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/join.png)
4. **注意**：所有联机设备（1P~4P）均需完成此步骤。

---

### 第六步：管理员页面授权设备
回到 ZeroTier 管理员后台页面：
1. 切换到第三个目录 **Members**。
2. 此时页面会列出刚才加入的几台用户设备。
3. 参照截图依次对每个设备勾选授权并绑定 IP。  
   ![分配绑定成员 IP](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/congjifenpei.png)

---

### 第七步：确认本地 IP 与准备 segatools
1. 各设备（1P、2P、3P 等）打开 Windows **任务管理器**。
2. 切换到 **“性能” -> “详细信息”** 页，找到名为 **以太网 (ZeroTier Virtual Port)** 的网卡。  
   ![网卡 IP 查看](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/ip.png)
3. 检查各设备的 IPv4 地址是否与管理员页面中设置的一致。
4. 确认无误后，打开游戏目录下的 `bin` 文件夹，找到并准备编辑 **`segatools.ini`** 文件。

---

### 第八步：修改 `segatools.ini` 配置文件

打开 `segatools.ini` 进行以下两处改动：

#### 1. 修改 `[netenv]` 节点下的 IP 尾数
在 `[netenv]` 下方输入/修改：
```ini
addrsuffix=14
```
> **填法说明**：若分配给该设备的 IP 为 `192.168.139.14`，则此处填写 **`14`**（即 IP 最后一段尾数）。每台设备根据自己的真实 IPv4 尾数如实填写！  
> ![netenv 修改截图](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/netenv.png)

#### 2. 修改 `[keychip]` 节点下的 子网网段
在 `[netenv]` / `[keychip]` 相关项中填写：
```ini
subnet=192.168.139.0
```
> **填法说明**：直接照此填入即可。  
> ![keychip 修改截图](https://raw.gitcode.com/turndargon1254/sdfzmc/raw/main/img/keychip.png)

---

## 💡 启动流程与故障排查

### 启动顺序
1. **建议由 1P（基准机）首先启动游戏**。
2. 1P 正常进入后，其他从机（2P、3P、4P）再依次启动游戏。

### 报错处理指南
* **卡自检 / 红框报错**：若从机卡自检进不去或弹红框，先进入游戏 **TEST 模式**，等待片刻后再退出 TEST 进行二次自检。
* **再次检查 IP**：如果依然无法进入，请重新核对 `segatools.ini` 中的 `addrsuffix` 尾数以及 ZeroTier 后台的 IP 绑定是否有误。
* **为什么只建议 4 人一组（1 基准机 + 3 从机）？**
  * 如果人数过高，无法实时把控大家的游戏启动状态。
  * **一旦有人忘记改回“从机”状态并以“基准机”身份启动游戏，全房网络将直接崩溃！**
