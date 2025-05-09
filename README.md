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

### 第二步，安装浏览器组件

从终端进入astrbot的虚拟环境，安装firefox。

#### ------------Windows的示例操作------------

```bash
# 进入astrbot的根目录
 cd "你的astrbot的安装路径"  

# 激活虚拟环境
venv\Scripts\activate

# 安装firefox
playwright install firefox

# 启动astrbot（当然你也可以通过astrbot面板重启bot）
python main.py
```

![tmpDD00](https://github.com/user-attachments/assets/72bf743c-792a-48ed-8848-58ff0cfe82cf)

#### ------------Linux的示例操作------------

- 进入astrbot的根目录

```bash
# 进入astrbot的根目录
 cd "你的astrbot的安装路径"  

# 激活虚拟环境
source venv/bin/activate

# 安装firefox
playwright install firefox

# 启动astrbot（当然你也可以通过astrbot面板重启bot）
python main.py
```

![tmp89D8](https://github.com/user-attachments/assets/1461c5f4-a918-4930-8ca7-b3a4701bf74c)

#### ------------Docker的示例操作------------

```bash
# 打开bash来安装
sudo docker exec -it astrbot /bin/bash
pip install playwright
playwright install-deps
playwright install firefox
# 装完用exit命令退出
```

## 🤝 配置

- 插件配置，请前往插件的配置面板进行配置
![tmp4FC4](https://github.com/user-attachments/assets/913a1c41-4be6-4b48-b4e8-5f16bc452a1c)

- 网站收藏夹，收藏夹文件位置如下，可打开进行自定义

  ![tmp692A](https://github.com/user-attachments/assets/d809f0f4-308f-4ad2-a555-e79ac72f3154)

## 🕹️ 使用说明

![tmp9666](https://github.com/user-attachments/assets/8d5f44de-1683-47b6-aa2b-4ea4665ed4d8)

## 🤝 TODO  

- [x] 支持收藏功能：新增指令 `/收藏 <内容>` 和 `/取消收藏 <内容>`
- [x] 提供收藏夹管理：新增指令 `/收藏夹` 查看所有收藏
- [ ] 添加 Cookies 管理：支持 `/添加cookies <内容>` 和 `/清除cookies`
- [x] 屏蔽违禁词
- [x] 新增帮助文档：提供指令使用指南，支持 `/浏览器帮助` 查询
- [ ] 降低性能消耗：优化代码逻辑，减少资源占用
- [ ] 提供刷新机制：新增指令 `/刷新` 更新数据状态

## 👥 贡献指南

- 🌟 Star 这个项目！（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码

## 📌 注意事项

- 本插件采用的是内置firefox浏览器，可播放视频，播放时电脑会有声音传出。
- 想第一时间得到反馈的可以来作者的插件反馈群（QQ群）：460973561（不点star不给进）
