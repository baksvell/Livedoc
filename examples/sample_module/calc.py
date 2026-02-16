"""
Модуль калькулятора для демонстрации связи код ↔ документация.
"""


def add(a: int, b: int) -> int:
    """Складывает два числа."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Вычитает b из a."""
    return a - b


class Calculator:
    """Простой калькулятор."""

    def multiply(self, x: float, y: float) -> float:
        """Умножает x на y."""
        return x * y

    def divide(self, a: float, b: float) -> float:
        """Делит a на b. При b=0 бросает ZeroDivisionError."""
        return a / b
