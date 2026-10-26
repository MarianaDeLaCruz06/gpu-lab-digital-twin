"""Static guards for the Ports & Adapters dependency rule (ports-and-adapters.md, Port contracts and purity)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "gpu_lab_twin"

FRAMEWORKS = {
    "fastapi",
    "starlette",
    "pydantic",
    "pydantic_settings",
    "sqlalchemy",
    "psycopg",
    "alembic",
    "httpx",
    "uvicorn",
}
HARDWARE = {"pynvml", "kubernetes", "prometheus_client", "nvidia_smi", "dcgm"}

FORBIDDEN_IMPORTS = {
    "domain": FRAMEWORKS
    | HARDWARE
    | {
        "random",
        "gpu_lab_twin.adapters",
        "gpu_lab_twin.api",
        "gpu_lab_twin.application",
        "gpu_lab_twin.ports",
        "gpu_lab_twin.config",
        "gpu_lab_twin.bootstrap",
    },
    "ports": FRAMEWORKS | HARDWARE | {"gpu_lab_twin.adapters", "gpu_lab_twin.api", "gpu_lab_twin.bootstrap"},
    "application": FRAMEWORKS
    | HARDWARE
    | {"random", "gpu_lab_twin.adapters", "gpu_lab_twin.api", "gpu_lab_twin.bootstrap"},
}
WALL_CLOCK_CALLS = {"now", "utcnow", "today", "time", "monotonic", "sleep"}


def _modules(layer: str) -> list[Path]:
    return sorted((PACKAGE / layer).rglob("*.py"))


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _violates(name: str, forbidden: set[str]) -> bool:
    return any(name == banned or name.startswith(banned + ".") for banned in forbidden)


@pytest.mark.parametrize("layer", sorted(FORBIDDEN_IMPORTS))
def test_inner_layers_do_not_import_frameworks_or_outer_layers(layer: str) -> None:
    offenders = {
        f"{path.relative_to(PACKAGE)} imports {name}"
        for path in _modules(layer)
        for name in _imported_names(ast.parse(path.read_text(encoding="utf-8")))
        if _violates(name, FORBIDDEN_IMPORTS[layer])
    }
    assert not offenders, sorted(offenders)


@pytest.mark.parametrize("layer", ["domain", "application"])
def test_inner_layers_never_read_the_wall_clock(layer: str) -> None:
    offenders = []
    for path in _modules(layer):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in WALL_CLOCK_CALLS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"datetime", "date", "time"}
            ):
                offenders.append(f"{path.relative_to(PACKAGE)}:{node.lineno}")
    assert not offenders, offenders


def test_no_module_touches_physical_gpu_tooling() -> None:
    offenders = {
        f"{path.relative_to(PACKAGE)} imports {name}"
        for path in PACKAGE.rglob("*.py")
        for name in _imported_names(ast.parse(path.read_text(encoding="utf-8")))
        if _violates(name, HARDWARE)
    }
    assert not offenders, sorted(offenders)
