"""Module containing utility functions for arithmetic operations."""

from typing import Union


def add_numbers(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """Add two numbers and return their sum.

    Args:
        a: The first number (int or float).
        b: The second number (int or float).

    Returns:
        The sum of a and b.
    """
    return a + b
