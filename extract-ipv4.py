#!/usr/bin/env python3
"""
extract-ipv4.py
===============

Extract IPv4 addresses from a plain-text file with a regular expression and
write them to an output file, one address per line.

Features
--------
 Strict dotted-quad validation (each octet in the range 0-255, no leading
  zeros).
 Boundary-aware matching: substrings of longer numeric sequences such as
  ``1234.1.1.1``, ``1.1.1.1234``, or ``1.2.3.4.5`` are NOT extracted.
 Optional de-duplication (``--unique``) while preserving first-seen order.
 Optional numeric sorting (``--sorted``) using ``ipaddress.IPv4Address``.

Usage
-----
    python3 extract_ipv4.py input.txt
    python3 extract_ipv4.py input.txt -o ips.txt --unique --sorted

Exit codes
----------
    0 : success
    1 : I/O error (input missing, cannot read, cannot write, ...)
    2 : argument parsing error (raised by argparse)
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Regular expression
# ---------------------------------------------------------------------------
#
# Each octet alternative matches exactly 0-255 with no leading zeros:
#
#   25[0-5]        -> 250..255
#   2[0-4][0-9]    -> 200..249
#   1[0-9]{2}      -> 100..199
#   [1-9]?[0-9]    ->   0..99  (single digit, or two digits with non-zero lead)
#
# The surrounding lookarounds stop the regex from matching IP-like substrings
# embedded inside longer numeric sequences:
#
#   (?<![0-9])      not preceded by a digit        -> rejects "1234.1.1.1"
#   (?<![0-9]\.)    not preceded by digit + dot    -> rejects "1.2.3.4.5"
#                                                     (no match at "2.3.4.5")
#   (?![0-9])       not followed by a digit        -> rejects "1.1.1.1234"
#   (?!\.[0-9])     not followed by dot + digit    -> rejects "1.2.3.4.5"
#                                                     (no match at "1.2.3.4")
#
# Explicit [0-9] (instead of \d) avoids accidentally matching non-ASCII
# Unicode digits such as Arabic-Indic numerals.
OCTET = r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])"
IPV4_REGEX = re.compile(
    r"(?<![0-9])(?<![0-9]\.)"
    rf"{OCTET}(?:\.{OCTET}){{3}}"
    r"(?![0-9])(?!\.[0-9])"
)


# ---------------------------------------------------------------------------
# Core API (small, pure functions that are easy to unit-test)
# ---------------------------------------------------------------------------
def extract_ipv4_addresses(text: str) -> List[str]:
    """Return every IPv4 address found in text, in order of appearance.

    Duplicates are preserved; use :func:`deduplicate_preserve_order` to remove
    them while keeping the original ordering.
    """
    return IPV4_REGEX.findall(text)


def deduplicate_preserve_order(items: Iterable[str]) -> List[str]:
    """Remove duplicates from items while preserving first-seen order."""
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def sort_ip_addresses(addresses: Iterable[str]) -> List[str]:
    """Return addresses sorted numerically (not lexicographically).

    ``"9.0.0.0"`` therefore sorts before ``"10.0.0.0"``.
    """
    return sorted(addresses, key=lambda a: int(ipaddress.IPv4Address(a)))


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="extract_ipv4",
        description="Extract IPv4 addresses from a text file and write them "
                    "to an output file (one address per line).",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the input text file.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Path to the output file. Defaults to '<input>.ips'.",
    )
    parser.add_argument(
        "-u", "--unique",
        action="store_true",
        help="Remove duplicate IP addresses (first-seen order is preserved).",
    )
    parser.add_argument(
        "-s", "--sorted",
        dest="sort",
        action="store_true",
        help="Sort the output numerically (e.g. 9.0.0.0 before 10.0.0.0).",
    )
    parser.add_argument(
        "-e", "--encoding",
        default="utf-8",
        help="Text encoding for both input and output files (default: utf-8).",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Do not print a summary line to stdout.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    # 1. Validate input file
    if not args.input.is_file():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        return 1

    # 2. Read the input
    try:
        text = args.input.read_text(encoding=args.encoding)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Error reading input file: {exc}", file=sys.stderr)
        return 1

    # 3. Extract, optionally deduplicate, optionally sort
    addresses = extract_ipv4_addresses(text)
    if args.unique:
        addresses = deduplicate_preserve_order(addresses)
    if args.sort:
        addresses = sort_ip_addresses(addresses)

    # 4. Determine the output path and write
    output_path = args.output
    if output_path is None:
        output_path = args.input.with_suffix(args.input.suffix + ".ips")

    payload = "\n".join(addresses)
    if addresses:
        payload += "\n"  # POSIX-friendly trailing newline when non-empty

    try:
        output_path.write_text(payload, encoding=args.encoding)
    except OSError as exc:
        print(f"Error writing output file: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            f"Extracted {len(addresses)} IPv4 address(es) -> {output_path}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
