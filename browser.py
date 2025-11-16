
import asyncio
import json
from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright

from astrbot import logger

from .ticks_overlay import TickOverlayManager


class BrowserManager:
    def __init__(self, browser_cookies_file: Path):
        self.playwright = None
        self.browser = None
        self.context: BrowserContext | None = None
        self.user_sessions: dict[str, Page] = {}  # 每个group_id对应一个Page
        self.all_pages: list[Page] = []
        self.cookies_file_path = browser_cookies_file  # cookies文件路径
        self.in_memory_cookies: list = []  # 内存中的cookies副本（保持列表格式）
        self.tom = TickOverlayManager()

    async def initialize(self):
        """初始化浏览器"""
        if not self.browser:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.firefox.launch(
                headless=True,
                args=[
                    "--mute-audio",
                    "--disable-gpu",
                ],
                firefox_user_prefs={
                    "intl.accept_languages": "zh-CN,zh",
                    "intl.locale.requested": "zh-CN",
                    "general.useragent.locale": "zh-CN",
                    "javascript.enabled": True,
                }
            )
            self.context = await self.browser.new_context()  # 创建新的浏览器上下文
            await self.load_cookies()  # 在创建新的浏览器上下文之后加载cookies
        return True

    async def close_browser(self) -> bool:
        """关闭浏览器并保存状态"""
        for group_id, page in list(self.user_sessions.items()):
            await page.close()
            del self.user_sessions[group_id]
        if self.context:
            await self.save_cookies()
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        return True


    async def add_cookies(self, cookies: list):
        """添加cookies到当前的浏览器上下文"""
        if self.context:
            await self.context.add_cookies(cookies)
            self.in_memory_cookies = cookies
        else:
            raise Exception("浏览器上下文未初始化，请先初始化浏览器。")

    async def get_cookies(self) -> list:
        """获取当前浏览器上下文的cookies"""
        if self.context:
            cookies = await self.context.cookies()
            return cookies
        else:
            raise Exception("浏览器上下文未初始化，请先初始化浏览器。")


    async def clear_cookies(self, delete_file_cookies: bool = False):
        """清除当前浏览器上下文的cookies"""
        if self.context:
            await self.context.clear_cookies()
            self.in_memory_cookies = []
            if delete_file_cookies:
                await self.save_cookies()
        else:
            raise Exception("浏览器上下文未初始化，请先初始化浏览器。")

    async def load_cookies(self):
        """从json文件中加载cookies到当前的浏览器上下文"""
        try:
            # 尝试打开并加载 cookies 文件
            with open(self.cookies_file_path, encoding="utf-8") as f:
                cookies = json.load(f)
                self.in_memory_cookies = cookies
                if self.context:
                    await self.context.add_cookies(cookies)
        except FileNotFoundError:
            # 如果文件不存在，则创建一个空的 JSON 文件
            print("Cookies文件未找到，正在创建空的cookies文件。")
            self.cookies_file_path.parent.mkdir(
                parents=True, exist_ok=True
            )  # 确保父目录存在
            with open(self.cookies_file_path, "w", encoding="utf-8") as f:
                json.dump([], f)  # 创建一个空的 JSON 数组
            self.in_memory_cookies = []  # 初始化 in_memory_cookies 为一个空列表
        except json.JSONDecodeError:
            print("Cookies文件格式错误，跳过加载。")


    async def save_cookies(self):
        """保存当前浏览器上下文的cookies到json文件中"""
        if self.context:
            cookies = await self.context.cookies()
            with open(self.cookies_file_path, "w") as f:
                json.dump(cookies, f, indent=4)
            self.in_memory_cookies = cookies
        else:
            # 清空JSON文件中的cookie
            with open(self.cookies_file_path, "w") as f:
                json.dump([], f)
            self.in_memory_cookies = []



    async def zoom_to_scale(self, group_id: str, scale_factor: float) -> str | None:
        """根据提供的缩放比例缩放网页"""
        if group_id not in self.user_sessions:
            return "页面未打开"
        page = self.user_sessions[group_id]
        await page.evaluate(f"document.body.style.zoom = {scale_factor};")
        await asyncio.sleep(0.5)
        return None

    async def close_tab(self, group_id: str|None = None, tab_index: int|None = None) -> str:
        """关闭指定序号的标签页，并从所有相关数据结构中移除"""
        await self.save_cookies()
        if tab_index is not None:
            if not (0 <= tab_index < len(self.all_pages)):
                return f"无效的标签页序号{tab_index}"
            target_page = self.all_pages[tab_index]
        elif group_id:
            target_page = next((page for gid, page in self.user_sessions.items() if gid == group_id), None)
            if not target_page:
                return "未找到对应的群组或标签页"
        else:
            return "未指定群号或序号"
        # 获取并移除关联的group_id
        group_id_to_remove = next((gid for gid, page in self.user_sessions.items() if page == target_page), None)

        if target_page in self.all_pages: # 从all_pages中移除目标页面
            self.all_pages.remove(target_page)

        if group_id_to_remove:  # 如果找到了关联的group_id，则从user_sessions中移除
            del self.user_sessions[group_id_to_remove]

        title = await target_page.title()
        await target_page.close()  # 关闭页面
        return f"已关闭标签页【{title}】"


    async def switch_to_tab(self, group_id: str, tab_index: int) -> str | None:
        """根据标签页序号切换当前页面"""
        if not (0 <= tab_index < len(self.all_pages)):
            return "无效的标签页序号"
        self.user_sessions[group_id] = self.all_pages[tab_index]
        return None


    async def search(
            self,
            group_id: str,
            url: str,
            timeout: int = 30000,
            zoom_factor:float=1.5,
            max_pages: int = 5
    ) -> str | None:
        """访问对应的url,如果有重复页面则直接切换，否则创建新页面"""

        if self.all_pages:
            for index, page in enumerate(self.all_pages):
                if page.url == url:
                    await self.switch_to_tab(group_id, index)
                    return None

        try:
            page = await self.context.new_page() # type: ignore
            await page.goto(url=url, timeout=timeout)
            await page.wait_for_load_state("networkidle")
            await page.evaluate(f"document.body.style.zoom = {zoom_factor};")
            self.user_sessions[group_id] = page
            self.all_pages.append(page)
             # 如果超过最大标签页数量，移除最早的标签页
            if len(self.all_pages) > max_pages:
                await self.close_tab(tab_index=0)
            await self.save_cookies()
            return None
        except Exception as e:
            logger.error(f"URL访问失败: {e}")
            return "访问失败"


    async def click_coord(self, group_id: str, coords: list) -> str | None:
        """模拟点击网页的对应坐标"""
        if group_id not in self.user_sessions:
            return "页面未打开"
        page = self.user_sessions[group_id]
        x, y = map(int, coords)
        new_page = None
        def on_popup(popup):
            nonlocal new_page
            new_page = popup
            self.user_sessions[group_id] = new_page
        page.on("popup", on_popup)
        try:
            await page.mouse.click(x, y, delay=100)
            await asyncio.sleep(2)
        finally:
            page.remove_listener("popup", on_popup)
            await self.save_cookies()
        return None


    async def click_button(self, group_id: str, button_text:str) -> str | None:
        """模拟点击网页上的按钮"""
        if group_id not in self.user_sessions:
            return "页面未打开"
        page = self.user_sessions[group_id]
        await page.wait_for_load_state()
        login_button = await page.query_selector(f'//button[contains(., "{button_text}")]')
        if login_button is None:
            return f"未找到【{button_text}】按钮"
        new_page = None
        def on_popup(popup):
            nonlocal new_page
            new_page = popup
            self.user_sessions[group_id] = new_page
        page.on("popup", on_popup)
        try:
            await login_button.click()
            await asyncio.sleep(2)
        finally:
            page.remove_listener("popup", on_popup)
            await self.save_cookies()
        return None
    async def text_input(self, group_id: str, text: str, enter: bool = True) -> str | None:
        """在网页上输入文本"""
        if group_id not in self.user_sessions:
            return "页面未打开"

        page = self.user_sessions[group_id]
        await page.wait_for_load_state("networkidle")

        # 选出符合类型但未禁用、未只读的输入框（CSS无法判断可见性）
        raw_inputs = await page.query_selector_all(
            """input[type="text"]:not([disabled]):not([readonly]),
            input[type="email"]:not([disabled]):not([readonly]),
            input[type="password"]:not([disabled]):not([readonly])"""
        )

        # 进一步筛选出“可见”的输入框
        input_elements = []
        for el in raw_inputs:
            try:
                if await el.is_visible():
                    input_elements.append(el)
            except Exception as e:
                print(f"输入框可见性判断失败：{e}")

        if not input_elements:
            return "未找到可用的输入框"

        # 先找空的输入框
        for el in input_elements:
            try:
                input_value = await el.evaluate("el => el.value")
                if not input_value:
                    await el.fill(text)
                    if enter:
                        await page.keyboard.press("Enter")
                    await asyncio.sleep(1)
                    return None
            except Exception as e:
                logger.debug(f"输入失败（空输入框）：{e}")
                continue

        # 若都非空，清空第一个可用输入框后再填入
        for el in input_elements:
            try:
                await el.fill("")
                await el.fill(text)
                if enter:
                    await page.keyboard.press("Enter")
                await asyncio.sleep(1)
                return None
            except Exception as e:
                logger.debug(f"输入失败（兜底清空再填）：{e}")
                continue

        return "所有输入框都无法使用"

    async def text_input_by_selector(self, group_id: str, selector: str, text: str) -> str | None:
        """在指定的选择器元素中输入文本"""
        if group_id not in self.user_sessions:
            return "页面未打开"
        page = self.user_sessions[group_id]
        await page.wait_for_load_state("networkidle")
        input_element = await page.query_selector(selector)
        if input_element is None:
            return f"未找到选择器【{selector}】对应的元素"
        await input_element.fill(text)
        await asyncio.sleep(1)
        return None


    async def swipe(self, group_id: str, coords: list) -> str | None:
        """根据提供的起始和结束坐标进行滑动操作"""
        if group_id not in self.user_sessions:
            return "页面未打开"
        page = self.user_sessions[group_id]
        startX, startY, endX, endY = map(int, coords)
        await page.mouse.move(startX, startY)
        await page.mouse.down()
        await page.mouse.move(endX, endY, steps=5)  # 可以调整steps的数量来控制滑动的速度
        await asyncio.sleep(0.2)  # 等待一段时间确保滑动完成
        await page.mouse.up()
        await asyncio.sleep(2)
        await self.save_cookies()
        return None

    async def scroll_by(self, group_id: str, distance: int, direction: str) -> str | None:
        """根据提供的方向和距离进行滚动操作"""
        if group_id not in self.user_sessions:
            return "页面未打开"
        page = self.user_sessions[group_id]
        await page.wait_for_load_state("networkidle")
        if direction == "上":
            await page.evaluate(f"window.scrollBy(0, -{distance});")
        elif direction == "下":
            await page.evaluate(f"window.scrollBy(0, {distance});")
        elif direction == "左":
            await page.evaluate(f"window.scrollBy(-{distance}, 0);")
        elif direction == "右":
            await page.evaluate(f"window.scrollBy({distance}, 0);")
        await asyncio.sleep(0.2)
        return None


    async def go_back(self, group_id: str)-> str | None:
        """跳转到浏览器历史记录中的上一页"""
        if group_id not in self.user_sessions:
            raise Exception("浏览器未打开")
        page = self.user_sessions[group_id]
        await page.go_back()
        await page.wait_for_load_state("networkidle")
        return None


    async def go_forward(self, group_id: str) -> str | None:
        """跳转到浏览器历史记录中的下一页"""
        if group_id not in self.user_sessions:
            return "页面未打开"
        page = self.user_sessions[group_id]
        await page.go_forward()
        await page.wait_for_load_state("networkidle")
        return None

    async def get_all_tabs_titles(self) -> list[str]:
        """获取所有标签页的名称"""
        titles = []
        for page in self.all_pages:
            title = await page.title()  # 获取每个页面的标题
            titles.append(title)
        return titles


    async def get_screenshot(
            self,
            group_id: str,
            zoom_factor: float|None = None,
            full_page: bool = False,
            viewport_width: int = 1920,
            viewport_height: int = 1440
    ) -> bytes | None:
        """获取对应群聊网页的截图"""
        # if group_id not in self.user_sessions:
        #     return
        page = self.user_sessions[group_id]
        if zoom_factor:
            await page.evaluate(f"document.body.style.zoom = {zoom_factor};")
            await page.evaluate("window.scrollTo(0, 0);")
        await page.set_viewport_size({"width": viewport_width, "height": viewport_height})
        screenshot = await page.screenshot(
            full_page=full_page,
            type="jpeg",
            quality=100,
            timeout=30000
        )
        image: bytes = self.tom.overlay_on_background(screenshot)
        return image

