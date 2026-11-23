"""What is kept between sessions, as JSON: a file on desktop, the browser's localStorage on the web.
The best run lives here; the long-term profile (game/profile.py) uses Store."""

from pathlib import Path
import json

from game.config import WEB

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "saves" / "lockdown.json"
WEB_KEY = "brain-room-best"


def _browser_storage():
    """localStorage, reached through pygbag's bridge to the page. None outside the browser."""
    if not WEB:
        return None
    try:
        import platform
        return platform.window.localStorage
    except (ImportError, AttributeError):
        return None


class Store:
    """One JSON document kept between sessions: a file on desktop, a localStorage key in the
    browser. With no path it lives in memory only (tests, bots)."""

    def __init__(self, path: Path | None, key: str):
        self.path, self.key = path, key
        self.storage = _browser_storage() if path is not None else None

    def read(self) -> dict:
        try:
            if self.storage is not None:
                text = self.storage.getItem(self.key)
            elif self.path is not None and self.path.exists():
                text = self.path.read_text(encoding="utf-8")
            else:
                return {}
            data = json.loads(text or "{}")
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError, TypeError, AttributeError):
            return {}

    def write(self, data: dict):
        text = json.dumps(data)
        try:
            if self.storage is not None:
                self.storage.setItem(self.key, text)
            elif self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(text, encoding="utf-8")
        except (OSError, AttributeError):
            pass


class Best:
    def __init__(self, path: Path | None = DEFAULT_PATH):
        self.path = path
        self.storage = _browser_storage() if path is not None else None
        self.score = 0
        self.floor = 0
        self.room = 0
        self.won = False
        try:
            data = json.loads(self._read() or "{}")
            self.score = int(data.get("score", 0))
            self.floor, self.room = int(data.get("floor", 0)), int(data.get("room", 0))
            self.won = bool(data.get("won", False))
        except (ValueError, OSError, TypeError, AttributeError):
            pass

    def _read(self) -> str | None:
        if self.storage is not None:
            return self.storage.getItem(WEB_KEY)
        if self.path is not None and self.path.exists():
            return self.path.read_text(encoding="utf-8")
        return None

    def _write(self, text: str):
        if self.storage is not None:
            self.storage.setItem(WEB_KEY, text)
        elif self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(text, encoding="utf-8")

    def label(self) -> str:
        return f"floor {self.floor}, room {self.room}" + (", ARGUS shut down" if self.won else "")

    def record(self, score: int, floor: int, room: int, won: bool) -> bool:
        """Returns True for a new best."""
        if score <= self.score:
            return False
        self.score, self.floor, self.room, self.won = score, floor, room, won
        try:
            self._write(json.dumps({"score": score, "floor": floor, "room": room, "won": won}))
        except (OSError, AttributeError):
            pass
        return True
