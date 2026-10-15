from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EphemeralPostgresPlan:
    """Harness design only. A later implementation supplies lifecycle/connectivity."""

    migration: Path
    image: str = "postgres:17"
    database: str = "gpu_lab_test"
    isolated_per_test: bool = True

    def assert_ready_for_implementation(self) -> None:
        assert self.migration.name == "001_gpu_lab_digital_twin_schema.sql"
        assert self.migration.exists()
