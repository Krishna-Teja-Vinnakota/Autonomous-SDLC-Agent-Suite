import pytest
from correct_implementation import DataValidator, MathOperations
from typing import List, Union


class TestDataValidator:
    @pytest.fixture
    def validator(self):
        return DataValidator()

    def test_should_validate_valid_email(self, validator):
        email = "test@example.com"
        assert validator.validate_email(email) is True, "Valid email should return True"

    def test_should_invalidate_invalid_email(self, validator):
        email = "invalid-email"
        assert validator.validate_email(email) is False, "Invalid email should return False"

    def test_should_invalidate_empty_email(self, validator):
        email = ""
        assert validator.validate_email(email) is False, "Empty email should return False"

    def test_should_invalidate_none_email(self, validator):
        email = None
        assert validator.validate_email(email) is False, "None email should return False"

    def test_should_invalidate_non_string_email(self, validator):
        email = 123
        assert validator.validate_email(email) is False, "Non-string email should return False"

    def test_should_validate_valid_phone(self, validator):
        phone = "123-456-7890"
        assert validator.validate_phone(phone) is True, "Valid phone should return True"

    def test_should_validate_valid_phone_no_dashes(self, validator):
        phone = "1234567890"
        assert validator.validate_phone(phone) is True, "Valid phone without dashes should return True"

    def test_should_validate_valid_phone_with_country_code(self, validator):
        phone = "11234567890"
        assert validator.validate_phone(phone) is True, "Valid phone with country code should return True"

    def test_should_invalidate_invalid_phone(self, validator):
        phone = "123-456-789"
        assert validator.validate_phone(phone) is False, "Invalid phone should return False"

    def test_should_invalidate_empty_phone(self, validator):
        phone = ""
        assert validator.validate_phone(phone) is False, "Empty phone should return False"

    def test_should_invalidate_none_phone(self, validator):
        phone = None
        assert validator.validate_phone(phone) is False, "None phone should return False"

    def test_should_invalidate_non_string_phone(self, validator):
        phone = 1234567890
        assert validator.validate_phone(phone) is False, "Non-string phone should return False"

    def test_should_increment_validation_count(self, validator):
        validator.validate_email("test@example.com")
        validator.validate_phone("123-456-7890")
        assert validator.get_validation_count() == 2, "Validation count should increment"

    def test_should_reset_validation_count(self, validator):
        validator.validate_email("test@example.com")
        validator.reset_count()
        assert validator.get_validation_count() == 0, "Validation count should reset to 0"


class TestMathOperations:
    def test_should_calculate_average_of_numbers(self):
        numbers = [1, 2, 3, 4, 5]
        assert MathOperations.calculate_average(numbers) == 3.0, "Average should be calculated correctly"

    def test_should_calculate_average_of_floats(self):
        numbers = [1.5, 2.5, 3.5]
        assert MathOperations.calculate_average(numbers) == 2.5, "Average of floats should be calculated correctly"

    def test_should_raise_value_error_for_empty_list(self):
        numbers: List[Union[int, float]] = []
        with pytest.raises(ValueError, match="Cannot calculate average of empty list"):
            MathOperations.calculate_average(numbers)

    def test_should_raise_type_error_for_non_numeric_values(self):
        numbers = [1, 2, "a", 4, 5]
        with pytest.raises(TypeError, match="All elements must be numbers"):
            MathOperations.calculate_average(numbers)

    def test_should_find_median_of_odd_length_list(self):
        numbers = [1, 3, 2, 4, 5]
        assert MathOperations.find_median(numbers) == 3, "Median should be found correctly"

    def test_should_find_median_of_even_length_list(self):
        numbers = [1, 2, 3, 4]
        assert MathOperations.find_median(numbers) == 2.5, "Median should be found correctly"

    def test_should_find_median_of_already_sorted_list(self):
        numbers = [1, 2, 3, 4, 5]
        assert MathOperations.find_median(numbers) == 3, "Median should be found correctly"

    def test_should_find_median_of_reverse_sorted_list(self):
        numbers = [5, 4, 3, 2, 1]
        assert MathOperations.find_median(numbers) == 3, "Median should be found correctly"

    def test_should_find_median_of_list_with_duplicates(self):
        numbers = [1, 2, 2, 3, 3, 3]
        assert MathOperations.find_median(numbers) == 2.5, "Median should be found correctly"

    def test_should_raise_value_error_for_empty_list_median(self):
        numbers: List[Union[int, float]] = []
        with pytest.raises(ValueError, match="Cannot calculate median of empty list"):
            MathOperations.find_median(numbers)

    def test_should_raise_type_error_for_non_numeric_values_median(self):
        numbers = [1, 2, "a", 4, 5]
        with pytest.raises(TypeError, match="All elements must be numbers"):
            MathOperations.find_median(numbers)