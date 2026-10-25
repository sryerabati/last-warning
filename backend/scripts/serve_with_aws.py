#!/usr/bin/env python3
"""Run the local simulator with a temporary AWS session held only in process memory."""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path


def main():
    import boto3
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-parts", type=int, default=0,
                        help="Read a JSON SDK credential dictionary in this many hidden input parts")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Reload local backend source during development")
    args = parser.parse_args()
    if not 0 <= args.credential_parts <= 10 or not 1024 <= args.port <= 65535:
        parser.error("Use 0–10 credential parts and a port between 1024 and 65535")
    if args.credential_parts:
        values = json.loads("".join(getpass.getpass("AWS session part (hidden): ")
                                   for _ in range(args.credential_parts)))
        fields = {"aws_access_key_id": "AWS_ACCESS_KEY_ID", "aws_secret_access_key": "AWS_SECRET_ACCESS_KEY",
                  "aws_session_token": "AWS_SESSION_TOKEN"}
        if set(values) != set(fields) or not all(isinstance(v, str) and v for v in values.values()):
            raise ValueError("Provide exactly the three AWS session credential fields")
        for key, name in fields.items():
            os.environ[name] = values[key]
        values.clear()
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")
    os.environ.setdefault("AWS_EC2_METADATA_DISABLED", "true")
    boto3.Session().client("sts").get_caller_identity()
    print("AWS authentication verified. Starting the local simulator.", flush=True)
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=args.port, reload=args.reload,
                reload_dirs=[str(root / "backend" / "app")] if args.reload else None)


if __name__ == "__main__":
    main()
