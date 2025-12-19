
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright._impl._api_structures import SetCookieParam
from playwright.async_api import Cookie

from astrbot.api import logger
from astrbot.core.config.astrbot_config import AstrBotConfig


class CookieManager:
    def __init__(self, config: AstrBotConfig, data_dir: Path):
        self.config = config
        self.cookies_file = data_dir / "browser_cookies.json"
    @staticmethod
    def parse_cookies(url, cookies_str):
        """将cookies字符串解析为Playwright所需的列表格式"""
        parsed_url = urlparse(url)
        domain = f".{parsed_url.netloc}"
        # 解析cookies字符串
        cookies_list = []
        for cookie in cookies_str.split("; "):
            parts = cookie.split("=", 1)
            if len(parts) < 2:
                continue
            name = parts[0].strip()
            value = parts[1].strip()
            # 处理cookie的域名
            cookie_dict = {"name": name, "value": value, "domain": domain, "path": "/"}
            # 处理其他属性
            attributes = cookie.split("; ")
            for attr in attributes[1:]:
                key_value = attr.strip().split("=", 1)
                if len(key_value) == 2:
                    key, val = key_value
                    key = key.lower()
                    val = val.strip()
                    if key == "expires":
                        try:
                            cookie_dict["expires"] = int(
                                datetime.strptime(
                                    val, "%a, %d-%b-%Y %H:%M:%S GMT"
                                ).timestamp()
                            )  # noqa: F821
                        except ValueError:
                            pass
                    elif key == "samesite":
                        cookie_dict["sameSite"] = val.capitalize()
                else:
                    key = key_value[0].lower()
                    if key == "httponly":
                        cookie_dict["httpOnly"] = True
                    elif key == "secure":
                        cookie_dict["secure"] = True

            cookies_list.append(cookie_dict)
        return cookies_list

    def load_cookies(self) -> list[SetCookieParam]:
        """从 json 文件加载 cookies，返回 List[Cookie]（TypedDict）"""
        try:
            with open(self.cookies_file, encoding="utf-8") as f:
                raw: list[dict] = json.load(f)
        except FileNotFoundError:
            logger.debug("Cookies 文件未找到或格式错误，返回空列表")
            self.cookies_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cookies_file, "w", encoding="utf-8") as f:
                json.dump([], f)
            return []
        except json.JSONDecodeError:
            logger.warning("Cookies 文件格式错误，无法解析，返回空列表且保留原文件")
            return []

        return [
            SetCookieParam(**{k: v for k, v in c.items() if v is not None}) for c in raw
        ]

    def save_cookies(self, cookies: list[Cookie]):
        """保存cookies到json文件中"""
        self.cookies_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cookies_file, "w") as f:
            json.dump(cookies, f, indent=4, ensure_ascii=False)

