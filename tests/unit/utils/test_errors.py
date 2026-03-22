import pytest
from src.utils.errors import (
    InzytsError,
    DataLoadingError,
    DataValidationError,
    CacheError,
    AnalysisError,
    LLMError,
    ConfigurationError,
)

def test_inzyts_error_basic():
    """Test basic InzytsError initialization and representation."""
    error = InzytsError("Something went wrong")
    assert error.message == "Something went wrong"
    assert error.original_error is None
    assert error.details == {}
    assert str(error) == "Something went wrong"

def test_inzyts_error_with_original_error():
    """Test InzytsError when an original exception is provided."""
    original = ValueError("Invalid value")
    error = InzytsError("Operation failed", original_error=original)
    
    assert error.message == "Operation failed"
    assert error.original_error is original
    assert str(error) == "Operation failed (Caused by: Invalid value)"

def test_inzyts_error_with_details():
    """Test InzytsError when additional details are provided."""
    details = {"file": "data.csv", "row": 5}
    error = InzytsError("Parse error", details=details)
    
    assert error.message == "Parse error"
    assert error.details == details
    assert error.details["file"] == "data.csv"

def test_derived_exceptions():
    """Test that derived exceptions inherit correctly."""
    exceptions = [
        DataLoadingError,
        DataValidationError,
        CacheError,
        AnalysisError,
        LLMError,
        ConfigurationError,
    ]
    
    for exc_class in exceptions:
        error = exc_class("Specific error occurred")
        assert isinstance(error, InzytsError)
        assert issubclass(exc_class, Exception)
        assert str(error) == "Specific error occurred"
