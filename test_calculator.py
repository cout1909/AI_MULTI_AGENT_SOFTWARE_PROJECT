"""Tests for the calculator module."""

import pytest
from calculator import add


def test_add_positive_integers():
    assert add(2, 3) == 5


def test_add_negative_integers():
    assert add(-2, -4) == -6


def test_add_positive_and_negative():
    assert add(5, -3) == 2


def test_add_zero():
    assert add(0, 0) == 0
    assert add(5, 0) == 5
    assert add(0, -5) == -5


def test_add_floats():
    assert add(1.5, 2.5) == 4.0
    assert add(0.1, 0.2) == pytest.approx(0.3)


def test_add_int_and_float():
    assert add(2, 3.5) == 5.5
    assert add(-2.5, 3) == 0.5
