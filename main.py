import argparse
import asyncio
import importlib.util
import os
import sys
from pathlib import Path


def use_project_venv():
    if sys.platform == "emscripten" or importlib.util.find_spec("pygame") is not None:
        return
    venv = Path(__file__).resolve().parent / ".venv"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if python.exists() and Path(sys.prefix).resolve() != venv.resolve():
        os.execv(str(python), [str(python), *sys.argv])
    sys.exit("pygame-ce is not installed. Run:  pip install -r requirements.txt")


use_project_venv()

import pygame  # noqa: E402

from game.app import Game  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="BRAIN ROOM: they built it to obey. It learned to disagree.",
                                     epilog=f"pygame-ce {pygame.version.ver}")
    parser.add_argument("--floor", type=int, default=1, help="floor to start on (any: floors never run out)")
    parser.add_argument("--boss", action="store_true", help="go straight to ARGUS's core (floor 9)")
    parser.add_argument("--xray", action="store_true", help="start with the AI view on")
    parser.add_argument("--seed", type=int, default=None, help="random seed for a reproducible run")
    parser.add_argument("--no-sound", action="store_true", help="turn sound off")
    args = parser.parse_args()
    floor, room = (9, 4) if args.boss else (max(1, args.floor), 1)
    Game(seed=args.seed, start_floor=floor, start_room=room, xray=args.xray,
         sound=not args.no_sound).run_loop()


async def main_web():
    await Game().run_async()


if __name__ == "__main__":
    if sys.platform == "emscripten":
        asyncio.run(main_web())
    else:
        main()
