from pathlib import Path

from fpga_rag.utils.hashing import compute_checksum


def test_compute_checksum(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("fpga")
    digest = compute_checksum(file_path)
    assert digest == compute_checksum(file_path)
    assert len(digest) == 64
