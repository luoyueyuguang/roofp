from __future__ import annotations

from dataclasses import dataclass, field


def _validate_positive(name: str, value: float) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")
    return float(value)


@dataclass(frozen=True)
class RoofSpec:
    label: str
    compute: float
    bandwidth: float
    color: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "compute", _validate_positive("compute", self.compute))
        object.__setattr__(
            self, "bandwidth", _validate_positive("bandwidth", self.bandwidth)
        )

    @property
    def ridge_point(self) -> float:
        return self.compute / self.bandwidth


@dataclass(frozen=True)
class OperatorPoint:
    name: str
    compute: float
    bandwidth: float
    color: str = "#1f2937"

    def __post_init__(self) -> None:
        object.__setattr__(self, "compute", _validate_positive("compute", self.compute))
        object.__setattr__(
            self, "bandwidth", _validate_positive("bandwidth", self.bandwidth)
        )

    @property
    def arithmetic_intensity(self) -> float:
        return self.compute / self.bandwidth


@dataclass(frozen=True)
class PlotRequest:
    title: str
    ideal: RoofSpec
    actual: RoofSpec | None = None
    operators: list[OperatorPoint] = field(default_factory=list)
    width: int = 1280
    height: int = 720

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")

    @property
    def roofs(self) -> list[RoofSpec]:
        roofs = [self.ideal]
        if self.actual is not None:
            roofs.append(self.actual)
        return roofs
