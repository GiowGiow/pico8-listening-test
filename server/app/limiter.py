from flask import request
from flask_limiter import Limiter


def client_ip():
    # External traffic always comes through Cloudflare, which overwrites
    # CF-Connecting-IP with the real client address. Inside the LAN the header
    # is absent and the peer address (Traefik) is used instead.
    return request.headers.get("CF-Connecting-IP", "").strip() or request.remote_addr or "unknown"


limiter = Limiter(key_func=client_ip, default_limits=["300/minute"])
