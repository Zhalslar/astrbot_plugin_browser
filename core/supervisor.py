# astrbot/core/supervisor.py
import asyncio
import time
import traceback
from typing import Any

import psutil

from astrbot.api import logger

from .browser import BrowserCore


class BrowserSupervisor:
    """
    纯 asyncio 版本浏览器管理器
    支持：
    - 启动/停止浏览器
    - 内存监控自动重启
    - 闲置自动关闭
    - 异步调用 BrowserCore 方法
    上游保证 Playwright 已装好才会实例化本类，因此内部只处理运行时异常，不抛到上游。
    """

    def __init__(self, config: dict):
        self.config = config
        sup_cfg: dict[str, Any] = config.get("supervisor", {})
        self.max_memory_percent: int = sup_cfg.get("max_memory_percent", 90)
        self.idle_timeout: int = sup_cfg.get("idle_timeout", 300)
        self.monitor_interval: float = sup_cfg.get("monitor_interval", 10.0)

        self.browser: BrowserCore | None = None
        self._last_active: float = time.time()
        self._lock = asyncio.Lock()
        self._monitor_task: asyncio.Task | None = None
        self._restart_lock = asyncio.Lock()

    # ---------------- 生命周期 ----------------
    async def start(self):
        """启动浏览器和监控协程"""
        async with self._lock:
            if self.browser is None:
                await self._start_browser()

            if self._monitor_task is None or self._monitor_task.done():
                self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """停止浏览器和监控"""
        async with self._lock:
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
    async def call(self, method: str, **kwargs) -> Any:
        """线程安全地调用 BrowserCore 方法；失败自动重启"""
        async with self._lock:
            if self.browser is None:
                await self._restart_browser()

            self._last_active = time.time()
            func = getattr(self.browser, method, None)
            if func is None:
                raise AttributeError(f"BrowserCore 没有方法 {method}")
            try:
                return await func(**kwargs)
            except Exception:
                # 让上层拿到原始异常，同时触发重启
                raise

    # ---------------- 内部浏览器启动/重启 ----------------
    async def _start_browser(self):
        """启动 BrowserCore；失败时 self.browser 保持 None"""
        if self.browser is not None:
            return
        core = BrowserCore(self.config)
        try:
            await core.initialize()
        except Exception:
            logger.exception("[Supervisor] BrowserCore.initialize 失败")
            # 关键：把 browser 置 None，让监控能感知到需要重启
            raise
        else:
            self.browser = core

    async def _restart_browser(self):
        """带重试的重启逻辑；3 次失败后停手"""
        async with self._restart_lock:
            logger.info("[Supervisor] 浏览器重启开始")
            attempts = 0
            while attempts < 3:
                attempts += 1
                if self.browser:
                    try:
                        await self.browser.terminate()
                    except Exception:
                        pass
                    self.browser = None

                try:
                    await self._start_browser()
                except Exception:
                    await asyncio.sleep(2)
                    continue

                # 成功
                self._last_active = time.time()
                logger.info("[Supervisor] 浏览器重启完成")
                return

            logger.error(
                "[Supervisor] 浏览器重启失败超过 3 次，请检查 Playwright 或配置"
            )

    # ---------------- 监控 ----------------

    async def _monitor_loop(self):
        while True:
            try:
                await asyncio.sleep(self.monitor_interval)

                # 空闲检测
                idle = time.time() - self._last_active
                if idle > self.idle_timeout:
                    logger.warning(
                        f"[Supervisor] 浏览器闲置超过 {self.idle_timeout}s，自动关闭"
                    )
                    await self.stop()
                    continue

                # 整体服务器内存监控
                mem = psutil.virtual_memory()
                mem_percent = mem.percent  # 已使用百分比
                if (
                    mem_percent > self.max_memory_percent
                ):
                    logger.warning(
                        f"[Supervisor] 服务器内存占用过高 ({mem_percent:.1f}%)，自动重启浏览器"
                    )
                    await self._restart_browser()

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Supervisor 监控循环异常:\n" + traceback.format_exc())
