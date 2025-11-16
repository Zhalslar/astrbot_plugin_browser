import asyncio
import json
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import astrbot.core.message.components as Comp
from astrbot import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core import AstrBotConfig
from astrbot.core.config.astrbot_config import AstrBotConfig  # noqa: F811
from astrbot.core.platform import AstrMessageEvent
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core.star.filter.permission import PermissionType

from .browser import BrowserManager


@register("astrbot_plugin_browser", "Zhalslar", "...", "...")
class BrowserPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.viewport_width: int = config.get("viewport_width", 1920)  # 视口宽度
        self.viewport_height: int = config.get("viewport_height", 1440)  # 视口高度
        self.zoom_factor: float = config.get("zoom_factor", 1.5)  # 打开新页面时的默认缩放比例
        self.full_page_zoom_factor: float = config.get("full_page_zoom_factor", 0)  # 查看页时的默认缩放比例, 0表示不改变原来的缩放比
        self.default_search_engine: str = config.get("default_search_engine", "必应搜索")  # 默认使用的搜索引擎
        self.max_pages: int = config.get("max_pages", 6) # 允许的最大标签页数量
        self.delete_file_cookies: bool = config.get("delete_file_cookies", False) # 是否删除文件中的cookies
        self.banned_wprds: list[str] = config.get("banned_words", [])  # 禁止的关键词列表

        # 获取astrbot的配置
        astrbot_config = config.get("astrbot_config", {})
        self.password = astrbot_config.get("password", "astrbot")
        dashboard_config = AstrBotConfig()["dashboard"]
        self.dashboard_username = dashboard_config.get("username", "astrbot")
        self.dashboard_host = dashboard_config.get("host","0.0.0.0")
        self.dashboard_port = dashboard_config.get("port", 6185)
        self.astrbot_password = astrbot_config.get("password", "astrbot")

        # 获取napcat的配置
        napcat_config = config.get("napcat_config", {})
        self.napcat_port: str = napcat_config.get("napcat_port", "6099")
        self.napcat_token: str = napcat_config.get("token", "napcat")
        self.napcat_dark_themes: bool = napcat_config.get("dark_themes", False)  # 是否使用深色主题

        # 文件路径
        self.plugin_data_dir = StarTools.get_data_dir("astrbot_plugin_qqadmin")
        self.browser_cookies_file = self.plugin_data_dir / "browser_cookies.json"
        self.favorite_file = self.plugin_data_dir / "favorite.json"

        # 初始化浏览器
        self.browser = BrowserManager(self.browser_cookies_file)
        asyncio.create_task(self.browser.initialize())

        # 初始化 favorite
        self.favorite: dict[str, str] = {}
        self._load_favorite()

    def _load_favorite(self):
        """加载收藏文件，如果不存在则创建空文件"""
        if self.favorite_file.exists():
            try:
                with open(self.favorite_file, encoding="utf-8") as file:
                    self.favorite = json.load(file)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 文件格式错误: {e}")
            except Exception as e:
                logger.error(f"读取 JSON 文件时发生错误: {e}")
        else:
            with open(self.favorite_file, "w", encoding="utf-8") as file:
                json.dump({}, file, ensure_ascii=False, indent=2)

    @filter.command("浏览器帮助")
    async def help(self, event: AstrMessageEvent):
        """浏览器帮助"""
        help_text = (
            "【浏览器插件帮助】：\n\n"
            "/搜索 <关键词> -搜索关键词\n\n"
            "/访问 <链接> -访问指定链接\n\n"
            "/点击 <x> <y> -模拟点击指定坐标\n\n"
            "/输入 <文本> <回车> -模拟输入文本\n\n"
            "/滑动 <起始X> <起始Y> <结束X> <结束Y> -模拟滑动\n\n"
            "/缩放 <缩放比例> -缩放网页\n\n"
            "/滚动 <方向> <距离> -滚动网页\n\n"
            "/当前页面 <缩放比例> -查看当前标签页的内容\n\n"
            "/整页 <缩放比例> -查看当前标签页的整页内容\n\n"
            "/上一页 -跳转上一页\n\n"
            "/下一页 -跳转下一页\n\n"
            "/标签页列表 -查看当前标签页列表\n\n"
            "/标签页 <序号> -切换到指定的标签页\n\n"
            "/关闭标签页 <序号> -关闭指定的标签页\n\n"
            "/关闭浏览器 -关闭浏览器\n\n"
            "/收藏夹 -查看收藏夹列表\n\n"
            "/收藏 <名称> <链接> -添加收藏\n\n"
            "/取消收藏 <名称> -取消收藏\n\n"
            "/清空收藏夹 -清空收藏夹\n\n"
            "/添加cookie <cookie> -添加cookie(施工中暂不可用...)\n\n"
            "/清空cookie -清空cookie\n\n"
            "/浏览器设置 <宽度> <高度> <缩放比> -设置浏览器参数\n\n"
            "/astrbot面板 -打开astrbot面板\n\n"
            "/napcat面板 -打开napcat面板\n\n"
            "/浏览器帮助 -查看帮助\n\n"
            "【可用的搜索触发词】：\n\n"
            + "、".join(f"{k}" for k in self.favorite)
        )
        url = await self.text_to_image(help_text)
        yield event.image_result(url)



    @filter.event_message_type(filter.EventMessageType.ALL)
    async def search(self, event: AstrMessageEvent):
        """搜索关键词，如/搜索 关键词"""
        message_str = event.message_str
        if not message_str:
            return
        args = message_str.strip().split(" ")
        # 解析搜索引擎
        selected_engine = ""
        if args[0] == "搜索":
            selected_engine = self.default_search_engine
        elif args[0] in self.favorite.keys():
            selected_engine = args[0]
        else:
            return

        # 解析搜索关键词
        keyword = " ".join(args[1:]) if len(args) > 1 else ""

        # 屏蔽违禁词
        if any(banned_word in keyword for banned_word in self.banned_wprds):
            yield event.plain_result("搜索关键词包含禁词")
            return

        cilent_message_id = None
        group_id = event.get_group_id()


        bot_message = "正在搜索..."
        if event.get_platform_name() == "aiocqhttp":
            assert isinstance(event, AiocqhttpMessageEvent)
            client = event.bot
            cilent_message_id = (await client.send_msg(group_id=int(group_id), message=bot_message)).get("message_id")
        else:
            yield event.plain_result(bot_message)

        # 拼接URL
        url = self.format_url(selected_engine, keyword)

        # 搜索
        result = await self.browser.search(
            group_id=group_id,
            url=url,
            zoom_factor=self.zoom_factor,
            max_pages=self.max_pages
        )
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain)  # type: ignore

        if cilent_message_id and event.get_platform_name() == "aiocqhttp":
            await client.delete_msg(message_id=cilent_message_id)


    @filter.command("访问")
    async def visit(self, event: AstrMessageEvent, url:str|None=None):
        """访问指定链接，如/访问 链接"""
        if not url:
            yield event.plain_result("未输入链接")
            return
        if any(banned_word in url for banned_word in self.banned_wprds):
            yield event.plain_result("访问链接包含禁词")
            return
        group_id = event.get_group_id()
        yield event.plain_result("访问中...")
        result = await self.browser.search(
            group_id=group_id,
            url=url,
            zoom_factor=self.zoom_factor,
            max_pages=self.max_pages,
        )
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain) # type: ignore


    @filter.command("点击")
    async def click(self, event: AstrMessageEvent, input_x:int=0, input_y:int=0):
        """模拟点击指定坐标，如/点击 200 300"""
        group_id = event.get_group_id()
        coords = [input_x, input_y]
        result = await self.browser.click_coord(group_id=group_id, coords=coords)
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain) # type: ignore


    @filter.command("输入")
    async def text_input(self, event: AstrMessageEvent):
        """模拟输入文本，如/输入 文本 回车"""
        group_id = event.get_group_id()
        input = event.message_str.removeprefix("输入").strip()
        if any(banned_word in input for banned_word in self.banned_wprds):
            yield event.plain_result("搜索关键词包含禁词")
            return
        if not input:
            yield event.plain_result("未指定输入内容")
            return
        result = await self.browser.text_input(group_id=group_id, text=input)
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain) # type: ignore


    @filter.command("滑动")
    async def swipe(self, event: AstrMessageEvent, start_x:int|None=None, start_y:int|None=None, end_x:int|None=None, end_y:int|None=None):
        """模拟滑动，如/滑动 100 200 300 400"""
        group_id = event.get_group_id()
        coords = [start_x, start_y, end_x, end_y]
        if len(coords) != 4:
            yield event.plain_result("应提供4个整数：起始X，起始Y，结束X，结束Y")
            return
        result = await self.browser.swipe(group_id=group_id, coords=coords)
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain) # type: ignore


    @filter.command("缩放")
    async def zoom_to_scale(self, event: AstrMessageEvent, scale_factor:float=1.5):
        """缩放网页，如/缩放 1.5"""
        group_id = event.get_group_id()
        result = await self.browser.zoom_to_scale(
            group_id=group_id, scale_factor=scale_factor
        )
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain) # type: ignore


    @filter.command("滚动")
    async def scroll(self, event: AstrMessageEvent) :
        """滚动网页，如/滚动 上 100"""
        group_id = event.get_group_id()
        args = event.message_str.strip().split()
        distance = self.viewport_height - 100
        direction = "下"
        for arg in args:
            if arg.isdigit():
                distance = int(arg)
            elif arg in ["上", "下", "左", "右"]:
                direction = arg
            else:
                pass
        result = await self.browser.scroll_by(
            group_id=group_id, distance=distance, direction=direction
        )
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain) # type: ignore


    @filter.command("当前页面")
    async def view_page(self, event: AstrMessageEvent, zoom_factor:float|None=None):
        """查看当前标签页的内容"""
        group_id = event.get_group_id()
        zoom_factor = zoom_factor or self.zoom_factor
        if screenshot := await self.browser.get_screenshot(
            group_id=group_id,
            zoom_factor=zoom_factor,
        ):
            chain = [Comp.Image.fromBytes(screenshot)]
            yield event.chain_result(chain) # type: ignore


    @filter.command("整页")
    async def view_full_page(self, event: AstrMessageEvent, zoom_factor:float|None=None):
        """查看当前标签页的内容，如/当前页面 1.5"""
        group_id = event.get_group_id()
        zoom_factor = zoom_factor or self.full_page_zoom_factor or self.zoom_factor
        if screenshot := await self.browser.get_screenshot(
            group_id=group_id, full_page=True, zoom_factor=zoom_factor
        ):
            chain = [Comp.Image.fromBytes(screenshot)]
            yield event.chain_result(chain) # type: ignore


    @filter.command("上一页")
    async def go_back(self, event: AstrMessageEvent):
        """跳转上一页"""
        group_id = event.get_group_id()
        result = await self.browser.go_back(group_id=group_id)
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain) # type: ignore


    @filter.command("下一页")
    async def go_forward(self, event: AstrMessageEvent):
        """跳转下一页"""
        group_id = event.get_group_id()
        result = await self.browser.go_forward(group_id=group_id)
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain) # type: ignore


    @filter.command("标签页列表")
    async def get_all_tabs_titles(self, event: AstrMessageEvent):
        """查看当前标签页列表"""
        titles = await self.browser.get_all_tabs_titles()
        titles_str = ("\n".join(f"{i + 1}. {title}" for i, title in enumerate(titles))) or "暂无打开中的标签页"
        yield event.plain_result(titles_str)


    @filter.command("标签页", alias={"切换标签页"})
    async def switch_to_tab(self, event: AstrMessageEvent, index:int=1):
        """切换到指定的标签页，如/标签页 1"""
        group_id = event.get_group_id()
        result = await self.browser.switch_to_tab(group_id=group_id, tab_index=index - 1)
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain) # type: ignore


    @filter.command("关闭标签页")
    async def close_tab(self, event: AstrMessageEvent):
        """关闭指定的标签页，如/关闭标签页 1 2 3"""
        group_id = event.get_group_id()
        message_str = event.get_message_str()
        index_list = [int(num) for num in re.findall(r"\d+", message_str)]
        if not index_list:  # 如果输入为空，则默认操作为关闭最后一个标签页
            result = await self.browser.close_tab(group_id=group_id)
            if result:
                yield event.plain_result(result)
                return
        else:
            try:  # 将输入的索引转换为整数，并按降序排序
                index_list = sorted(index_list, reverse=True)
            except ValueError:
                yield event.plain_result("所有输入必须是整数序号")
                return
            for index in index_list:
                result = await self.browser.close_tab(
                    tab_index=index - 1, group_id=group_id
                )
                if result:
                    yield event.plain_result(result)


    @filter.command("关闭浏览器")
    async def close_browser(self, event: AstrMessageEvent):
        """关闭浏览器"""
        is_closed = await self.browser.close_browser()
        if is_closed:
            yield event.plain_result("浏览器已关闭")
        else:
            yield event.plain_result("没有打开中的浏览器")


    @filter.command("收藏夹", alias={"查看收藏夹"})
    async def favorite_list(self, event: AstrMessageEvent):
        """查看收藏夹列表"""
        if not self.favorite:
            yield event.plain_result("收藏夹列表为空")
            return
        favorite_list_str = "收藏夹列表：\n"
        favorite_list_str += "\n\n".join(
            f"{i + 1}. {k}: {v}" for i, (k, v) in enumerate(self.favorite.items())
        )
        url = await self.text_to_image(favorite_list_str)
        yield event.image_result(url)


    @filter.command("收藏", alias={"添加收藏"})
    async def add_favorite(self, event: AstrMessageEvent, name:str|None=None, url:str|None=None):
        """添加收藏"""
        if not name or not url:
            yield event.plain_result("请输入名称和链接")
            return
        if name in self.favorite:
            yield event.plain_result(f" {name} 已收藏过了")
            return
        self.favorite[name] = url
        with open(self.favorite_file, "w", encoding="utf-8") as file:
            json.dump(self.favorite, file, ensure_ascii=False, indent=4)
        yield event.plain_result(f"已收藏：{name}: {url}")


    @filter.command("取消收藏")
    async def delete_favorite(self, event: AstrMessageEvent, name:str|None=None):
        """取消收藏"""
        if not name:
            yield event.plain_result("请输入名称")
            return
        if name not in self.favorite:
            yield event.plain_result(f"{name} 在收藏夹中不存在")
            return
        del self.favorite[name]
        with open(self.favorite_file, "w", encoding="utf-8") as file:
            json.dump(self.favorite, file, ensure_ascii=False, indent=4)
        yield event.plain_result(f"已取消收藏：{name}")


    @filter.command("清空收藏夹", alias={"清空收藏"})
    async def clear_favorite(self, event: AstrMessageEvent):

        if not self.favorite:
            yield event.plain_result("收藏夹列表为空")
            return
        self.favorite.clear()
        with open(self.favorite_file, "w", encoding="utf-8") as file:
            json.dump(self.favorite, file, ensure_ascii=False, indent=4)
        yield event.plain_result("已清空收藏夹")


    @filter.command("添加cookie")
    async def add_cookies(self, event: AstrMessageEvent, url:str|None=None, cookies_str:str|None=None):
        """添加cookie(施工中暂不可用...)"""
        if not cookies_str:
            yield event.plain_result("未输入cookies")
            return
        if not url:
            yield event.plain_result("未输入url")
            return
        cookies_list = self.parse_cookies(url=url,cookies_str=cookies_str)
        result = await self.browser.add_cookies(cookies=cookies_list)

        group_id = event.get_group_id()
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain)


    @filter.command("清空cookie", alias={"清除cookie"})
    async def clear_cookies(self, event: AstrMessageEvent):
        """清空cookie"""
        group_id = event.get_group_id()
        result = await self.browser.clear_cookies(
            delete_file_cookies=False
        ) # TODO: 这里的delete_file_cookie参数需要根据实际情况设置
        chain = await self.screenshot(group_id, result)
        yield event.chain_result(chain)


    @filter.command("浏览器设置")
    async def set_browser(self, event: AstrMessageEvent, viewport_width:int|None=None, viewport_height:int|None=None, zoom_factor:float|None=None):

        if viewport_width:
            self.viewport_width = viewport_width
        if viewport_height:
            self.viewport_height = viewport_height
        if zoom_factor:
            self.zoom_factor = zoom_factor
        reply = (
            f"浏览器参数已设置：\n"
            f"宽度：{self.viewport_width}\n"
            f"高度：{self.viewport_height}\n"
            f"缩放比：{self.zoom_factor}"
        )
        yield event.plain_result(reply)


    async def screenshot(self, group_id:str, result: str|None=None):

        chain = []
        if result:
            chain.append(Comp.Plain(result))
        if screenshot := await self.browser.get_screenshot(
            group_id=group_id,
            viewport_width=self.viewport_width,
            viewport_height=self.viewport_height,
        ):
            chain.append(Comp.Image.fromBytes(screenshot))
        return chain


    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("astrbot面板", alias={"Astrbot面板"})
    async def open_astrbot_webui(self, event: AstrMessageEvent):
        """打开astrbot面板"""
        group_id = event.get_group_id()
        yield event.plain_result("正在打开astrbot面板...")

        if self.dashboard_host == "0.0.0.0":
            self.dashboard_host = "127.0.0.1"
        dashboard_url = f"http://{self.dashboard_host}:{self.dashboard_port}"

        try:
            await self.browser.search(group_id=group_id, url=dashboard_url)
            await self.browser.text_input(group_id=group_id, text=self.dashboard_username)
            await self.browser.text_input(group_id=group_id, text=self.password)
            chain = await self.screenshot(group_id)
            yield event.chain_result(chain) # type: ignore

        except Exception as e:
            logger.error(f"Astrbot面板打开时出错：{e}")
            yield event.plain_result("Astrbot面板打不开")


    @filter.permission_type(PermissionType.ADMIN)
    @filter.command("napcat面板", alias={"Napcat面板"})
    async def open_napcat_webui(self, event: AstrMessageEvent):
        """打开napcat面板"""
        group_id = event.get_group_id()
        yield event.plain_result("正在打开napcat面板...")

        napcat_url = f"http://{self.dashboard_host}:{self.napcat_port}" # napcat的host应该是和astrbot的host一致的
        try:
            await self.browser.search(group_id=group_id, url=napcat_url)
            await self.browser.text_input(group_id=group_id, text=self.napcat_token)
            await self.browser.click_button(group_id=group_id, button_text="登录")
            if self.napcat_dark_themes:
                await self.browser.click_button(group_id=group_id, button_text="深色主题")

            chain = await self.screenshot(group_id)
            yield event.chain_result(chain) # type: ignore

        except Exception as e:
            logger.error(f"Napcat面板打开时出错：{e}")
            yield event.plain_result("Napcat面板打不开")



    @staticmethod
    def get_current_timestamps():
        """获取当前时间戳（秒和毫秒）"""
        current_time = time.time()  # 获取当前时间戳（秒）
        timestamp_s = int(current_time)  # 秒级时间戳
        timestamp_ms = int(current_time * 1000)  # 毫秒级时间戳
        return timestamp_s, timestamp_ms


    def format_url(self, selected_engine, keyword):
        """格式化URL"""
        if selected_engine in self.favorite:
            url_template = self.favorite[selected_engine]
            timestamp_s, timestamp_ms = self.get_current_timestamps()
            params = {
                "keyword": keyword,
                "timestamp_s": timestamp_s,
                "timestamp_ms": timestamp_ms
            }
            try:
                formatted_url = url_template.format(**params)
            except KeyError as e:
                # 如果模板中有未定义的占位符，则移除相应的参数并重试
                missing_key = e.args[0]
                del params[missing_key]
                formatted_url = url_template.format(**params)

            return formatted_url
        else:
            return ""

    @staticmethod
    def parse_cookies(url, cookies_str):
        """将cookies字符串解析为Playwright所需的列表格式"""
        parsed_url = urlparse(url)
        domain = f".{parsed_url.netloc}"
        # 解析cookies字符串
        cookies_list = []
        for cookie in cookies_str.split("; "):
            parts = cookie.split("=", 1)
            if len(parts) < 2:
                continue
            name = parts[0].strip()
            value = parts[1].strip()
            # 处理cookie的域名
            cookie_dict = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/"
            }
            # 处理其他属性
            attributes = cookie.split("; ")
            for attr in attributes[1:]:
                key_value = attr.strip().split("=", 1)
                if len(key_value) == 2:
                    key, val = key_value
                    key = key.lower()
                    val = val.strip()
                    if key == "expires":
                        try:
                            cookie_dict["expires"] = int(datetime.strptime(val, "%a, %d-%b-%Y %H:%M:%S GMT").timestamp())  # noqa: F821
                        except ValueError:
                            pass
                    elif key == "samesite":
                        cookie_dict["sameSite"] = val.capitalize()
                else:
                    key = key_value[0].lower()
                    if key == "httponly":
                        cookie_dict["httpOnly"] = True
                    elif key == "secure":
                        cookie_dict["secure"] = True

            cookies_list.append(cookie_dict)
        return cookies_list
