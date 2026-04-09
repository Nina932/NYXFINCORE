import socket
import asyncio

async def test_resolve():
    host = "ep-raspy-water-agnr9eff-pooler.c-2.eu-central-1.aws.neon.tech"
    print(f"Testing resolution of: {host}")
    try:
        # Standard socket resolution
        addr_info = socket.getaddrinfo(host, 5432)
        print("Success: socket.getaddrinfo resolved the host.")
        for info in addr_info:
            print(f" - {info[4]}")
            
        # Asyncio resolution (closer to what asyncpg does)
        loop = asyncio.get_event_loop()
        res = await loop.getaddrinfo(host, 5432)
        print("Success: loop.getaddrinfo resolved the host.")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_resolve())
