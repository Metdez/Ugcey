from fastapi import FastAPI

from ugecy.api import jobs, memories, misc, runs, threads, uploads
from ugecy.api.errors import install_error_handlers


def install_api(app: FastAPI) -> None:
    install_error_handlers(app)
    for module in (threads, runs, memories, misc, jobs, uploads):
        app.include_router(module.router)
