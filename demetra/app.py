from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from demetra.api.auth import router as auth_router
from demetra.api.github import router as github_router
from demetra.api.projects import router as projects_router
from demetra.api.sessions import router as sessions_router
from demetra.api.users import router as users_router
from demetra.api.watcher import router as watcher_router
from demetra.api.webhooks import router as webhooks_router
from demetra.settings import CORS_ALLOWED_ORIGINS


app = FastAPI(title="Demetra API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth_router)
app.include_router(github_router)
app.include_router(projects_router)
app.include_router(sessions_router)
app.include_router(users_router)
app.include_router(watcher_router)
app.include_router(webhooks_router)
