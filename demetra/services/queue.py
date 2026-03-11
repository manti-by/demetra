from redis import Redis
from rq import Queue

from demetra.settings import REDIS_URL


queue = Queue(connection=Redis.from_url(url=REDIS_URL), default_timeout=3600)
