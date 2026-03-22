"""
Unit tests for file_utils module.

Tests robust CSV loading with automatic delimiter detection,
multi-encoding fallback, and edge case handling.
"""

import pytest

from src.utils.file_utils import detect_csv_dialect, load_csv_robust


class TestDetectCSVDialect:
    """Test suite for CSV dialect detection."""

    def test_detect_comma_delimiter(self, tmp_path):
        """Test detection of comma-delimited CSV."""
        csv_path = tmp_path / "comma.csv"
        csv_path.write_text("a,b,c\n1,2,3\n4,5,6\n")

        delimiter, quotechar = detect_csv_dialect(str(csv_path))

        assert delimiter == ","

    def test_detect_semicolon_delimiter(self, tmp_path):
        """Test detection of semicolon-delimited CSV."""
        csv_path = tmp_path / "semicolon.csv"
        csv_path.write_text("a;b;c\n1;2;3\n4;5;6\n")

        delimiter, quotechar = detect_csv_dialect(str(csv_path))

        assert delimiter == ";"

    def test_detect_tab_delimiter(self, tmp_path):
        """Test detection of tab-delimited CSV."""
        csv_path = tmp_path / "tab.csv"
        csv_path.write_text("a\tb\tc\n1\t2\t3\n4\t5\t6\n")

        delimiter, quotechar = detect_csv_dialect(str(csv_path))

        assert delimiter == "\t"

    def test_detect_pipe_delimiter(self, tmp_path):
        """Test detection of pipe-delimited CSV."""
        csv_path = tmp_path / "pipe.csv"
        csv_path.write_text("a|b|c\n1|2|3\n4|5|6\n")

        delimiter, quotechar = detect_csv_dialect(str(csv_path))

        assert delimiter == "|"

    def test_nonexistent_file(self):
        """Test handling of non-existent file."""
        delimiter, quotechar = detect_csv_dialect("/nonexistent/path.csv")

        assert delimiter is None
        assert quotechar is None

    def test_empty_file(self, tmp_path):
        """Test handling of empty file."""
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("")

        delimiter, quotechar = detect_csv_dialect(str(csv_path))

        assert delimiter is None
        assert quotechar is None


class TestLoadCSVRobust:
    """Test suite for robust CSV loading."""

    def test_load_comma_csv(self, tmp_path):
        """Test loading standard comma-delimited CSV."""
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n")

        df = load_csv_robust(str(csv_path))

        assert len(df) == 2
        assert list(df.columns) == ["name", "age", "city"]
        assert df.iloc[0]["name"] == "Alice"

    def test_load_semicolon_csv(self, tmp_path):
        """Test loading semicolon-delimited CSV."""
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("name;age;city\nAlice;30;NYC\nBob;25;LA\n")

        df = load_csv_robust(str(csv_path))

        assert len(df) == 2
        assert list(df.columns) == ["name", "age", "city"]

    def test_load_tab_csv(self, tmp_path):
        """Test loading tab-delimited CSV."""
        csv_path = tmp_path / "data.tsv"
        csv_path.write_text("name\tage\tcity\nAlice\t30\tNYC\nBob\t25\tLA\n")

        df = load_csv_robust(str(csv_path))

        assert len(df) == 2
        assert list(df.columns) == ["name", "age", "city"]

    def test_load_with_nrows(self, tmp_path):
        """Test loading with nrows parameter."""
        csv_path = tmp_path / "data.csv"
        lines = ["id,val\n"] + [f"{i},{i*10}\n" for i in range(100)]
        csv_path.write_text("".join(lines))

        df = load_csv_robust(str(csv_path), nrows=5)

        assert len(df) == 5

    def test_load_latin1_encoding(self, tmp_path):
        """Test loading file with latin-1 encoding."""
        csv_path = tmp_path / "latin1.csv"
        content = "name,city\nJosé,São Paulo\nMüller,München\n"
        csv_path.write_bytes(content.encode("latin-1"))

        df = load_csv_robust(str(csv_path))

        assert len(df) == 2
        assert "José" in df["name"].values

    def test_load_utf8_bom(self, tmp_path):
        """Test loading file with UTF-8 BOM encoding."""
        csv_path = tmp_path / "bom.csv"
        content = "name,age\nAlice,30\nBob,25\n"
        csv_path.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

        df = load_csv_robust(str(csv_path))

        assert len(df) == 2
        assert "name" in df.columns

    def test_explicit_sep_override(self, tmp_path):
        """Test that explicit sep parameter overrides auto-detection."""
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("a|b|c\n1|2|3\n")

        df = load_csv_robust(str(csv_path), sep="|")

        assert list(df.columns) == ["a", "b", "c"]

    def test_load_nonexistent_file_raises(self):
        """Test that loading non-existent file raises an error."""
        with pytest.raises((FileNotFoundError, ValueError)):
            load_csv_robust("/nonexistent/path.csv")

    def test_load_with_quoted_fields(self, tmp_path):
        """Test loading CSV with quoted fields containing delimiters."""
        csv_path = tmp_path / "quoted.csv"
        csv_path.write_text('name,description\nAlice,"Has, commas"\nBob,"No commas"\n')

        df = load_csv_robust(str(csv_path))

        assert len(df) == 2
        assert "Has, commas" in df["description"].values

    def test_load_with_missing_values(self, tmp_path):
        """Test loading CSV with missing values."""
        csv_path = tmp_path / "missing.csv"
        csv_path.write_text("a,b,c\n1,,3\n,5,\n7,8,9\n")

        df = load_csv_robust(str(csv_path))

        assert len(df) == 3
        assert df.isnull().sum().sum() == 3
