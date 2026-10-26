from __future__ import annotations

from fastapi import Request

from gpu_lab_twin.bootstrap import Container


def get_container(request: Request) -> Container:
    return request.app.state.container
