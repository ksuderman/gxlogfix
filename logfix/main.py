import argparse
import os

from logfix import *
from logfix import linter


def run(directory: str):
    files_checked = 0
    lines_patched = 0
    files_patched = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                files_checked += 1
                print(f"{files_checked:04} {file}")
                n = patch_file(f"{root}/{file}")
                if n > 0:
                    files_patched += 1
                    lines_patched += n

    print(f"Checked {files_checked} files.")
    print(f"Files   {files_patched} files.")
    print(f"Lines   {lines_patched} lines")


def main():
    parser = argparse.ArgumentParser(
        prog="gxlog",
        description="Patch greedy string interpolation in Galaxy.",
        epilog="Copyright 2023 The Galayx Project (https://galaxyproject.org)",
    )

    parser.add_argument("directory", help="the directory to scan", nargs="*")
    parser.add_argument(
        "-l",
        "--lint",
        action="store_true",
        help="only print the patches that would be applied",
        default=False,
    )
    args = parser.parse_args()
    if len(args.directory) == 0:
        parser.print_help()
        return
    dir = args.directory[0]
    if args.lint:
        linter.run(dir)
    else:
        run(dir)


if __name__ == "__main__":
    main()
