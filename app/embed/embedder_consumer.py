import os
import asyncio

async def main() -> None:
    provider = os.getenv("EMBED_PROVIDER", "tei").strip().lower()

    if provider == "stub":
        from app.embed.stub_embedder_consumer import main as run
    else:
        from app.embed.tei_embedder_consumer import main as run

    await run()


if __name__ == "__main__":
    asyncio.run(main())
