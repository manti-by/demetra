from fastapi import FastAPI


app: FastAPI = FastAPI(title="Demetra API")


def get_app() -> FastAPI:
    return app


def register_routes() -> None:
    from demetra.api import (
        github,  # noqa: F401
        projects,  # noqa: F401
        tickets,  # noqa: F401
        users,  # noqa: F401
        watcher,  # noqa: F401
    )


register_routes()
