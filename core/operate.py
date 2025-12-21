# /astrbot/core/operate.py
import re
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Image, Plain
from astrbot.core.platform import AstrMessageEvent
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .favorite import FavoriteManager
from .supervisor import BrowserSupervisor
from .ticks_overlay import TickOverlay


class BrowserOperator:
    """
    浏览器命令操作层：
    - 解析用户输入
    - 通过 BrowserSupervisor 调用浏览器方法
    - 统一处理截图和消息回传
    """

    def __init__(
        self,
        config: AstrBotConfig,
        fav_mgr: FavoriteManager,
        overlay: TickOverlay,
        supervisor: BrowserSupervisor,
    ):
        self.config = config
        self.fav_mgr = fav_mgr
        self.overlay = overlay
        self.supervisor = supervisor

    # ================= 内部工具 ==================

    def _contains_banned(self, text: str) -> bool:
        return any(word in text for word in self.config["banned_words"])

    def _get_current_timestamps(self):
        now = time.time()
        return int(now), int(now * 1000)

    def _format_url(self, engine_name: str, keyword: str) -> str | None:
        url_template = self.fav_mgr.get(engine_name)
        if not url_template:
            return None
        ts_s, ts_ms = self._get_current_timestamps()
        try:
            return url_template.format(
                keyword=keyword, timestamp_s=ts_s, timestamp_ms=ts_ms
            )
        except KeyError as e:
            logger.warning(f"URL 模板缺少参数: {e}")
            return None

    async def send_screenshot(
        self,
        event: AstrMessageEvent,
        path: str | None = None,
        *,
        full_page: bool = False,
        zoom_factor: float | None = None,
    ):
        """
        统一截图 + 文本回传
        """
        chain = []

        if path:
            chain.append(Plain(path))
        screenshot: str | None = await self.supervisor.call(
            "screenshot", zoom_factor=zoom_factor, full_page=full_page
        )
        if screenshot:
            if self.config["enable_overlay"]:
                overlay_screenshot = self.overlay.overlay_on_background(Path(screenshot))
                chain.append(Image.fromFileSystem(overlay_screenshot))
            else:
                chain.append(Image.fromFileSystem(screenshot))

        if chain:
            await event.send(event.chain_result(chain))

    # ================= 搜索 / 访问 ==================
    async def search(self, event: AstrMessageEvent):
        msg = event.message_str.strip()
        if not msg:
            return

        args = msg.split()
        head = args[0].lower()

        if head == "搜索":
            engine = self.config.get("default_search_engine", "百度")
        elif head in self.fav_mgr.list_names():
            engine = head
        else:
            return

        keyword = " ".join(args[1:])
        if not keyword:
            await event.send(event.plain_result("未指定搜索关键词"))
            return
        if self._contains_banned(keyword):
            await event.send(event.plain_result("搜索关键词包含禁词"))
            return

        url = self._format_url(engine, keyword)
        if not url:
            await event.send(event.plain_result("URL 模板错误"))
            return

        if isinstance(event, AiocqhttpMessageEvent):
            client_msg_id = (
                await event.bot.send_msg(
                    group_id=int(event.get_group_id()), message="正在搜索..."
                )
            ).get("message_id")
        else:
            await event.send(event.plain_result("正在搜索..."))

        logger.info(f"正在访问: {url}")
        result_path = await self.supervisor.call("search", url=url)

        await self.send_screenshot(event, result_path)

        if isinstance(event, AiocqhttpMessageEvent) and client_msg_id:
            await event.bot.delete_msg(message_id=client_msg_id)

    async def visit(self, event: AstrMessageEvent, url: str | None = None):
        if not url:
            await event.send(event.plain_result("未输入链接"))
            return
        if self._contains_banned(url):
            await event.send(event.plain_result("访问链接包含禁词"))
            return
        await event.send(event.plain_result("访问中..."))
        result_path = await self.supervisor.call("search", url=url)
        await self.send_screenshot(event, result_path)

    # ================= 页面交互 ==================
    async def click(self, event: AstrMessageEvent, x: int = 0, y: int = 0):
        result_path = await self.supervisor.call("click_coord", coords=[x, y])
        await self.send_screenshot(event, result_path)

    async def text_input(self, event: AstrMessageEvent):
        text = event.message_str.removeprefix("输入").strip()
        if not text:
            await event.send(event.plain_result("未指定输入内容"))
            return
        if self._contains_banned(text):
            await event.send(event.plain_result("输入内容包含禁词"))
            return
        result_path = await self.supervisor.call("text_input", text=text)
        await self.send_screenshot(event, result_path)

    async def swipe(self, event: AstrMessageEvent, sx=None, sy=None, ex=None, ey=None):
        coords = [sx, sy, ex, ey]
        if any(v is None for v in coords):
            await event.send(
                event.plain_result("应提供 4 个整数：起始X 起始Y 结束X 结束Y")
            )
            return
        result_path = await self.supervisor.call("swipe", coords=coords)
        await self.send_screenshot(event, result_path)

    async def scroll(self, event: AstrMessageEvent):
        args = event.message_str.split()
        direction, distance = "下", 1300
        for arg in args:
            if arg in {"上", "下", "左", "右"}:
                direction = arg
            elif arg.isdigit():
                distance = int(arg)
        result_path = await self.supervisor.call(
            "scroll_by", distance=distance, direction=direction
        )
        await self.send_screenshot(event, result_path)

    async def zoom_to_scale(self, event: AstrMessageEvent, scale: float = 1.5):
        result_path = await self.supervisor.call("zoom_to_scale", scale=scale)
        await self.send_screenshot(event, result_path)

    # ================= 页面浏览 ==================
    async def go_back(self, event: AstrMessageEvent):
        result_path = await self.supervisor.call("go_back")
        await self.send_screenshot(event, result_path)

    async def go_forward(self, event: AstrMessageEvent):
        result_path = await self.supervisor.call("go_forward")
        await self.send_screenshot(event, result_path)

    # ================= 标签页管理 ==================
    async def get_all_tabs_titles(self, event: AstrMessageEvent):
        titles = await self.supervisor.call("get_all_tabs_titles")
        if not titles:
            await event.send(event.plain_result("暂无打开中的标签页"))
            return
        await event.send(
            event.plain_result("\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles)))
        )

    async def switch_to_tab(self, event: AstrMessageEvent, index: int = 1):
        result_path = await self.supervisor.call("switch_tab", index=index - 1)
        await self.send_screenshot(event, result_path)

    async def close_tab(self, event: AstrMessageEvent):
        nums = [int(n) for n in re.findall(r"\d+", event.message_str)]
        if not nums:
            await event.send(event.plain_result("未指定要关闭的标签页"))
            return
        for idx in sorted(nums, reverse=True):
            result_msg = await self.supervisor.call("close_tab", index=idx - 1)
            if result_msg:
                await event.send(event.plain_result(result_msg))

    async def close_browser(self, event: AstrMessageEvent | None = None):
        if not self.supervisor:
            if event:
                await event.send(event.plain_result("未开启浏览器的监控器"))
            return

        if not self.supervisor.browser:
            if event:
                await event.send(event.plain_result("未开启浏览器"))
            return

        try:
            await self.supervisor._stop_browser()
            logger.info("已关闭浏览器")
            if event:
                await event.send(event.plain_result("已关闭浏览器"))
        except Exception as e:
            logger.error(f"关闭浏览器时发生错误：{e}")
            if event:
                await event.send(event.plain_result(f"关闭浏览器时出错: {e}"))

