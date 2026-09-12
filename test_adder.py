"""Unit tests for adder.py."""

import pytest
from adder import add_numbers


def test_add_positive_integers():
    """Test adding two positive integers."""
    assert add_numbers(2, 3) == 5


def test_add_negative_integers():
    """Test adding two negative integers."""
    assert add_numbers(-2, -3) == -5


def test_add_mixed_sign_integers():
    """Test adding a positive integer and a negative integer."""
    assert add_numbers(5, -3) == 2
    assert add_numbers(-5, 3) == -2


def test_add_zero():
    """Test adding zero to an integer/float."""
    assert add_numbers(0, 5) == 5
    assert add_numbers(5, 0) == 5
    assert add_numbers(0, 0) == 0


def test_add_floats():
    """Test adding floating-point numbers."""
    assert add_numbers(2.5, 3.5) == 6.0
    assert add_numbers(0.1, 0.2) == pytest.approx(0.3)


def test_add_int_and_float():
    """Test adding an integer and a float."""
    assert add_numbers(2, 3.5) == 5.5
    assert add_numbers(2.5, 3) == 5.5


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (10, 20, 30),
        (-10, -20, -30),
        (-10, 20, 10),
        (0.5, 0.25, 0.75),
        (-0.5, 0.5, 0.0),
        (1000000, 2000000, 3000000),
    ],
)
def test_add_numbers_parametrized(a, b, expected):
    """Parametrized test for add_numbers with various numeric inputs."""
    assert add_numbers(a, b) == pytest.approx(expected)
