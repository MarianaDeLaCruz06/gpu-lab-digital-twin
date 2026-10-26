"""ASGI entry point: `uvicorn gpu_lab_twin.main:app`."""

from gpu_lab_twin.api.app import create_app

app = create_app()
