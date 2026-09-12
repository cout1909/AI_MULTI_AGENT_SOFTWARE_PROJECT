import pytest
from adder import add_numbers


def test_add_positive_numbers():
    assert add_numbers(2, 3) == 5


def test_add_negative_numbers():
    assert add_numbers(-2, -3) == -5


def test_add_mixed_sign_numbers():
    assert add_numbers(5, -3) == 2
    assert add_numbers(-5, 3) == -2


def test_add_zero():
    assert add_numbers(0, 5) == 5
    assert add_numbers(5, 0) == 5
    assert add_numbers(0, 0) == 0


def test_add_floats():
    assert add_numbers(1.5, 2.5) == 4.0
    assert add_numbers(0.1, 0.2) == pytest.approx(0.3)
