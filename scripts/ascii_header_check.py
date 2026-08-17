import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: ascii_header_check.py <contract.py>")
        return 2
    path = sys.argv[1]
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    for idx, line in enumerate(lines, 1):
        bad = [ch for ch in line if ord(ch) > 127]
        if bad:
            print(f"Line {idx}: {bad!r} {line.strip()}")
            return 1
    if len(lines) < 3:
        print("missing required header lines")
        return 1
    if not lines[0].startswith("# v"):
        print("line 1 must be current Studio version pragma")
        return 1
    if "Depends" not in lines[1]:
        print("line 2 must be Depends comment")
        return 1
    if lines[2].strip() != "from genlayer import *":
        print("line 3 must be from genlayer import *")
        return 1
    print("ASCII_HEADER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

