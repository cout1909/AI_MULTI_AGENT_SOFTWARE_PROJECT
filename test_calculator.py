import pytest
from calculator import add

def test_add_integers():
    assert add(1, 2) == 3
    assert add(-1, 1) == 0
    assert add(-5, -5) == -10
    assert add(0, 0) == 0

def test_add_floats():
    assert add(1.5, 2.5) == 4.0
    assert add(-1.5, 2.5) == 1.0
    assert add(-1.5, -2.5) == -4.0
    assert add(0.0, 0.0) == 0.0

def test_add_mixed_int_and_float():
    assert add(1, 2.5) == 3.5
    assert add(2.5, 1) == 3.5
    assert add(-5, 2.5) == -2.5

def test_add_large_numbers():
    assert add(10**12, 10**12) == 2 * 10**12
    assert add(1e10, 1e10) == 2e10

def test_add_float_precision():
    assert add(0.1, 0.2) == pytest.approx(0.3)
