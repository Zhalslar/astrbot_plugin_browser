
import os
from pathlib import Path

from astrbot.api.event import filter
from astrbot.api.star import Context, Star, StarTools
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.platform import AstrMessageEvent

from .core.cookie import CookieManager
from .core.favorite import FavoriteManager
from .core.utils import HELP_TEXT, check_browser_installed, install_browser


class BrowserPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_dir = StarTools.get_data_dir("astrbot_plugin_browser")

        # 轻量组件，永远安全
        self.cookie = CookieManager(self.config, self.data_dir)
        FAV_FILE = Path(__file__).parent / "resource" / "favorite.json"
        self.fav_mgr = FavoriteManager(self.config, FAV_FILE)

        # 浏览器子系统延迟初始化
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(self.data_dir / "browsers")
        self.browser = None
        self.operator = None
        self._browser_ready = False

    # ================= 生命周期 ===================

    async def initialize(self):
        """插件加载时触发"""
        pass
    async def terminate(self):
        """插件卸载时触发"""
        if self.browser:
            await self.browser.terminate()

    # ================= 浏览器依赖 ===================

    @filter.command("安装浏览器")
    async def install_browser(self, event: AstrMessageEvent):
        """安装 Playwright 浏览器依赖"""
        yield event.plain_result("开始安装浏览器组件…")
        ok = await install_browser(self.data_dir)
        yield event.plain_result(
            "浏览器组件安装完成" if ok else "浏览器安装失败，请检查日志"
        )

    async def _ensure_browser_ready(self, event: AstrMessageEvent) -> bool:
        """确保浏览器已初始化"""
        if self._browser_ready:
            return True

        if not await check_browser_installed():
            await event.send(event.plain_result("浏览器未安装，请执行命令：安装浏览器"))
            return False
        # 真正初始化
        from .core.browser import BrowserManager
        from .core.operate import BrowserOperator

        self.browser = BrowserManager(self.config, self.cookie)
        await self.browser.initialize()
        self.operator = BrowserOperator(self.config, self.browser, self.fav_mgr)
        self._browser_ready = True
        return True

    # ================= 浏览器命令 ===================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def search(self, event: AstrMessageEvent):
        """搜索关键词，如/搜索 关键词"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.search(event)  # type: ignore

    @filter.command("访问")
    async def visit(self, event: AstrMessageEvent, url: str | None = None):
        """访问指定链接，如/访问 链接"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.visit(event, url)  # type: ignore

    @filter.command("点击")
    async def click(self, event: AstrMessageEvent, input_x: int = 0, input_y: int = 0):
        """模拟点击指定坐标，如/点击 200 300"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.click(event, input_x, input_y)  # type: ignore

    @filter.command("输入")
    async def text_input(self, event: AstrMessageEvent):
        """模拟输入文本，如/输入 文本 回车"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.text_input(event)  # type: ignore

    @filter.command("滑动")
    async def swipe(
        self,
        event: AstrMessageEvent,
        start_x: int | None = None,
        start_y: int | None = None,
        end_x: int | None = None,
        end_y: int | None = None,
    ):
        """模拟滑动，如/滑动 100 200 300 400"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.swipe(event, start_x, start_y, end_x, end_y)  # type: ignore

    @filter.command("缩放")
    async def zoom_to_scale(self, event: AstrMessageEvent, scale_factor: float = 1.5):
        """缩放网页，如/缩放 1.5"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.zoom_to_scale(event, scale_factor)  # type: ignore

    @filter.command("滚动")
    async def scroll(self, event: AstrMessageEvent):
        """滚动网页，如/滚动 上 100"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.scroll(event)  # type: ignore

    @filter.command("当前页面")
    async def view_page(
        self, event: AstrMessageEvent, zoom_factor: float | None = None
    ):
        """查看当前标签页的内容"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.view_page(event, zoom_factor)  # type: ignore

    @filter.command("整页")
    async def view_full_page(
        self, event: AstrMessageEvent, zoom_factor: float | None = None
    ):
        """查看当前标签页的内容，如/当前页面 1.5"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.view_full_page(event, zoom_factor)  # type: ignore

    @filter.command("上一页")
    async def go_back(self, event: AstrMessageEvent):
        """跳转上一页"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.go_back(event)  # type: ignore

    @filter.command("下一页")
    async def go_forward(self, event: AstrMessageEvent):
        """跳转下一页"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.go_forward(event)  # type: ignore

    @filter.command("标签页列表")
    async def get_all_tabs_titles(self, event: AstrMessageEvent):
        """查看当前标签页列表"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.get_all_tabs_titles(event)  # type: ignore

    @filter.command("标签页", alias={"切换标签页"})
    async def switch_to_tab(self, event: AstrMessageEvent, index: int = 1):
        """切换到指定的标签页，如/标签页 1"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.switch_to_tab(event, index)  # type: ignore

    @filter.command("关闭标签页")
    async def close_tab(self, event: AstrMessageEvent):
        """关闭指定的标签页，如/关闭标签页 1 2 3"""
        if not await self._ensure_browser_ready(event):
            return
        await self.operator.close_tab(event)  # type: ignore

    @filter.command("关闭浏览器")
    async def close_browser(self, event: AstrMessageEvent):
        """关闭浏览器"""
        if not await self._ensure_browser_ready(event):
            return
        await self.browser.terminate()  # type: ignore
        self.browser = None
        self.operator = None
        self._browser_ready = False

    @filter.command("查看收藏夹", alias={"收藏夹"})
    async def favorite_list(self, event: AstrMessageEvent):
        """查看收藏夹列表"""
        favorites = self.fav_mgr.dump()
        if not favorites:
            yield event.plain_result("收藏夹为空")
            return
        lines = [
            f"{idx}. {name}: {url}"
            for idx, (name, url) in enumerate(favorites.items(), 1)
        ]
        text = "收藏夹列表：\n" + "\n\n".join(lines)
        image = await self.text_to_image(text)
        yield event.image_result(image)

    @filter.command("收藏", alias={"添加收藏"})
    async def add_favorite(
        self,
        event: AstrMessageEvent,
        name: str | None = None,
        url: str | None = None,
    ):
        """收藏 <名称> <网址>"""
        if not name or not url:
            yield event.plain_result("用法：收藏 <名称> <网址>")
            return
        if self.fav_mgr.add(name, url):
            yield event.plain_result(f"已收藏：{name}")
        else:
            yield event.plain_result(f"{name} 已存在于收藏夹中")

    @filter.command("取消收藏")
    async def delete_favorite(
        self,
        event: AstrMessageEvent,
        name: str | None = None,
    ):
        """取消收藏 <名称>"""
        if not name:
            yield event.plain_result("请输入要取消的收藏名称")
            return
        if self.fav_mgr.remove(name):
            yield event.plain_result(f"已取消收藏：{name}")
        else:
            yield event.plain_result(f"{name} 不在收藏夹中")

    @filter.command("清空收藏夹", alias={"清空收藏"})
    async def clear_favorite(self, event: AstrMessageEvent):
        """清空收藏夹"""
        if self.fav_mgr.clear():
            yield event.plain_result("已清空收藏夹")
        else:
            yield event.plain_result("收藏夹本来就是空的")

    @filter.command("浏览器设置")
    async def set_browser(
        self,
        event: AstrMessageEvent,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        zoom_factor: float | None = None,
    ):
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

    @filter.command("浏览器帮助")
    async def help(self, event: AstrMessageEvent):
        """浏览器帮助"""
        url = await self.text_to_image(HELP_TEXT)
        yield event.image_result(url)
