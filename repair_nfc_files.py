from pathlib import Path
import re
import argparse
import shutil

BLOCK_RE = re.compile(r"^(Block\s+(\d+):\s*)(.*)$", re.IGNORECASE)

HEX_RE = re.compile(r"^[0-9a-fA-F]{1,2}$")


def normalize_block_line(line: str):
    """
    Returns:
        new_line: corrected line
        changed: bool
        warnings: list[str]
    """
    match = BLOCK_RE.match(line.rstrip("\n\r"))
    if not match:
        return line, False, []

    prefix = match.group(1)
    block_no = match.group(2)
    data = match.group(3).strip()

    tokens = data.split()
    warnings = []
    changed = False

    if len(tokens) != 16:
        warnings.append(
            f"Block {block_no}: expected 16 bytes, found {len(tokens)}: {tokens}"
        )
        # Do not auto-fix block length errors.
        return line, False, warnings

    normalized = []

    for token in tokens:
        if not HEX_RE.match(token):
            warnings.append(
                f"Block {block_no}: invalid hex byte '{token}'"
            )
            normalized.append(token)
            continue

        if len(token) == 1:
            normalized.append("0" + token.upper())
            changed = True
        else:
            normalized.append(token.upper())

    new_line = prefix + " ".join(normalized) + "\n"
    return new_line, changed, warnings


def process_file(path: Path, fix: bool, backup: bool):
    original = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

    new_lines = []
    changed_lines = []
    warnings = []

    for idx, line in enumerate(original, start=1):
        new_line, changed, line_warnings = normalize_block_line(line)

        if changed:
            changed_lines.append((idx, line.rstrip(), new_line.rstrip()))

        for warning in line_warnings:
            warnings.append((idx, warning))

        new_lines.append(new_line)

    if fix and changed_lines:
        if backup:
            backup_path = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup_path)

        path.write_text("".join(new_lines), encoding="utf-8")

    return changed_lines, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Scan and optionally repair Flipper Zero .nfc dumps with missing leading zeroes in block bytes."
    )

    parser.add_argument(
        "folder",
        help="Folder containing .nfc files"
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Actually write corrected files. Without this, only a dry-run scan is performed."
    )

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create .bak backup files when fixing."
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search recursively through subfolders."
    )

    args = parser.parse_args()

    root = Path(args.folder)

    if not root.exists():
        raise SystemExit(f"Folder does not exist: {root}")

    pattern = "**/*.nfc" if args.recursive else "*.nfc"
    files = sorted(root.glob(pattern))

    if not files:
        print("No .nfc files found.")
        return

    total_changed_files = 0
    total_changed_lines = 0
    total_warnings = 0

    for file in files:
        changed_lines, warnings = process_file(
            file,
            fix=args.fix,
            backup=not args.no_backup
        )

        if changed_lines or warnings:
            print()
            print(f"File: {file}")

        if changed_lines:
            total_changed_files += 1
            total_changed_lines += len(changed_lines)

            for line_no, old, new in changed_lines:
                print(f"  Line {line_no}:")
                print(f"    OLD: {old}")
                print(f"    NEW: {new}")

        if warnings:
            total_warnings += len(warnings)

            for line_no, warning in warnings:
                print(f"  WARNING line {line_no}: {warning}")

    print()
    print("Summary")
    print("-------")
    print(f"Files scanned:        {len(files)}")
    print(f"Files with changes:  {total_changed_files}")
    print(f"Corrected block rows:{total_changed_lines}")
    print(f"Warnings:            {total_warnings}")

    if not args.fix:
        print()
        print("Dry run only. Run again with --fix to write corrected files.")


if __name__ == "__main__":
    main()