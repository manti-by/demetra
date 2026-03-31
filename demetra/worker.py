from redis import Redis
from rq import Worker

from demetra.settings import REDIS_URL


connection = Redis.from_url(url=REDIS_URL)

if __name__ == "__main__":
    connection = Redis.from_url(url=REDIS_URL)
    try:
        worker = Worker(
            ["default"],
            connection=connection,
        )

        worker.work()
    except (KeyboardInterrupt, SystemExit):
        connection.close()
