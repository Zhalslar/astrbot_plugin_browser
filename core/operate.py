import re
import time

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Image, Plain
from astrbot.core.platform import AstrMessageEvent
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)

from .browser import BrowserManager
from .favorite import FavoriteManager


class BrowserOperator:
    """
    浏览器命令操作层：
    - 负责解析用户输入
    - 调用 BrowserManager
    - 统一处理截图与消息回传
    """

    def __init__(
        self,
        config: AstrBotConfig,
        browser: BrowserManager,
        fav_mgr: FavoriteManager,
    ):
        self.config = config
        self.browser = browser
        self.fav_mgr = fav_mgr

        self.zoom_factor: float = config["zoom_factor"]
        self.banned_words: list[str] = config["banned_words"]

    # ================= 内部工具 ==================

    def _contains_banned(self, text: str) -> bool:
        return any(word in text for word in self.banned_words)

    def _get_current_timestamps(self):
        """获取当前时间戳（秒和毫秒）"""
        current_time = time.time()  # 获取当前时间戳（秒）
        timestamp_s = int(current_time)  # 秒级时间戳
        timestamp_ms = int(current_time * 1000)  # 毫秒级时间戳
        return timestamp_s, timestamp_ms

    def _format_url(self, engine_name: str, keyword: str) -> str:
        """
        根据收藏的 URL 模板格式化搜索地址
        """
        url_template = self.fav_mgr.get(engine_name)
        if not url_template:
            return ""

        timestamp_s, timestamp_ms = self._get_current_timestamps()
        params = {
            "keyword": keyword,
            "timestamp_s": timestamp_s,
            "timestamp_ms": timestamp_ms,
        }

        try:
            return url_template.format(**params)
        except KeyError as e:
            # 缺参数就直接失败，比“悄悄删参数”更安全
            logger.warning(f"URL 模板缺少参数: {e}")
            return ""

    async def _send_screenshot(
        self,
        event: AstrMessageEvent,
        result: str | None = None,
        *,
        full_page: bool = False,
        zoom_factor: float | None = None,
    ):
        """
        统一截图 + 文本回传
        """
        chain = []

        if result:
            chain.append(Plain(result))

        screenshot = await self.browser.get_screenshot(
            full_page=full_page,
            zoom_factor=zoom_factor,
            viewport_width=self.config["viewport_width"],
            viewport_height=self.config["viewport_height"],
        )

        if screenshot:
            chain.append(Image.fromBytes(screenshot))

        if chain:
            await event.send(event.chain_result(chain))

    # ================= 搜索 / 访问 ==================

    async def search(self, event: AstrMessageEvent):
        """搜索关键词，如：搜索 关键词 / 百度 关键词"""
        message = event.message_str.strip()
        if not message:
            return

        args = message.split()
        head = args[0]

        if head == "搜索":
            engine = self.config["default_search_engine"]
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

        client_msg_id = None
        if isinstance(event, AiocqhttpMessageEvent):
            client_msg_id = (
                await event.bot.send_msg(
                    group_id=int(event.get_group_id()),
                    message="正在搜索...",
                )
            ).get("message_id")
        else:
            await event.send(event.plain_result("正在搜索..."))

        result = await self.browser.search(
            url=url,
            zoom_factor=self.zoom_factor,
            max_pages=self.config["max_pages"],
        )

        await self._send_screenshot(event, result)

        if client_msg_id and isinstance(event, AiocqhttpMessageEvent):
            await event.bot.delete_msg(message_id=client_msg_id)

    async def visit(self, event: AstrMessageEvent, url: str | None = None):
        """访问指定链接"""
        if not url:
            await event.send(event.plain_result("未输入链接"))
            return

        if self._contains_banned(url):
            await event.send(event.plain_result("访问链接包含禁词"))
            return

        await event.send(event.plain_result("访问中..."))

        result = await self.browser.search(
            url=url,
            zoom_factor=self.zoom_factor,
            max_pages=self.config["max_pages"],
        )

        await self._send_screenshot(event, result)

    # ================= 页面交互 ==================

    async def click(self, event: AstrMessageEvent, x: int = 0, y: int = 0):
        """点击指定坐标"""
        result = await self.browser.click_coord([x, y])
        await self._send_screenshot(event, result)

    async def text_input(self, event: AstrMessageEvent):
        """输入文本，如：输入 内容"""
        text = event.message_str.removeprefix("输入").strip()
        if not text:
            await event.send(event.plain_result("未指定输入内容"))
            return

        if self._contains_banned(text):
            await event.send(event.plain_result("输入内容包含禁词"))
            return

        result = await self.browser.text_input(text=text)
        await self._send_screenshot(event, result)

    async def swipe(
        self,
        event: AstrMessageEvent,
        sx: int | None = None,
        sy: int | None = None,
        ex: int | None = None,
        ey: int | None = None,
    ):
        """滑动页面，如：滑动 100 200 300 400"""
        coords = [sx, sy, ex, ey]
        if any(v is None for v in coords):
            await event.send(
                event.plain_result("应提供 4 个整数：起始X 起始Y 结束X 结束Y")
            )
            return

        result = await self.browser.swipe(coords)  # type: ignore[arg-type]
        await self._send_screenshot(event, result)

    async def scroll(self, event: AstrMessageEvent):
        """滚动页面，如：滚动 下 300"""
        args = event.message_str.split()

        direction = "下"
        distance = self.config["viewport_height"] - 100

        for arg in args:
            if arg in {"上", "下", "左", "右"}:
                direction = arg
            elif arg.isdigit():
                distance = int(arg)

        result = await self.browser.scroll_by(distance, direction)
        await self._send_screenshot(event, result)

    async def zoom_to_scale(self, event: AstrMessageEvent, scale: float = 1.5):
        """缩放页面"""
        result = await self.browser.zoom_to_scale(scale)
        await self._send_screenshot(event, result)

    # ================= 页面浏览 ==================

    async def view_page(self, event: AstrMessageEvent, zoom: float | None = None):
        """查看当前页面"""
        await self._send_screenshot(
            event,
            zoom_factor=zoom or self.zoom_factor,
        )

    async def view_full_page(self, event: AstrMessageEvent, zoom: float | None = None):
        """查看完整页面"""
        await self._send_screenshot(
            event,
            full_page=True,
            zoom_factor=zoom
            or self.config.get("full_page_zoom_factor")
            or self.zoom_factor,
        )

    async def go_back(self, event: AstrMessageEvent):
        """返回上一页"""
        result = await self.browser.go_back()
        await self._send_screenshot(event, result)

    async def go_forward(self, event: AstrMessageEvent):
        """前进下一页"""
        result = await self.browser.go_forward()
        await self._send_screenshot(event, result)

    # ================= 标签页管理 ==================

    async def get_all_tabs_titles(self, event: AstrMessageEvent):
        """列出所有标签页"""
        titles = await self.browser.get_all_tabs_titles()
        if not titles:
            await event.send(event.plain_result("暂无打开中的标签页"))
            return

        text = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
        await event.send(event.plain_result(text))

    async def switch_to_tab(self, event: AstrMessageEvent, index: int = 1):
        """切换标签页，如：标签页 1"""
        result = await self.browser.switch_tab(index - 1)
        await self._send_screenshot(event, result)

    async def close_tab(self, event: AstrMessageEvent):
        """关闭指定标签页，如：关闭标签页 1 2"""
        nums = [int(n) for n in re.findall(r"\d+", event.message_str)]
        if not nums:
            await event.send(event.plain_result("未指定要关闭的标签页"))
            return

        for idx in sorted(nums, reverse=True):
            result = await self.browser.close_tab(idx - 1)
            if result:
                await event.send(event.plain_result(result))
