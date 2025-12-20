
import asyncio
import os
import sys
from pathlib import Path

from astrbot.api import logger

HELP_TEXT = (
    "【浏览器插件帮助】：\n\n"
    "/搜索 <关键词> -搜索关键词\n\n"
    "/访问 <链接> -访问指定链接\n\n"
    "/点击 <x> <y> -模拟点击指定坐标\n\n"
    "/输入 <文本> <回车> -模拟输入文本\n\n"
    "/滑动 <起始X> <起始Y> <结束X> <结束Y> -模拟滑动\n\n"
    "/缩放 <缩放比例> -缩放网页\n\n"
    "/滚动 <方向> <距离> -滚动网页\n\n"
    "/当前页面 <缩放比例> -查看当前标签页的内容\n\n"
    "/整页 <缩放比例> -查看当前标签页的整页内容\n\n"
    "/上一页 -跳转上一页\n\n"
    "/下一页 -跳转下一页\n\n"
    "/标签页列表 -查看当前标签页列表\n\n"
    "/标签页 <序号> -切换到指定的标签页\n\n"
    "/关闭标签页 <序号> -关闭指定的标签页\n\n"
    "/关闭浏览器 -关闭浏览器\n\n"
    "/收藏夹 -查看收藏夹列表\n\n"
    "/收藏 <名称> <链接> -添加收藏\n\n"
    "/取消收藏 <名称> -取消收藏\n\n"
    "/清空收藏夹 -清空收藏夹\n\n"
    "/添加cookie <cookie> -添加cookie(施工中暂不可用...)\n\n"
    "/清空cookie -清空cookie\n\n"
    "/浏览器设置 <宽度> <高度> <缩放比> -设置浏览器参数\n\n"
    "/astrbot面板 -打开astrbot面板\n\n"
    "/napcat面板 -打开napcat面板\n\n"
    "/浏览器帮助 -查看帮助\n\n"
)


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

