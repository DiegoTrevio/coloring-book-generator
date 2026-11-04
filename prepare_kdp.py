#!/usr/bin/env python3
"""
prepare_kdp.py  —  Build a complete KDP upload package from one (or all) book MD files.

Usage:
    python prepare_kdp.py                           # process every .md in D:\KPD\books\
    python prepare_kdp.py "D:\KPD\books\book.md"   # process one book
    python prepare_kdp.py --only-pdf                # rebuild PDFs only (no API calls)
    python prepare_kdp.py --only-cover              # regenerate covers only
"""
import subprocess
import sys
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
BOOKS_DIR   = Path(r"D:\KPD\books")
OUT_DIR     = Path(r"D:\KPD")
BUILDER     = Path(__file__).parent / "kdp_book_builder.py"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(md: Path, extra_flags: list[str]) -> bool:
    cmd = [
        sys.executable, str(BUILDER),
        str(md),
        "--out", str(OUT_DIR),
        "--yes",
        *extra_flags,
    ]
    print(f"\n{'='*60}")
    print(f"  Book: {md.stem}")
    print(f"{'='*60}")
    result = subprocess.run(cmd)
    return result.returncode == 0


def _summary(md: Path) -> None:
    """Print the files to upload for this book."""
    book_dir = OUT_DIR / _book_folder(md)
    if not book_dir.exists():
        return

    interior = next(book_dir.glob("interior/*.pdf"), None)
    front    = book_dir / "cover" / "front.png"
    back     = book_dir / "cover" / "back.png"
    combined = book_dir / "cover" / "cover_combined.png"
    details  = book_dir / "upload_details.txt"

    print(f"\n  📂 Output: {book_dir}")
    print(f"  {'✓' if interior and interior.exists() else '✗'} Interior PDF : "
          f"{interior.name if interior else 'NOT FOUND'}")
    print(f"  {'✓' if front.exists() else '✗'} Front cover  : cover/front.png")
    print(f"  {'✓' if back.exists() else '✗'} Back cover   : cover/back.png")
    if combined.exists():
        print(f"  ✓ Combined   : cover/cover_combined.png")
    print(f"  {'✓' if details.exists() else '✗'} Upload info  : upload_details.txt")

    if interior and interior.exists():
        print(f"\n  ➜ KDP manuscript to upload:")
        print(f"    {interior}")
    print()


def _book_folder(md: Path) -> str:
    """Guess the output folder name for this MD (same logic as cli.py)."""
    from kdp.parser import parse_book
    from kdp.utils import sanitize_folder_name
    try:
        book = parse_book(md)
        return sanitize_folder_name(book.book_title)
    except Exception:
        return md.stem


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    # Pull out mode flags
    extra = []
    md_files: list[Path] = []
    for a in args:
        if a.startswith("--"):
            extra.append(a)
        else:
            md_files.append(Path(a))

    # Default: all .md files in BOOKS_DIR
    if not md_files:
        md_files = sorted(BOOKS_DIR.glob("*.md"))
        if not md_files:
            sys.exit(f"No .md files found in {BOOKS_DIR}")

    results: list[tuple[Path, bool]] = []
    for md in md_files:
        if not md.exists():
            print(f"⚠  File not found: {md}")
            results.append((md, False))
            continue

        ok = _run(md, extra)
        _summary(md)
        results.append((md, ok))

    # Final report
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    for md, ok in results:
        icon = "✓" if ok else "✗"
        print(f"  {icon}  {md.stem}")
    print()


if __name__ == "__main__":
    main()
