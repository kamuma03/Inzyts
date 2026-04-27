"""Unit tests for the CSV hashing helper used by previous-job lookup."""

from pathlib import Path

from src.server.services.csv_hashing import hash_csv_file


def test_returns_none_for_empty_path():
    assert hash_csv_file("") is None
    assert hash_csv_file(None) is None  # type: ignore[arg-type]


def test_returns_none_for_missing_file(tmp_path: Path):
    assert hash_csv_file(tmp_path / "nope.csv") is None


def test_hash_is_stable_for_same_content(tmp_path: Path):
    f = tmp_path / "a.csv"
    f.write_text("col_a,col_b\n1,2\n3,4\n")
    h1 = hash_csv_file(f)
    h2 = hash_csv_file(f)
    assert h1 is not None
    assert h1 == h2
    # sha256 hex digest is 64 chars
    assert len(h1) == 64


def test_different_content_different_hash(tmp_path: Path):
    f1 = tmp_path / "a.csv"
    f2 = tmp_path / "b.csv"
    f1.write_text("col_a,col_b\n1,2\n")
    f2.write_text("col_a,col_b\n9,9\n")
    assert hash_csv_file(f1) != hash_csv_file(f2)


def test_handles_large_file_in_chunks(tmp_path: Path):
    # Larger than the 64 KiB chunk size — exercises the streaming loop.
    f = tmp_path / "big.csv"
    f.write_text("col\n" + ("0," * 50_000) + "\n")
    h = hash_csv_file(f)
    assert h is not None and len(h) == 64
