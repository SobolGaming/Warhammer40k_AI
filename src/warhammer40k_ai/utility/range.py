from dataclasses import dataclass
from typing import Union


@dataclass
class Range:
    min: int
    max: int

    def __post_init__(self):
        if self.min > self.max:
            raise ValueError("min value cannot be greater than max value")

    @classmethod
    def from_string(cls, string: str) -> 'Range':
        parts = string.split("-")
        if len(parts) == 1:
            value = int(parts[0].strip())
            return cls(min=value, max=value)
        elif len(parts) == 2:
            return cls(min=int(parts[0].strip()), max=int(parts[1].strip()))
        else:
            raise ValueError("Invalid range format. Use 'n' or 'min-max'")

    def __contains__(self, value: Union[int, 'Range']) -> bool:
        if isinstance(value, int):
            return self.min <= value <= self.max
        elif isinstance(value, Range):
            return self.min <= value.min and value.max <= self.max
        else:
            return False

    def __str__(self) -> str:
        return f"{self.min}-{self.max}" if self.min != self.max else str(self.min)

    def is_above(self, value: int) -> bool:
        return value > self.max