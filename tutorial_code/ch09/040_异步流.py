import asyncio

async def main():
    async for chunk in agent.astream(
        {"messages": [...]},
        stream_mode="updates"
    ):
        print(chunk)

asyncio.run(main())