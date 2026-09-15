"""Unit tests for the calculator module using pytest."""

import pytest
from calculator import add


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1, 2, 3),
        (-1, -2, -3),
        (-1, 5, 4),
        (0, 0, 0),
        (0, 5, 5),
        (-5, 0, -5),
        (1000000, 2000000, 3000000),
    ],
)
def test_add_integers(a: int, b: int, expected: int) -> None:
    """Test addition with integer inputs."""
    assert add(a, b) == expected


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1.5, 2.5, 4.0),
        (-1.5, -2.5, -4.0),
        (-1.5, 2.5, 1.0),
        (0.0, 0.0, 0.0),
        (0.1, 0.2, 0.3),
    ],
)
def test_add_floats(a: float, b: float, expected: float) -> None:
    """Test addition with float inputs."""
    assert add(a, b) == pytest.approx(expected)


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1, 2.5, 3.5),
        (2.5, 1, 3.5),
        (-1, 2.5, 1.5),
        (0, 3.14, 3.14),
    ],
)
def test_add_mixed_types(a: float | int, b: float | int, expected: float | int) -> None:
    """Test addition with mixed integer and float inputs."""
    assert add(a, b) == pytest.approx(expected)
