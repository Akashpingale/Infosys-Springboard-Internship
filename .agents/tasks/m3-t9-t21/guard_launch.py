import runpy
import socket
import sys

LOCAL = {"127.0.0.1", "::1", "localhost"}
real_connect = socket.socket.connect
real_getaddrinfo = socket.getaddrinfo


def guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else address
    if host not in LOCAL:
        raise RuntimeError(f"review guard: network blocked ({host})")
    return real_connect(self, address)


def guarded_getaddrinfo(host, *args, **kwargs):
    if host not in LOCAL and host is not None:
        raise RuntimeError(f"review guard: name lookup blocked ({host})")
    return real_getaddrinfo(host, *args, **kwargs)


socket.socket.connect = guarded_connect
socket.getaddrinfo = guarded_getaddrinfo

script = sys.argv[1]
sys.argv = [script, *sys.argv[2:]]
runpy.run_path(script, run_name="__main__")
