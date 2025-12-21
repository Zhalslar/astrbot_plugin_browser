import asyncio
import os
import sys
from pathlib import Path

from astrbot.api import logger


async def generic_install(
    *cmd: str,
    extra_env: dict | None = None,
) -> bool:
    """
    通用异步安装器
    :param cmd: 完整命令序列，如 [sys.executable, "-m", "pip", "install", "playwright"]
    :param extra_env: 额外环境变量
    :return: 是否成功
    """
    env = {**os.environ, **(extra_env or {})}
    cmd_str = " ".join(cmd)
    logger.info(f"执行安装命令：{cmd_str}")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error(
            "安装失败，返回码 %s\nstdout: %s\nstderr: %s",
            proc.returncode,
            stdout.decode(errors="ignore"),
            stderr.decode(errors="ignore"),
        )
        return False
    logger.info(f"安装成功：{cmd_str}")
    return True


async def install_playwright_package() -> bool:
    """装 playwright PyPI 包"""
    return await generic_install(
        sys.executable,
        "-m",
        "pip",
        "install",
        "-U",
        "playwright",
    )


async def install_browser_bin(data_dir: Path, browser_type: str = "firefox") -> bool:
    """装浏览器二进制"""
    extra_env = {"PLAYWRIGHT_BROWSERS_PATH": str(data_dir / "browsers")}
    return await generic_install(
        sys.executable,
        "-m",
        "playwright",
        "install",
        browser_type,
        extra_env=extra_env,
    )


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
    except Exception:
        return False
