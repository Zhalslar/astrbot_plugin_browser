# \astrbot\core\browser.py

import asyncio
import json
import shutil
import uuid
from collections.abc import Coroutine, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from playwright._impl._api_structures import SetCookieParam
from playwright.async_api import BrowserContext, Cookie, Page, async_playwright

T = TypeVar("T")


class CookieManager:
    def __init__(self):
        self.cookies_file = Path(__file__).resolve().parent / "browser_cookies.json"

    def load_cookies(self) -> list[dict]:
        """从 json 文件加载 cookies，返回 List[Cookie]（TypedDict）"""
        try:
            with open(self.cookies_file, encoding="utf-8") as f:
                raw_cookies: list[dict] = json.load(f)
                return raw_cookies
        except FileNotFoundError:
            print("Cookies 文件未找到或格式错误，返回空列表")
            self.cookies_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cookies_file, "w", encoding="utf-8") as f:
                json.dump([], f)
            return []
        except json.JSONDecodeError:
            print("Cookies 文件格式错误，无法解析，返回空列表且保留原文件")
            return []

    def save_cookies(self, cookies: list[dict]):
        """保存cookies到json文件中"""
        self.cookies_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cookies_file, "w") as f:
            json.dump(cookies, f, indent=4, ensure_ascii=False)


