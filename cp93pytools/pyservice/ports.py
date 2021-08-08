import socket
from contextlib import closing


# https://stackoverflow.com/a/52872579/3671939
def is_port_in_use(port: int):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        return s.connect_ex(('localhost', port)) == 0


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def find_free_port(preferred_port: int = None) -> int:
    port = preferred_port
    while port is None or is_port_in_use(port):
        port = _find_free_port()
    return port