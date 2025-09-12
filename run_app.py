import asyncio
import socket
import webbrowser
from contextlib import closing

import uvicorn
import app.main as main_app


def _find_free_port(preferred: int = 8000) -> int:
	# Try preferred, else let OS choose
	with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
		try:
			s.bind(("127.0.0.1", preferred))
			return preferred
		except OSError:
			pass
	with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
		s.bind(("127.0.0.1", 0))
		return s.getsockname()[1]


async def _open_browser_after_delay(url: str, delay_seconds: float = 0.8) -> None:
	await asyncio.sleep(delay_seconds)
	webbrowser.open(url)


async def _serve() -> None:
	port = _find_free_port(8000)
	url = f"http://127.0.0.1:{port}"
	asyncio.create_task(_open_browser_after_delay(url))
	config = uvicorn.Config(app=main_app.app, host="127.0.0.1", port=port, log_level="info")
	server = uvicorn.Server(config)
	await server.serve()


def main() -> None:
	asyncio.run(_serve())


if __name__ == "__main__":
	main()


