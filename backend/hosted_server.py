"""Run the existing simulator as the authenticated origin behind ChatGPT Sites.

AWS credentials come from the EC2 instance role. The origin secret is fetched
from Parameter Store at startup and remains in process memory.
"""
import hmac
import os

import boto3
import uvicorn
from starlette.responses import JSONResponse


class PrivateOrigin:
    def __init__(self, app, secret):
        self.app = app
        self.secret = secret.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        supplied = headers.get(b"x-last-warning-key", b"")
        if not hmac.compare_digest(supplied, self.secret):
            return await JSONResponse({"detail": "Authentication required"}, status_code=401)(scope, receive, send)
        path = scope["path"]
        if not path.startswith("/api/") or path.startswith(("/api/neural", "/api/stimuli")):
            return await JSONResponse({"detail": "Not found"}, status_code=404)(scope, receive, send)
        await self.app(scope, receive, send)


def main():
    os.environ["LAST_WARNING_ALLOW_INSTANCE_ROLE"] = "1"
    os.environ["LAST_WARNING_NEURAL_INFERENCE"] = "0"
    region = os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")
    parameter = os.environ.get("LAST_WARNING_SECRET_PARAMETER", "/last-warning/sites/origin-secret")
    secret = boto3.client("ssm", region_name=region).get_parameter(Name=parameter, WithDecryption=True)["Parameter"]["Value"]
    if len(secret) < 32:
        raise RuntimeError("Origin secret is invalid")
    from backend.app.main import app

    uvicorn.run(PrivateOrigin(app, secret), host="127.0.0.1", port=8000, proxy_headers=False)


if __name__ == "__main__":
    main()
