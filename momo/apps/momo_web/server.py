from __future__ import annotations

import os
from pathlib import Path

from ...config import load_config
from . import create_app


def main() -> None:
    cfg_path = Path(os.environ.get("MOMO_CONFIG", "configs/momo.yml")).expanduser()
    cfg = load_config(cfg_path)
    app = create_app(cfg)
    app.run(host=cfg.web.bind_host, port=cfg.web.bind_port)


if __name__ == "__main__":
    main()


