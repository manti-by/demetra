import asyncio
from chimera.settings import PROJECTS_PATH
from chimera.services.linear import LinearClient
from chimera.services.opencode import OpenCodeService
from chimera.services.coderabbit import CodeRabbitService

async def main():
    print("Chimera workflow orchestrator")
    linear = LinearClient()
    opencode = OpenCodeService()
    coderabbit = CodeRabbitService()

if __name__ == "__main__":
    asyncio.run(main())
