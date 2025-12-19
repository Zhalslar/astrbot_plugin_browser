from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


class TickOverlay:
    # ------------------------------------------------------------------
    # 类常量：所有“不会随实例变化”的样式/路径信息
    # ------------------------------------------------------------------
    DEFAULT_FONT_PATH: Path = Path(
        "data/plugins/astrbot_plugin_browser/resource/kaiti_GB2312.ttf"
    )
    DEFAULT_SCALE_PATH: Path = Path(
        "data/plugins/astrbot_plugin_browser/resource/ticks_overlay.png"
    )

    # 颜色
    FONT_COLOR: tuple[int, int, int] = (200, 0, 0)
    LINE_COLOR: tuple[int, int, int] = (0, 0, 0)
    DOT_COLOR: tuple[int, int, int] = (0, 0, 0)

    # 刻度长度
    MAJOR_TICK_LENGTH_X: int = 20
    MINOR_TICK_LENGTH_X: int = 10
    MAJOR_TICK_LENGTH_Y: int = 30
    MINOR_TICK_LENGTH_Y: int = 15

    # 交点半径
    DOT_RADIUS: int = 1

    # 默认尺寸
    DEFAULT_WIDTH: int = 4000
    DEFAULT_HEIGHT: int = 13000
    DEFAULT_TICK_INTERVAL: int = 100
    DEFAULT_FONT_SIZE: int = 20

    # ------------------------------------------------------------------
    # 构造器：只保留“可能变化”的参数，其余一律用类常量
    # ------------------------------------------------------------------
    def __init__(
        self,
        *,
        font_path: Path | None = None,
        scale_path: Path | None = None,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        tick_interval: int = DEFAULT_TICK_INTERVAL,
        font_size: int = DEFAULT_FONT_SIZE,
    ) -> None:
        self.font_path = font_path or self.DEFAULT_FONT_PATH
        self.scale_path = scale_path or self.DEFAULT_SCALE_PATH
        self.width = width
        self.height = height
        self.tick_interval = tick_interval
        self.font_size = font_size

    # ------------------------------------------------------------------
    # 以下实现与原先完全一致，仅把硬编码常量换成类常量
    # ------------------------------------------------------------------
    def create_overlay(self) -> None:
        """生成刻度覆盖图并保存为PNG"""
        img = Image.new("RGBA", (self.width, self.height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # X 轴主/次刻度
        for x in range(0, self.width + 1, self.tick_interval):
            draw.line(
                [(x, self.MAJOR_TICK_LENGTH_X), (x, 0)],
                fill=self.LINE_COLOR,
            )
            for j in range(1, 10):
                minor_x = x - (j * self.tick_interval // 10)
                if minor_x > 0:
                    draw.line(
                        [(minor_x, self.MINOR_TICK_LENGTH_X), (minor_x, 0)],
                        fill=self.LINE_COLOR,
                    )

        # Y 轴主/次刻度
        for y in range(0, self.height + 1, self.tick_interval):
            draw.line(
                [(0, y), (self.MAJOR_TICK_LENGTH_Y, y)],
                fill=self.LINE_COLOR,
            )
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
                (x, self.MAJOR_TICK_LENGTH_X),
                str(x),
                font=font,
                fill=self.FONT_COLOR,
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

    def overlay_on_background(self, background_bytes: bytes) -> bytes:
        """将刻度覆盖层叠加到背景图上，自动检查 overlay 是否存在"""
        if not self.scale_path.exists():
            self.create_overlay()

        background = Image.open(BytesIO(background_bytes)).convert("RGBA")
        overlay = Image.open(self.scale_path).convert("RGBA")

        combined = Image.new("RGBA", background.size)
        combined.paste(background, (0, 0))
        combined.paste(overlay, (0, 0), overlay)

        output = BytesIO()
        combined.save(output, format="PNG")
        return output.getvalue()

# 全局单例
tick_overlay = TickOverlay()