class BrowserCore:
    """
    浏览器核心
    """

    _BROWSER_ENGINES = {"firefox", "chromium", "webkit"}

    def __init__(self, config: dict):
        self.config = config
        self.cookie = CookieManager()

        self.cache_dir = Path(__file__).resolve().parent / "screenshot_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.browser_type: str = self.config.get("browser_type", "firefox")
        if self.browser_type not in self._BROWSER_ENGINES:
            raise ValueError(f"不支持的浏览器类型: {self.browser_type}")

        self.playwright = None
        self.browser = None
        self.context: BrowserContext | None = None

        self.all_pages: list[Page] = []
        self.current_index: int | None = None
        self.page: Page | None = None

        self._terminated = False

        # ===== 核心防护 =====
        self._op_lock = asyncio.Lock()

    # ======================================================
    # 通用兜底工具
    # ======================================================

    async def _safe_await(self, coro: Coroutine[Any, Any, T], retries: int = 2) -> T: # type: ignore
        """
        Playwright 操作超时重试机制
        :param coro: 协程
        :param timeout: 单次操作超时时间
        :param retries: 重试次数
        """
        for attempt in range(retries + 1):
            try:
                return await asyncio.wait_for(coro, self.config["timeout"])
            except asyncio.TimeoutError as e:

                if attempt < retries:
                    await asyncio.sleep(0.5)  # 等待再重试
                else:
                    raise RuntimeError("Playwright 操作超时") from e

    async def _safe_page_op(self, page: Page, coro: Coroutine[Any, Any, T]) -> T:
        """
        Page 级操作兜底：
        - 任意异常 -> 关闭 Page -> 移除 -> 重建
        """
        try:
            return await coro
        except Exception:
            await self._discard_page(page)
            raise

    async def _discard_page(self, page: Page):
        try:
            await page.close()
        except Exception:
            pass

        if page in self.all_pages:
            self.all_pages.remove(page)

        if not self.all_pages:
            await self._ensure_page()
        else:
            await self._ensure_page(
                min(self.current_index or 0, len(self.all_pages) - 1)
            )

    # ======================================================
    # 生命周期
    # ======================================================

    async def initialize(self):
        async with self._op_lock:
            self.playwright = await async_playwright().start()
            engine = getattr(self.playwright, self.browser_type)

            self.browser = await engine.launch(
                headless=True,
                **self._get_launch_options(self.browser_type),
            )

            self.context = await self.browser.new_context(
                viewport=self.config.get("viewport_size"),
            )

            raw_cookies = self.cookie.load_cookies()
            cookies = [
                SetCookieParam(**{k: v for k, v in c.items() if v is not None})
                for c in raw_cookies
            ]
            if cookies:
                await self.context.add_cookies(cookies)

            await self._ensure_page()

    async def terminate(self):
        """优雅关闭浏览器及相关资源，幂等执行"""
        async with self._op_lock:
            if self._terminated:
                return
            self._terminated = True

            async def safe_close(obj, close_method="close"):
                if obj is None:
                    return
                try:
                    coro = getattr(obj, close_method)
                    if asyncio.iscoroutinefunction(coro):
                        await coro()
                    else:
                        coro()
                except Exception:
                    pass

            # 保存 cookies
            await safe_close(self.save_cookies, "save_cookies")

            # 关闭所有 Page
            for page in self.all_pages:
                await safe_close(page)
            self.all_pages.clear()
            self.current_index = None
            self.page = None

            # 关闭 context / browser / playwright
            await safe_close(self.context)
            self.context = None

            await safe_close(self.browser)
            self.browser = None

            await safe_close(self.playwright, "stop")
            self.playwright = None

            # 清空并重建缓存目录
            if self.cache_dir.exists():
                try:
                    shutil.rmtree(self.cache_dir, ignore_errors=True)
                except Exception:
                    pass
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ======================================================
    # 参数
    # ======================================================

    def _get_launch_options(self, engine: str) -> dict[str, Any]:
        args = [
            "--mute-audio",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-extensions",
        ]

        opts: dict[str, Any] = {"args": args}

        if engine == "firefox":
            opts["firefox_user_prefs"] = {
                "intl.accept_languages": "zh-CN,zh",
                "intl.locale.requested": "zh-CN",
                "general.useragent.locale": "zh-CN",
                "media.autoplay.default": 5,
                "media.autoplay.blocking_policy": 2,
                "dom.ipc.processCount": 1,
                "browser.tabs.remote.autostart": False,
            }

        return opts

    async def _freeze_page(self, page: Page):
        """
        冻结指定 Page，使其不活动（暂停视频、动画、定时器等）。
        """
        try:
            await page.evaluate("""
                (() => {
                    document.querySelectorAll('video,audio').forEach(v => v.pause());
                    if (!window._freeze) {
                        window._oldSetInterval = window.setInterval;
                        window._oldRequestAnimationFrame = window.requestAnimationFrame;
                        window.setInterval = () => 0;
                        window.requestAnimationFrame = () => {};
                        window._freeze = true;
                    }
                })()
            """)
        except Exception:
            pass

    async def _unfreeze_page(self, page: Page):
        """
        解冻指定 Page，使其恢复活动（恢复视频、动画、定时器等）。
        """
        try:
            await page.evaluate("""
                (() => { window._freeze = false; })()
            """)
        except Exception:
            pass

    # ======================================================
    # 内部保障
    # ======================================================

    def _require_context(self) -> BrowserContext:
        if self._terminated:
            raise RuntimeError("BrowserManager 已终止")
        if self.context is None:
            raise RuntimeError("BrowserContext 未初始化")
        return self.context

    async def _ensure_page(self, index: int | None = None) -> Page:
        context = self._require_context()

        if not self.all_pages:
            # 初始化第一页
            page = await context.new_page()
            await self._safe_await(page.goto(self.config["default_url"]))
            self.all_pages.append(page)
            self.current_index = 0
            self.page = page
            return page

        if index is None:
            index = self.current_index or 0

        # 保证索引合法
        index = max(0, min(index, len(self.all_pages) - 1))

        # 切换前冻结旧 Page
        if self.page is not None and index != self.current_index:
            await self._freeze_page(self.page)

        # 更新索引和当前页
        self.current_index = index
        self.page = self.all_pages[index]

        # 激活新 Page（解除冻结）
        await self._unfreeze_page(self.page)

        return self.page

    async def save_cookies(self):
        if not self.context:
            return
        cookies: list[Cookie] = await self.context.cookies()
        self.cookie.save_cookies(cookies)  # type: ignore

    # ======================================================
    # 标签页管理
    # ======================================================

    async def get_all_tabs_titles(self) -> list[str]:
        async with self._op_lock:
            return await asyncio.gather(*(p.title() for p in self.all_pages))

    async def switch_tab(self, index: int) -> str | None:
        async with self._op_lock:
            if not (0 <= index < len(self.all_pages)):
                return f"无效的标签页序号 {index}"
            await self._ensure_page(index)


    async def close_tab(self, index: int) -> str:
        async with self._op_lock:
            if not (0 <= index < len(self.all_pages)):
                return f"无效的标签页序号 {index}"

            page = self.all_pages[index]
            title = await page.title()
            await self._discard_page(page)
            return f"已关闭标签页【{title}】"

    # ======================================================
    # 页面展示
    # ======================================================

    async def zoom_to_scale(self, scale: float) -> str | None:
        async with self._op_lock:
            page = await self._ensure_page()
            await page.evaluate(f"document.body.style.zoom = {scale};")
            return None

    async def screenshot(
        self,
        zoom_factor: float | None = None,
        full_page: bool = False,
    ) -> str | None:
        async with self._op_lock:
            page = await self._ensure_page()

            async def _shot():
                if zoom_factor:
                    await page.evaluate(f"document.body.style.zoom = {zoom_factor};")
                    await page.evaluate("window.scrollTo(0, 0);")

                return await page.screenshot(
                    full_page=full_page,
                    type="jpeg",
                    quality=min(self.config["screenshot_quality"], 100),
                )

            raw: bytes = await _shot()

            if raw is None:  # 截图失败
                return None

            # ========== 落地到缓存文件 ==========
            file_name = f"{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.jpg"
            cache_path = self.cache_dir / file_name
            cache_path.write_bytes(raw)

            return str(cache_path)

    # ======================================================
    # 页面访问
    # ======================================================

    async def search(self, url: str) -> str | None:
        async with self._op_lock:
            for i, p in enumerate(self.all_pages):
                if p.url == url:
                    await self._ensure_page(i)
                    return None

            while len(self.all_pages) > self.config["max_pages"]:
                old_page = self.all_pages.pop(0)
                await self._discard_page(old_page)

            page = await self._require_context().new_page()

            try:
                await self._safe_await(
                    page.goto(url, wait_until="domcontentloaded"),
                )
                await page.evaluate(
                    f"document.body.style.zoom = {self.config['zoom_factor']};"
                )
            except Exception:
                await self._discard_page(page)
                return "URL 访问失败"

            self.all_pages.append(page)
            self.current_index = len(self.all_pages) - 1
            self.page = page

            await self.save_cookies()
            return None

    # ======================================================
    # 页面交互
    # ======================================================
    async def click_coord(self, coords: Sequence[int]) -> str | None:
        if len(coords) != 2:
            return "坐标参数格式错误"

        x, y = map(int, coords)

        async with self._op_lock:
            page = await self._ensure_page()
            new_page: Page | None = None

            # 弹窗回调：新页面产生后立即替换当前页
            def on_popup(popup: Page):
                nonlocal new_page, page
                new_page = popup
                # 切换当前页到 popup
                self.all_pages.append(popup)
                self.current_index = len(self.all_pages) - 1
                self.page = popup

            page.on("popup", on_popup)

            try:
                await self._safe_page_op(
                    page,
                    self._safe_await(page.mouse.click(x, y, delay=100)),
                )
                await asyncio.sleep(2)

            finally:
                page.remove_listener("popup", on_popup)

        return None


    async def scroll_by(self, distance: int, direction: str) -> str | None:
        async with self._op_lock:
            page = await self._ensure_page()

            dx = dy = 0
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

            await self._safe_page_op(
                page,
                page.evaluate(f"window.scrollBy({dx}, {dy});"),
            )
            return None

    async def swipe(self, coords: Sequence[int]) -> str | None:
        if len(coords) != 4:
            return "滑动参数格式错误"
        async with self._op_lock:
            page = await self._ensure_page()
            sx, sy, ex, ey = map(int, coords)

            await page.mouse.move(sx, sy)
            await page.mouse.down()
            await page.mouse.move(ex, ey, steps=5)
            await page.mouse.up()

            await asyncio.sleep(1)
            return None

    async def text_input(self, text: str, enter: bool = True) -> str | None:
        async with self._op_lock:
            page = await self._ensure_page()
            await page.wait_for_load_state("load")

            inputs = await page.query_selector_all(
                "input:not([disabled]):not([readonly])"
            )

            for el in inputs:
                if await el.is_visible():
                    await el.fill(text)
                    if enter:
                        await page.keyboard.press("Enter")
                    return None

            return "未找到可用的输入框"

    async def text_input_by_selector(self, selector: str, text: str) -> str | None:
        async with self._op_lock:
            page = await self._ensure_page()
            await page.wait_for_load_state("load")

            el = await page.query_selector(selector)
            if el is None:
                return f"未找到选择器【{selector}】对应的元素"

            await el.fill(text)
            return None

    async def go_back(self) -> str | None:
        async with self._op_lock:
            page = await self._ensure_page()
            await page.go_back()
            await page.wait_for_load_state("load")
            return None

    async def go_forward(self) -> str | None:
        async with self._op_lock:
            page = await self._ensure_page()
            await page.go_forward()
            await page.wait_for_load_state("load")
            return None
