import json
from pathlib import Path

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig


class FavoriteManager:
    """
    收藏夹管理器（单实例）

    职责：
    - 管理收藏数据的内存态
    - 负责持久化（JSON）
    - 提供原子级 CRUD 接口
    """

    def __init__(self, config: AstrBotConfig, file_path: Path) -> None:
        self._config = config
        self._file_path: Path = file_path

        # name -> url
        self._favorites: dict[str, str] = {}

        self._load()

    # ─────────────────────────────
    # 内部 I/O
    # ─────────────────────────────

    def _load(self) -> None:
        """加载收藏数据（失败时回退为空）"""
        if not self._file_path.exists():
            self._save()
            return

        try:
            with self._file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._favorites = {str(k): str(v) for k, v in data.items()}
                else:
                    logger.error("favorite.json 格式非法，已重置")
                    self._favorites = {}
        except json.JSONDecodeError as e:
            logger.error(f"favorite.json 解析失败: {e}")
            self._favorites = {}
        except Exception as e:
            logger.exception(f"读取 favorite.json 失败: {e}")
            self._favorites = {}

    def _save(self) -> None:
        """持久化当前收藏数据"""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._file_path.open("w", encoding="utf-8") as f:
                json.dump(
                    self._favorites,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            logger.exception(f"写入 favorite.json 失败: {e}")

    # ─────────────────────────────
    # 查询接口（只读）
    # ─────────────────────────────

    def list_names(self) -> list[str]:
        """返回所有收藏名称（保持插入顺序）"""
        return list(self._favorites.keys())

    def get(self, name: str) -> str | None:
        """获取指定收藏的 URL"""
        return self._favorites.get(name)

    def dump(self) -> dict[str, str]:
        """获取收藏夹快照（副本）"""
        return dict(self._favorites)

    def is_empty(self) -> bool:
        return not self._favorites

    # ─────────────────────────────
    # 写操作（原子）
    # ─────────────────────────────

    def add(self, name: str, url: str) -> bool:
        """
        添加收藏

        :return: 是否新增成功（已存在返回 False）
        """
        if name in self._favorites:
            return False

        self._favorites[name] = url
        self._save()
        return True

    def remove(self, name: str) -> bool:
        """
        删除收藏

        :return: 是否删除成功
        """
        if name not in self._favorites:
            return False

        del self._favorites[name]
        self._save()
        return True

    def clear(self) -> bool:
        """
        清空收藏夹

        :return: 是否执行了清空
        """
        if not self._favorites:
            return False

        self._favorites.clear()
        self._save()
        return True
