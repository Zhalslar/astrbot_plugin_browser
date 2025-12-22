# browser_downloader.py
"""
Production-ready Playwright browser downloader

特性：
- Virtualenv safe
- Concurrent safe
- 同一浏览器只允许一个下载任务
- 重复触发会复用当前下载任务
- 返回 (bool, message)
- 下载完成后自动验证可启动性
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from astrbot.api import logger


class BrowserDownloader:
    _SUPPORTED = {"firefox", "chromium", "webkit"}

    # 全局锁：防止 playwright install 竞态
    _global_lock = asyncio.Lock()

    # ★ 每个 browser 一个下载任务
    _download_tasks: dict[str, asyncio.Task] = {}

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.browsers_dir = data_dir / "browsers"

        self.env = os.environ.copy()
        self.env["PLAYWRIGHT_BROWSERS_PATH"] = str(self.browsers_dir)

        # 同步到当前进程，供 async_playwright 使用
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(self.browsers_dir)

        logger.debug(f"PLAYWRIGHT_BROWSERS_PATH = {self.browsers_dir}")

    # ================== public ==================

    async def download(self, browser: str) -> tuple[bool, str]:
        """
        下载指定浏览器（幂等）
        - 返回 (success, message)
        - 若已有下载任务，直接复用
        """
        if browser not in self._SUPPORTED:
            return False, f"不支持的浏览器类型: {browser}"

        # ★ 已有下载任务 → 复用
        task = self._download_tasks.get(browser)
        if task:
            logger.info(f"{browser} 已有下载任务，复用中")
            return await task

        # ★ 创建新任务
        task = asyncio.create_task(self._download_impl(browser))
        self._download_tasks[browser] = task

        try:
            return await task
        finally:
            # 清理 task（无论成功失败）
            self._download_tasks.pop(browser, None)

    # ================== core ==================

    async def _download_impl(self, browser: str) -> tuple[bool, str]:
        async with self._global_lock:
            ok, msg = await self._ensure_playwright()
            if not ok:
                return False, msg

            if await self._browser_installed(browser):
                logger.info(f"{browser} 已存在，进行完整性验证")
                if await self.verify_browser(browser):
                    return True, f"{browser} 已安装且可用"
                else:
                    logger.warning(f"{browser} 已存在但不可用，重新安装")

            ok, msg = await self._install_browser(browser)
            if not ok:
                return False, msg

            if await self.verify_browser(browser):
                return True, f"{browser} 下载并验证成功"

            return False, f"{browser} 下载完成，但启动验证失败"

    # ================== playwright ==================

    async def _ensure_playwright(self) -> tuple[bool, str]:
        if await self._run("playwright", "--version"):
            return True, "playwright 已就绪"

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
            err = stderr.decode(errors="ignore")
            logger.error(f"pip install playwright 失败:\n{err}")
            return False, "playwright 安装失败"

        if await self._run("playwright", "--version"):
            return True, "playwright 安装成功"

        return False, "playwright 安装完成但无法运行"

    # ================== browser ==================

    async def _browser_installed(self, browser: str) -> bool:
        if not self.browsers_dir.exists():
            return False

        prefix = f"{browser}-"
        try:
            return any(
                p.is_dir() and p.name.startswith(prefix)
                for p in self.browsers_dir.iterdir()
            )
        except Exception:
            return False

    async def _install_browser(self, browser: str) -> tuple[bool, str]:
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
            return True, f"{browser} 下载完成"

        out = stdout.decode(errors="ignore")
        err = stderr.decode(errors="ignore")
        logger.error(f"{browser} 下载失败\nstdout:\n{out}\nstderr:\n{err}")
        return False, f"{browser} 下载失败"

    @staticmethod
    async def verify_browser(browser: str) -> bool:
        """
        真正启动一次浏览器，验证可用性
        """
        logger.debug(f"验证 {browser} 可启动性")
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError:
            return False

        try:
            async with async_playwright() as p:
                launcher = getattr(p, browser)
                b = await launcher.launch(headless=True)
                await b.close()
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
