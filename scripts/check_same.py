"""Check that a code change left the results unchanged.

Runs metrics.py and report.py on the saved data in data/, with the clock fixed,
for several report ranges, and compares everything they produce (results files,
HTML pages and console lines) with a saved reference.

Usage (from the repo folder):
  python scripts/check_same.py save       before changing the code
  python scripts/check_same.py compare    after each change

The reference goes to output/check-reference/ (output/ is never committed).
Covers metrics.py and report.py only: fetch.py calls GitHub and is checked by hand.
Does not change data/ or any script. Exit codes: 0 same, 1 different, 2 setup problem.
"""

import contextlib
import filecmp
import importlib.util
import io
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REFERENCE = Path("output/check-reference")
FIXED_NOW = datetime(2026, 11, 17, 0, 0, tzinfo=timezone.utc)  # after the saved data
RANGES = {
    "default": [],
    "since-start": ["--since-start"],
    "last-3-months": ["--last", "3 months"],
    "dates": ["--from", "2026-11-02", "--to", "2026-11-15"],
}


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW.astimezone(tz) if tz else FIXED_NOW


def run_script(name, argv):
    """Run scripts/<name>.py with the given arguments and a fixed clock; return its console output."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "datetime"):
        module.datetime = FixedClock
    out = io.StringIO()
    sys.argv = [f"{name}.py", *argv]
    with contextlib.redirect_stdout(out):
        module.main()
    return out.getvalue()


def produce(target):
    """Write every range's results, pages and console lines under target/<range>/."""
    for label, argv in RANGES.items():
        folder = target / label
        console = run_script("metrics", [*argv, "--out-dir", str(folder)])
        run_dir = next(p for p in folder.iterdir() if p.is_dir())
        console += run_script("report", [str(run_dir)])
        for spelling in (folder.as_posix(), str(folder)):  # same text wherever the output went
            console = console.replace(spelling, "<output>")
        (folder / "console.txt").write_text(console, encoding="utf-8")


def differences(a, b):
    """Paths of files that are missing on one side or differ in content."""
    cmp = filecmp.dircmp(a, b)
    found = [str(Path(a, n)) for n in cmp.left_only + cmp.right_only + cmp.diff_files + cmp.funny_files]
    for sub in cmp.common_dirs:
        found += differences(Path(a, sub), Path(b, sub))
    return found


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("save", "compare"):
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    if sys.argv[1] == "save":
        shutil.rmtree(REFERENCE, ignore_errors=True)
        produce(REFERENCE)
        print(f"Reference saved to {REFERENCE.as_posix()}")
        return
    if not REFERENCE.exists():
        print("No reference yet. Run: python scripts/check_same.py save", file=sys.stderr)
        sys.exit(2)
    with tempfile.TemporaryDirectory() as tmp:
        produce(Path(tmp))
        changed = differences(REFERENCE, Path(tmp))
    if changed:
        print("DIFFERENT from the reference:")
        for path in changed:
            print(f"  {path}")
        sys.exit(1)
    print("SAME: results, pages and console lines match the reference.")


if __name__ == "__main__":
    main()
