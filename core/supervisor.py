# astrbot/core/supervisor.py

import asyncio
import time
import traceback
from pathlib import Path
from typing import Any

import psutil

from astrbot.api import logger


class BrowserSupervisor:
    """
    纯 asyncio 版本浏览器管理器
    支持：
    - 检查浏览器安装
    - 启动/停止浏览器
    - 内存监控自动重启
    - 闲置自动关闭
    - 异步调用 BrowserCore 方法
    """

    def __init__(self, config: dict, data_dir: str):
        self.config = config
        sup_cfg: dict[str, Any] = config.get("supervisor", {})
        self.max_memory_percent: int = sup_cfg.get("max_memory_percent", 90)
        self.idle_timeout: int = sup_cfg.get("idle_timeout", 300)
        self.monitor_interval: float = sup_cfg.get("monitor_interval", 10.0)
        self.browser_type = config.get("browser_type", "firefox")
        self.verify_browser = config.get("verify_browser", True)

        self.data_dir = data_dir

        self.browser = None

        self._call_lock = asyncio.Lock()
        self._browser_lock = asyncio.Lock()

        self._last_active: float = time.time()
        self._monitor_task: asyncio.Task | None = None

    # ---------------- 生命周期 ----------------
    async def start(self):
        """启动监控协程，浏览器暂时不启动"""
        async with self._call_lock:
            if self._monitor_task is None or self._monitor_task.done():
                self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """停止浏览器和监控"""
        async with self._call_lock:
            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
                self._monitor_task = None

            if self.browser:
                try:
                    await self.browser.terminate()
                except Exception:
                    pass
                self.browser = None

    # ---------------- 对外调用 ----------------
    async def call(self, method: str, **kwargs):
        async with self._call_lock:
            if not self.browser:
                await self._start_browser()

            async with self._browser_lock:
                browser = self.browser
                if not browser:
                    return None
                func = getattr(browser, method, None)

            if func is None:
                raise AttributeError(f"BrowserCore 没有方法 {method}")

            self._last_active = time.time()
            return await func(**kwargs)

    # ---------------- 内部浏览器启动/重启 ----------------
    async def _start_browser(self):
        """启动浏览器"""
        async with self._browser_lock:
            # 检测浏览器安装
            if not self.browser:
                if self.verify_browser:
                    from .downloader import BrowserDownloader

                    if not await BrowserDownloader.verify_browser(self.browser_type):
                        logger.error(
                            "浏览器未安装或不可用，请先在聊天窗口发送命令：安装浏览器"
                        )
                        raise RuntimeError("浏览器未安装或不可用")

                from .browser import BrowserCore

                core = BrowserCore(self.config, Path(self.data_dir))
                try:
                    await core.initialize()
                except Exception:
                    logger.error("[Supervisor] BrowserCore.initialize 失败")
                    raise
                self.browser = core
                self._last_active = time.time()

    async def _stop_browser(self):
        """停止浏览器"""
        async with self._browser_lock:
            if self.browser:
                try:
                    await self.browser.terminate()
                except Exception:
                    logger.error("[Supervisor] BrowserCore.terminate 失败")
                    raise
                self.browser = None
                self._last_active = time.time()

    # ---------------- 监控 ----------------

    async def _monitor_loop(self):
        while True:
            try:
                await asyncio.sleep(self.monitor_interval)
                if not self.browser:
                    continue

                # 空闲检测
                if time.time() - self._last_active > self.idle_timeout:
                    await self._stop_browser()
                    logger.warning(
                        f"[Supervisor] 浏览器闲置超过 {self.idle_timeout}s，自动关闭浏览器"
                    )

                # 整体服务器内存监控
                mem = psutil.virtual_memory()
                if mem.percent > self.max_memory_percent:
                    await self._stop_browser()
                    logger.warning(
                        f"[Supervisor] 服务器内存占用过高 ({mem.percent:.1f}%)，自动关闭浏览器"
                    )

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Supervisor 监控循环异常:\n" + traceback.format_exc())
