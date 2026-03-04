from redis import Redis
from rq import Worker

from demetra.settings import REDIS_URL


worker = Worker(["default"], connection=Redis.from_url(url=REDIS_URL))
worker.work()
