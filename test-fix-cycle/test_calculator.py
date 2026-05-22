"""Tests for Calculator - expects correct error handling."""
import pytest
from calculator import Calculator


@pytest.fixture
def calc():
    return Calculator()


class TestBasicOperations:
    def test_add(self, calc):
        assert calc.add(2, 3) == 5

    def test_subtract(self, calc):
        assert calc.subtract(5, 3) == 2

    def test_multiply(self, calc):
        assert calc.multiply(3, 4) == 12

    def test_divide(self, calc):
        assert calc.divide(10, 2) == 5.0


class TestDivisionEdgeCases:
    def test_divide_by_zero_raises_value_error(self, calc):
        """divide(10, 0) should raise ValueError, not ZeroDivisionError."""
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            calc.divide(10, 0)

    def test_divide_by_zero_message(self, calc):
        """Error message should be specific."""
        try:
            calc.divide(10, 0)
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            assert "Cannot divide by zero" in str(e)


class TestFactorial:
    def test_factorial_0(self, calc):
        assert calc.factorial(0) == 1

    def test_factorial_1(self, calc):
        assert calc.factorial(1) == 1

    def test_factorial_5(self, calc):
        assert calc.factorial(5) == 120

    def test_factorial_negative_raises_value_error(self, calc):
        """factorial(-1) should raise ValueError."""
        with pytest.raises(ValueError, match="negative"):
            calc.factorial(-1)

    def test_factorial_large_raises_overflow_error(self, calc):
        """factorial(21) should raise OverflowError."""
        with pytest.raises(OverflowError, match="too large"):
            calc.factorial(21)

    def test_factorial_20(self, calc):
        """factorial(20) should work (boundary)."""
        assert calc.factorial(20) == 2432902008176640000


class TestPower:
    def test_power(self, calc):
        assert calc.power(2, 3) == 8

    def test_power_zero_exp(self, calc):
        assert calc.power(5, 0) == 1.0


class TestBatchOperation:
    def test_batch_add_multiply(self, calc):
        results = calc.batch_operation([
            ("add", 1, 2),
            ("multiply", 3, 4),
        ])
        assert results == [3, 12]

    def test_batch_with_unknown_op(self, calc):
        results = calc.batch_operation([("unknown", 1, 2)])
        assert "error" in results[0]


class TestStats:
    def test_initial_stats(self, calc):
        stats = calc.get_stats()
        assert stats == {"total": 0, "success": 0, "failed": 0}

    def test_stats_after_operations(self, calc):
        calc.add(1, 2)
        calc.batch_operation([("add", 3, 4)])
        stats = calc.get_stats()
        assert stats["total"] >= 1
        assert stats["success"] >= 1
