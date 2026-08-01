from __future__ import annotations

import uvicorn

from src.backend.api import create_app
from src.backend.bootstrap import build_backend_container


if __name__ == "__main__":
    uvicorn.run(create_app(build_backend_container()), host="127.0.0.1", port=8000)
