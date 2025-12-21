import hashlib
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


class TickOverlay:
    # -------------------- 颜色 --------------------
    FONT_COLOR: tuple[int, int, int] = (200, 0, 0)
    LINE_COLOR: tuple[int, int, int] = (0, 0, 0)
    DOT_COLOR: tuple[int, int, int] = (0, 0, 0)

    # -------------------- 刻度长度 --------------------
    MAJOR_TICK_LENGTH_X: int = 20
    MINOR_TICK_LENGTH_X: int = 10
    MAJOR_TICK_LENGTH_Y: int = 30
    MINOR_TICK_LENGTH_Y: int = 15

    # -------------------- 交点半径 --------------------
    DOT_RADIUS: int = 1

    def __init__(self, data_dir: Path, resource_dir: Path):
        self.cache_dir = data_dir / "overlay_cache"
        self.font_path = resource_dir / "kaiti_GB2312.ttf"
        self.scale_path = resource_dir / "ticks_overlay.png"

        # 基础参数
        self.width = 4000
        self.height = 13000
        self.tick_interval = 100
        self.font_size = 20

        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 生成刻度覆盖图
    # ------------------------------------------------------------------
    def create_overlay(self) -> None:
        img = Image.new("RGBA", (self.width, self.height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # X 轴主/次刻度
        for x in range(0, self.width + 1, self.tick_interval):
            draw.line([(x, self.MAJOR_TICK_LENGTH_X), (x, 0)], fill=self.LINE_COLOR)
            for j in range(1, 10):
                minor_x = x - (j * self.tick_interval // 10)
                if minor_x > 0:
                    draw.line(
                        [(minor_x, self.MINOR_TICK_LENGTH_X), (minor_x, 0)],
                        fill=self.LINE_COLOR,
                    )

        # Y 轴主/次刻度
        for y in range(0, self.height + 1, self.tick_interval):
            draw.line([(0, y), (self.MAJOR_TICK_LENGTH_Y, y)], fill=self.LINE_COLOR)
            for j in range(1, 10):
                minor_y = y + (j * self.tick_interval // 10)
                if minor_y < self.height:
                    draw.line(
                        [(self.MINOR_TICK_LENGTH_Y, minor_y), (0, minor_y)],
                        fill=self.LINE_COLOR,
                    )

        # 主刻度交点
        for x in range(0, self.width + 1, self.tick_interval):
            for y in range(0, self.height + 1, self.tick_interval):
                draw.ellipse(
                    [
                        (x - self.DOT_RADIUS, y - self.DOT_RADIUS),
                        (x + self.DOT_RADIUS, y + self.DOT_RADIUS),
                    ],
                    fill=self.DOT_COLOR,
                )

        # 文字标签
        font = ImageFont.truetype(str(self.font_path), self.font_size)
        for x in range(0, self.width + 1, self.tick_interval):
            draw.text(
                (x, self.MAJOR_TICK_LENGTH_X), str(x), font=font, fill=self.FONT_COLOR
            )
        for y in range(0, self.height + 1, self.tick_interval):
            draw.text(
                (self.MAJOR_TICK_LENGTH_Y + 5, y),
                str(y),
                font=font,
                fill=self.FONT_COLOR,
            )

        # 保存
        self.scale_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(self.scale_path), format="PNG")

    # ------------------------------------------------------------------
    # 叠加刻度并返回缓存文件路径
    # ------------------------------------------------------------------
    def overlay_on_background(self, background_path: Path | str) -> str:
        """
        将刻度覆盖层叠加到背景图上。
        返回合成后图片的本地缓存文件绝对路径。
        """
        # 1. 确保 overlay 存在
        if not self.scale_path.exists():
            self.create_overlay()

        # 2. 计算背景图摘要，生成缓存文件名
        background_path = Path(background_path)
        md5 = hashlib.md5(background_path.read_bytes()).hexdigest()
        cached_png = self.cache_dir / f"{md5}.png"

        # 3. 若缓存已存在，直接返回路径
        if cached_png.exists():
            return str(cached_png.resolve())

        # 4. 合成
        background = Image.open(background_path).convert("RGBA")
        overlay = Image.open(self.scale_path).convert("RGBA")

        combined = Image.new("RGBA", background.size)
        combined.paste(background, (0, 0))
        combined.paste(overlay, (0, 0), overlay)

        # 5. 保存到缓存
        combined.save(cached_png, format="PNG")

        # 6. 返回绝对路径
        return str(cached_png.resolve())

    def clear_cache(self):
        """
        清空 overlay_cache 下所有缓存文件并重建空目录。
        """
        if self.cache_dir.exists():
            try:
                shutil.rmtree(self.cache_dir, ignore_errors=True)
            except Exception:
                pass
        self.cache_dir.mkdir(parents=True, exist_ok=True)
