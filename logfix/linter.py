import argparse
import os

from logfix import *


def print_patches(filepath: str, patches: dict, source: str):
    if len(patches) == 0:
        return
    print(filepath)
    lines = source.splitlines(keepends=False)
    for line_no in sorted(patches):  # .keys().sort():
        patch = patches[line_no]
        for i in range(patch.line, patch.end_line + 1):
            print(f"{i:04d}: - {lines[i-1]}")
        print(f"{patch.line:04d}: + {patch.render()}")
    print()


def run(directory: str):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = f"{root}/{file}"
                with open(filepath) as f:
                    source = f.read()
                patches = get_patch(source, filepath)
                print_patches(filepath, patches, source)


def main():
    parser = argparse.ArgumentParser(
        prog="gxlint",
        description="Scan files looking greedy string interpolation in Galaxy.",
        epilog="Copyright 2023 The Galayx Project (https://galaxyproject.org)\n",
    )

    parser.add_argument("directory", help="the directory to scan", nargs="?")
    args = parser.parse_args()
    if args.directory is None:
        parser.print_help()
    else:
        run(args.directory)


if __name__ == "__main__":
    main()
