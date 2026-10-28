#!/usr/bin/env python3
"""Simple script to read and display the contents of a text file."""

import sys


def read_text_file(file_path):
    """Read a text file and return its contents."""
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file '{file_path}': {e}")
        sys.exit(1)


def main():
    if len(sys.argv) != 2:
        print("Usage: python read_file.py <path_to_txt_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    contents = read_text_file(file_path)
    print(contents)


if __name__ == "__main__":
    main()
