<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_browser?name=astrbot_plugin_browser&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_browser

_✨ [astrbot](https://github.com/AstrBotDevs/AstrBot) 浏览器对接插件 ✨_  

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)

</div>

## 🤝 介绍

本插件通过操控bot与浏览器交互（搜索、点击、滑动、滚动、缩放、输入、切换标签页、收藏等等），  
运行时，bot在后台打开一个浏览器，每完成一个交互动作，bot返回一张浏览器界面的截图。

## 💿 安装

### 第一步，安装本插件

直接在astrbot的插件市场搜索astrbot_plugin_browser，点击安装，等待完成即可

### 第二步，安装浏览器组件（embedded 模式）

- 打开插件配置面板，选择你要使用的浏览器，默认是firefox
- 在聊天中发送命令 `安装浏览器`，等待浏览器安装完成即可使用

### 可选：接入本地浏览器（local_cdp 模式，请使用chromium内核）

如果你希望插件直接操控本地浏览器窗口，请在配置中设置：

- `browser_mode = local_cdp`
- `cdp_url = http://127.0.0.1:9222`（默认值）
- `browser_type = chromium`

> `local_cdp` 只需要 `cdp_url`，**不需要在插件里配置浏览器可执行文件路径**。
> 插件只负责连接你本机已开启的 CDP 端口；你用什么系统启动浏览器由你自己决定。

`local_cdp` 模式下不需要下载内置浏览器内核；但首次使用前可执行一次 `安装浏览器`，用于安装/检查 playwright Python 运行时。

#### Linux 启动示例(较新版本的Linux需要加上--no-sandbox)

- Chrome

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-cdp
```

- Edge

```bash
microsoft-edge --remote-debugging-port=9222 --user-data-dir=/tmp/edge-cdp
```


### Docker环境依赖问题

Docker因为自身缺陷会出现依赖问题，通过以下命令可正常使用： 

**1、进入astrbot docker环境**  
docker exec -it 【container-id】 bash  
**2、安装缺失的依赖**  
playwright install-deps  
**3、重新发送"安装浏览器"命令，即可安装成功**

## 🤝 配置

- 插件配置，请前往插件的配置面板进行配置

- 网站收藏夹，收藏夹文件位置如下，可打开进行自定义

  ![tmp692A](https://github.com/user-attachments/assets/d809f0f4-308f-4ad2-a555-e79ac72f3154)

## 🕹️ 使用说明

![tmp9666](https://github.com/user-attachments/assets/8d5f44de-1683-47b6-aa2b-4ea4665ed4d8)

### 对话交互命令

- `/对话 你好`
- `/继续对话 请把上一条答案再简化`

对话命令会：
1. 在当前标签页定位输入框
2. 输入文本并发送（优先点发送按钮，否则按回车）
3. 返回当前页面截图

相关配置项：

- `chat_input_selector`：输入框 CSS 选择器（支持逗号分隔多个选择器）
- `chat_send_selector`：发送按钮 CSS 选择器（留空则回车发送）
- `chat_wait_ms`：发送后等待时间（毫秒）

## 🤝 TODO  

- [x] 支持收藏功能：新增指令 `/收藏 <内容>` 和 `/取消收藏 <内容>`
- [x] 提供收藏夹管理：新增指令 `/收藏夹` 查看所有收藏
- [ ] Cookies 高级管理
- [x] 屏蔽违禁词
- [x] 新增帮助文档：提供指令使用指南，支持 `/浏览器帮助` 查询
- [x] 降低性能消耗：优化代码逻辑，减少资源占用


## 👥 贡献指南

- 🌟 Star 这个项目！（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码

## 📌 注意事项

- 本插件采用的是内置firefox浏览器，可播放视频，播放时电脑会有声音传出。
- 想第一时间得到反馈的可以来作者的插件反馈群（QQ群）：460973561（不点star不给进）
