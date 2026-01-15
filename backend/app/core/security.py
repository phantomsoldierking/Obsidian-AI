import ipaddress
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_host = request.client.host if request.client else ""
        if not client_host:
            return JSONResponse(status_code=403, content={"detail": "Missing client host."})

        if client_host == "127.0.0.1" or client_host == "::1":
            return await call_next(request)

        try:
            ip = ipaddress.ip_address(client_host)
            if ip.is_private or ip.is_loopback:
                return await call_next(request)
        except ValueError:
            pass

        return JSONResponse(status_code=403, content={"detail": "Only local/private connections are allowed."})
