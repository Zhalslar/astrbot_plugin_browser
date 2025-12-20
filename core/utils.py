
import asyncio
import os
import sys
from pathlib import Path

from astrbot.api import logger


async def install_browser(data_dir: Path, browser_type: str = "firefox") -> bool:
    """
    静默安装指定的 Playwright 浏览器
    :param data_dir: Playwright 安装目录
    :param browser_type: 安装的浏览器，可选 "firefox", "chromium", "webkit"
    :return: 成功 True / 失败 False
    """
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(data_dir / "browsers")
    try:
        logger.info(f"正在安装 {browser_type} 浏览器...")
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "playwright",
            "install",
            browser_type,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
        return (await proc.wait()) == 0
    except FileNotFoundError as e:
        logger.error(f"playwright 安装失败: {e}")
        return False

async def check_browser_installed(browser_type: str = "firefox") -> bool:
    """
    检测指定浏览器是否已安装（纯检测，不弹窗口）
    :param browser_type: "firefox", "chromium", "webkit"
    :return: 已安装 True / 未安装 False
    """
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser_launcher = getattr(p, browser_type, None)
            if browser_launcher is None:
                logger.error(f"Playwright 不支持浏览器: {browser_type}")
                return False

            browser = await browser_launcher.launch(headless=True)
            await browser.close()
        return True
    except Exception as e:
        logger.exception(f"检测浏览器失败 ({browser_type}): {e}")
        return False

