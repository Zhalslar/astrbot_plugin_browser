import asyncio
from collections.abc import Sequence

from playwright.async_api import BrowserContext, Cookie, Page, async_playwright

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig

from .cookie import CookieManager
from .ticks_overlay import tick_overlay


class BrowserManager:
    """
    浏览器统一管理器：
    - 基于序号的多标签页管理
    - 始终保证存在一个可用页面
    """

    def __init__(self, config: AstrBotConfig, cookie: CookieManager):
        """
        初始化管理器（不启动浏览器）

        :param cookie: Cookie 持久化管理器
        """
        self.config = config
        self.cookie = cookie

        self.default_url = config["default_url"]

        self.playwright = None
        self.browser = None
        self.context: BrowserContext | None = None

        self.all_pages: list[Page] = []
        self.current_index: int | None = None
        self.page: Page | None = None

        self._terminated = False

    # ================= 生命周期 ==================

    async def initialize(self):
        """
        启动浏览器并恢复 Cookie
        初始化完成后保证至少存在一个页面
        """
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.firefox.launch(
            headless=True,
            args=["--mute-audio", "--disable-gpu"],
            firefox_user_prefs={
                "intl.accept_languages": "zh-CN,zh",
                "intl.locale.requested": "zh-CN",
                "general.useragent.locale": "zh-CN",
            },
        )

        self.context = await self.browser.new_context()

        cookies = self.cookie.load_cookies()
        if cookies:
            await self.context.add_cookies(cookies)

        await self._ensure_page()

    async def terminate(self):
        """
        关闭浏览器并持久化状态
        调用后实例不可再使用
        """
        self._terminated = True

        await self.save_cookies()

        for p in list(self.all_pages):
            try:
                await p.close()
            except Exception:
                pass

        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    # ================= 内部保障 ==================

    def _require_context(self) -> BrowserContext:
        if self._terminated:
            raise RuntimeError("BrowserManager 已终止")
        if self.context is None:
            raise RuntimeError("BrowserContext 未初始化")
        return self.context

    async def _ensure_page(self, index: int | None = None) -> Page:
        """
        确保存在一个合法的当前页面
        """
        context = self._require_context()

        if not self.all_pages:
            page = await context.new_page()
            await page.goto(self.default_url)
            self.all_pages.append(page)
            self.current_index = 0
            self.page = page
            return page

        if index is None:
            index = self.current_index

        if index is None or not (0 <= index < len(self.all_pages)):
            index = 0

        self.current_index = index
        self.page = self.all_pages[index]
        return self.page

    async def save_cookies(self):
        """
        保存当前浏览器上下文的 Cookie
        """
        if not self.context:
            return
        cookies: list[Cookie] = await self.context.cookies()
        self.cookie.save_cookies(cookies)

    # ================= 标签页管理 ==================

    async def get_all_tabs_titles(self) -> list[str]:
        """
        获取所有标签页标题（按序号顺序）
        """
        return await asyncio.gather(*(p.title() for p in self.all_pages))

    async def switch_tab(self, index: int) -> str | None:
        """
        切换到指定序号的标签页
        """
        if not (0 <= index < len(self.all_pages)):
            return f"无效的标签页序号 {index}"

        page = await self._ensure_page(index)
        title = await page.title()
        return f"已切换到标签页【{title}】"

    async def close_tab(self, index: int) -> str:
        """
        关闭指定序号的标签页
        自动修正当前页面
        """
        if not (0 <= index < len(self.all_pages)):
            return f"无效的标签页序号 {index}"

        target = self.all_pages.pop(index)
        title = await target.title()
        await target.close()

        if not self.all_pages:
            await self._ensure_page()
        else:
            await self._ensure_page(min(index, len(self.all_pages) - 1))

        return f"已关闭标签页【{title}】"

    # ================= 页面访问 ==================

    async def search(
        self,
        url: str,
        timeout: int = 30000,
        zoom_factor: float = 1.5,
        max_pages: int = 5,
    ) -> str | None:
        """
        打开指定 URL
        - 已存在则直接切换
        - 不存在则新建标签页
        :return: None 表示成功，字符串表示错误信息
        """
        for i, p in enumerate(self.all_pages):
            if p.url == url:
                await self._ensure_page(i)
                return None

        if len(self.all_pages) >= max_pages:
            await self.close_tab(0)

        page = await self._require_context().new_page()

        try:
            await page.goto(url, timeout=timeout)
            await page.wait_for_load_state("networkidle")
            await page.evaluate(f"document.body.style.zoom = {zoom_factor};")
        except Exception as e:
            await page.close()
            logger.error(f"URL访问失败: {e}")
            return "访问失败"

        self.all_pages.append(page)
        self.current_index = len(self.all_pages) - 1
        self.page = page

        await self.save_cookies()
        return None

    # ================= 页面交互 ==================

    async def click_coord(self, coords: Sequence[int]) -> str | None:
        """
        点击页面指定坐标 [x, y]
        """
        if len(coords) != 2:
            return "坐标参数格式错误"

        page = await self._ensure_page()
        x, y = map(int, coords)

        await page.mouse.click(x, y, delay=100)
        await asyncio.sleep(1)
        return None

    async def swipe(self, coords: Sequence[int]) -> str | None:
        """
        从起点滑动到终点 [sx, sy, ex, ey]
        """
        if len(coords) != 4:
            return "滑动参数格式错误"

        page = await self._ensure_page()
        sx, sy, ex, ey = map(int, coords)

        await page.mouse.move(sx, sy)
        await page.mouse.down()
        await page.mouse.move(ex, ey, steps=5)
        await page.mouse.up()

        await asyncio.sleep(1)
        return None

    async def click_button(self, button_text: str) -> str | None:
        """
        点击包含指定文本的按钮
        """
        page = await self._ensure_page()
        await page.wait_for_load_state("load")

        btn = await page.query_selector(f'//button[contains(., "{button_text}")]')
        if btn is None:
            return f"未找到【{button_text}】按钮"

        await btn.click()
        await asyncio.sleep(1)
        return None

    async def text_input(self, text: str, enter: bool = True) -> str | None:
        """
        向第一个可见输入框输入文本
        """
        page = await self._ensure_page()
        await page.wait_for_load_state("load")

        inputs = await page.query_selector_all("input:not([disabled]):not([readonly])")

        for el in inputs:
            if await el.is_visible():
                await el.fill(text)
                if enter:
                    await page.keyboard.press("Enter")
                return None

        return "未找到可用的输入框"

    async def text_input_by_selector(self, selector: str, text: str) -> str | None:
        """
        向指定选择器的输入框填入文本
        """
        page = await self._ensure_page()
        await page.wait_for_load_state("load")

        el = await page.query_selector(selector)
        if el is None:
            return f"未找到选择器【{selector}】对应的元素"

        await el.fill(text)
        return None

    async def scroll_by(self, distance: int, direction: str) -> str | None:
        """
        按方向滚动页面
        """
        page = await self._ensure_page()
        dx, dy = 0, 0

        if direction == "上":
            dy = -distance
        elif direction == "下":
            dy = distance
        elif direction == "左":
            dx = -distance
        elif direction == "右":
            dx = distance
        else:
            return "无效的滚动方向"

        await page.evaluate(f"window.scrollBy({dx}, {dy});")
        return None

    async def go_back(self) -> str | None:
        """
        返回历史记录上一页
        """
        page = await self._ensure_page()
        await page.go_back()
        await page.wait_for_load_state("load")
        return None

    async def go_forward(self) -> str | None:
        """
        前进到历史记录下一页
        """
        page = await self._ensure_page()
        await page.go_forward()
        await page.wait_for_load_state("load")
        return None

    # ================= 页面展示 ==================

    async def zoom_to_scale(self, scale_factor: float) -> str | None:
        """
        设置页面缩放比例
        """
        page = await self._ensure_page()
        await page.evaluate(f"document.body.style.zoom = {scale_factor};")
        return None

    async def get_screenshot(
        self,
        zoom_factor: float | None = None,
        full_page: bool = False,
        viewport_width: int = 1920,
        viewport_height: int = 1440,
    ) -> bytes | None:
        """
        获取当前页面截图
        """
        page = await self._ensure_page()

        if zoom_factor is not None:
            await page.evaluate(f"document.body.style.zoom = {zoom_factor};")
            await page.evaluate("window.scrollTo(0, 0);")

        await page.set_viewport_size(
            {"width": viewport_width, "height": viewport_height}
        )

        raw = await page.screenshot(
            full_page=full_page,
            type="jpeg",
            quality=100,
            timeout=30000,
        )

        return tick_overlay.overlay_on_background(raw)
