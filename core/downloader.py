# browser_downloader.py
"""
Production-ready Playwright browser downloader

特性：
- Virtualenv safe
- Concurrent safe
- 单次调用只处理一个浏览器
- 下载完成后自动验证可启动性
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from astrbot.api import logger


class BrowserDownloader:
    """
    Playwright 浏览器下载器（生产级）

    download() 是原子操作：
    - 安装 playwright（如需要）
    - 安装 browser（如需要）
    - 验证 browser 可启动
    """

    _SUPPORTED = {"firefox", "chromium", "webkit"}

    _global_lock = asyncio.Lock()

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.browsers_dir = data_dir / "browsers"

        self.env = os.environ.copy()
        self.env["PLAYWRIGHT_BROWSERS_PATH"] = str(self.browsers_dir)

        # ★ 关键：同步到当前 Python 进程，供 async_playwright 使用
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(self.browsers_dir)
        logger.debug(f"PLAYWRIGHT_BROWSERS_PATH: {self.browsers_dir}")


    # ================== public ==================

    async def download(self, browser: str) -> bool:
        if browser not in self._SUPPORTED:
            raise ValueError(f"不支持的浏览器类型: {browser}")

        async with self._global_lock:
            if not await self._ensure_playwright():
                return False

            if await self._browser_installed(browser):
                # 已存在也要验证一次，防止残缺安装
                return await self.verify_browser(browser)

            if not await self._install_browser(browser):
                return False

            return await self.verify_browser(browser)

    # ================== playwright ==================

    async def _ensure_playwright(self) -> bool:
        if await self._run("playwright", "--version"):
            return True

        logger.info("playwright 未安装，开始安装（当前虚拟环境）")

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pip",
            "install",
            "-U",
            "playwright",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=self.env,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(
                f"pip install playwright 失败：\n{stderr.decode(errors='ignore')}"
            )
            return False

        return await self._run("playwright", "--version")

    # ================== browser ==================

    async def _browser_installed(self, browser: str) -> bool:
        if not self.browsers_dir.exists():
            return False

        prefix = f"{browser}-"
        try:
            for p in self.browsers_dir.iterdir():
                if p.is_dir() and p.name.startswith(prefix):
                    return True
        except Exception:
            return False

        return False

    async def _install_browser(self, browser: str) -> bool:
        logger.info(f"开始下载 {browser}")

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "playwright",
            "install",
            browser,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            logger.info(f"{browser} 下载完成")
            return True

        logger.error(
            f"{browser} 下载失败\n"
            f"stdout:\n{stdout.decode(errors='ignore')}\n"
            f"stderr:\n{stderr.decode(errors='ignore')}"
        )
        return False

    @staticmethod
    async def verify_browser(browser: str) -> bool:
        """
        真正启动一次浏览器，验证可用性
        """
        logger.debug(f"验证 {browser} 可启动性")
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as e:
            logger.error(f"playwright 包仍未就绪，无法验证浏览器: {e}")
            return False

        try:
            async with async_playwright() as p:
                launcher = getattr(p, browser)
                b = await launcher.launch(headless=True)
                await b.close()
            logger.debug(f"{browser} 验证通过")
            return True
        except Exception as e:
            logger.error(f"{browser} 启动验证失败: {e}")
            return False

    # ================== utils ==================

    async def _run(self, *args: str) -> bool:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            *args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=self.env,
        )
        await proc.communicate()
        return proc.returncode == 0
