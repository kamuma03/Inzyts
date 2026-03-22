import pytest
import os
import pandas as pd
from unittest.mock import patch, mock_open
from src.utils.file_utils import detect_csv_dialect, load_csv_robust

def test_detect_csv_dialect_success(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("col1|col2\n\"val1\"|\"val2\"\n\"val3\"|\"val4\"")
    
    delimiter, quotechar = detect_csv_dialect(str(csv_file))
    assert delimiter == "|"
    assert quotechar == '"'

def test_detect_csv_dialect_not_found():
    delimiter, quotechar = detect_csv_dialect("nonexistent.csv")
    assert delimiter is None
    assert quotechar is None

def test_detect_csv_dialect_empty_file(tmp_path):
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("")
    
    delimiter, quotechar = detect_csv_dialect(str(csv_file))
    assert delimiter is None
    assert quotechar is None

def test_detect_csv_dialect_sniffer_error(tmp_path):
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("word1\nword2\nword3")
    
    with patch("src.utils.file_utils.csv.Sniffer.sniff", side_effect=ValueError("Sniffer failed")):
        delimiter, quotechar = detect_csv_dialect(str(csv_file))
        assert delimiter is None
        assert quotechar is None

@patch("src.utils.file_utils.open", side_effect=Exception("Read error"))
def test_detect_csv_dialect_exception(mock_open, tmp_path):
    csv_file = tmp_path / "error.csv"
    csv_file.touch() # file needs to exist to get past os.path.exists
    
    delimiter, quotechar = detect_csv_dialect(str(csv_file))
    assert delimiter is None
    assert quotechar is None

def test_load_csv_robust_success(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("A,B\n1,2\n3,4")
    
    df = load_csv_robust(str(csv_file))
    assert list(df.columns) == ["A", "B"]
    assert len(df) == 2

def test_load_csv_robust_explicit_kwargs(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("A|B\n1|2")
    
    df = load_csv_robust(str(csv_file), sep="|")
    assert list(df.columns) == ["A", "B"]
    assert len(df) == 1

def test_load_csv_robust_semicolon_fallback(tmp_path):
    csv_file = tmp_path / "semi.csv"
    csv_file.write_text("A;B\n1;2")
    
    with patch("src.utils.file_utils.detect_csv_dialect", return_value=(None, None)):
        df = load_csv_robust(str(csv_file))
        assert list(df.columns) == ["A", "B"] # Fallback found ";"

def test_load_csv_robust_python_engine_fallback(tmp_path):
    csv_file = tmp_path / "fallback.csv"
    csv_file.write_text("A,B\n1,2")
    
    original_read = pd.read_csv
    
    def side_effect(*args, **kwargs):
        if "engine" not in kwargs or kwargs["engine"] != "python":
            raise pd.errors.ParserError("First try failed")
        return original_read(*args, **kwargs)
        
    with patch("src.utils.file_utils.pd.read_csv", side_effect=side_effect):
        df = load_csv_robust(str(csv_file))
        assert list(df.columns) == ["A", "B"]

def test_load_csv_robust_complete_failure(tmp_path):
    csv_file = tmp_path / "broken.csv"
    csv_file.write_text("A,B\n1,2")
    
    original_read = pd.read_csv
    
    def side_effect(*args, **kwargs):
        if "engine" not in kwargs or kwargs["engine"] != "python":
            raise pd.errors.ParserError("First try failed")
        raise Exception("Final try failed")
        
    with patch("src.utils.file_utils.pd.read_csv", side_effect=side_effect):
        with pytest.raises(ValueError) as exc:
            load_csv_robust(str(csv_file))
        assert "Failed to load CSV" in str(exc.value)

def test_load_csv_robust_generic_exception(tmp_path):
    # Tests line 147 where generic Exceptions are re-raised inside retry loop
    csv_file = tmp_path / "broken.csv"
    csv_file.write_text("A,B\n1,2")
    
    # Not a ParserError/EmptyDataError, just a generic Exception during the first read loop
    with patch("src.utils.file_utils.pd.read_csv", side_effect=RuntimeError("Generic error")):
        with pytest.raises(RuntimeError) as exc:
            load_csv_robust(str(csv_file))
        assert "Generic error" in str(exc.value)
