"""Simple Calculator Module"""
from typing import List, Tuple, Any, Dict


class Calculator:
    """A simple calculator with known bugs."""

    def __init__(self):
        self._stats = {"total": 0, "success": 0, "failed": 0}

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    def subtract(self, a: float, b: float) -> float:
        """Subtract b from a."""
        return a - b

    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b

    def divide(self, a: float, b: float) -> float:
        """Divide a by b."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    def power(self, base: float, exp: float) -> float:
        """Raise base to exp."""
        return base ** exp

    def factorial(self, n: int) -> int:
        """Calculate factorial."""
        if n < 0:
            raise ValueError("Factorial is not defined for negative numbers")
        if n > 20:
            raise OverflowError("Input too large for factorial calculation")
        if n == 0:
            return 1
        result = 1
        for i in range(1, n + 1):
            result *= i
        return result

    def batch_operation(
        self, operations: List[Tuple[str, ...]]
    ) -> List[Any]:
        """Run a batch of operations. Returns list of results."""
        results = []
        for op in operations:
            name = op[0]
            args = op[1:]
            method = getattr(self, name, None)
            if method is None:
                self._stats["total"] += 1
                self._stats["failed"] += 1
                results.append({"error": f"Unknown operation: {name}"})
                continue
            try:
                result = method(*args)
                self._stats["total"] += 1
                self._stats["success"] += 1
                results.append(result)
            except Exception as e:
                self._stats["total"] += 1
                self._stats["failed"] += 1
                results.append({"error": str(e)})
        return results

    def get_stats(self) -> Dict[str, int]:
        """Return operation statistics."""
        return self._stats.copy()
