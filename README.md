# extract-ipv4

**A single-file CLI that extracts IPv4 addresses from a text file with strict, boundary-aware validation.**

`extract-ipv4.py` reads any plain-text input — log lines, firewall dumps, netflow exports, pcap text summaries, mixed-format incident data — and writes out one IPv4 address per line. The extraction is strict: each octet must be `0–255` with no leading zeros, and the match is **not** allowed to start or end inside a longer numeric run. That means version strings like `1.2.3.4.5`, prefixes like `1234.1.1.1`, and suffixes like `1.1.1.1234` produce zero matches rather than a spurious `1.2.3.4` or `2.3.4.5`.

Designed as the first stage of a two-step pipeline with its companion tool [lookup-ipv4](https://github.com/Hiroki-Tomimatsu/lookup-ipv4), but useful stand-alone for any "pull IPs out of this pile of text" task.

---

## Why this exists

Most one-liners for IP extraction look like this:

```bash
grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' input.txt
```

That pattern has two well-known problems:

1. It accepts `999.999.999.999` and `0.0.0.256` because it never checks the `0–255` range per octet.
2. It matches IP-shaped substrings inside longer numbers — e.g. in `version=1.2.3.4.5`, it happily emits `1.2.3.4`.

Tightening the regex to fix (1) is straightforward; tightening it to also fix (2) is fiddly and easy to get wrong. `extract-ipv4.py` bundles the correct regex — strict 0–255 per octet, no leading zeros, with lookarounds on both sides to enforce the boundary — into a well-tested script with useful post-processing options. You get the right IPs, not the IP-shaped substrings.

---

## Features

- **Strict dotted-quad validation.** Each octet is matched by a 0-to-255 alternation: `25[0-5]`, `2[0-4][0-9]`, `1[0-9]{2}`, `[1-9]?[0-9]`. Leading zeros are rejected (`01.02.03.04` does not match).
- **Boundary-aware matching.** Four lookarounds — `(?<![0-9])`, `(?<![0-9]\.)`, `(?![0-9])`, `(?!\.[0-9])` — ensure the match isn't starting or ending inside a longer dotted-numeric sequence. `1.2.3.4.5` produces **no matches** rather than `1.2.3.4` or `2.3.4.5`.
- **ASCII-only digits.** The regex uses an explicit `[0-9]` character class instead of `\d`, so Arabic-Indic numerals and other Unicode digit scripts won't accidentally participate in a match.
- **`--unique` with order preservation.** Deduplicates while keeping each address's first-seen position in the input — useful when the order tells you something (e.g. the first IP in a session log is the source).
- **`--sorted` by numeric value.** Sorts via `ipaddress.IPv4Address`, so `9.0.0.0` correctly precedes `10.0.0.0` rather than the usual lexicographic surprise (`10.*` < `9.*` as strings).
- **Configurable encoding.** `--encoding` propagates to both input read and output write, so Shift_JIS / EUC-JP / CP932 logs round-trip cleanly.
- **Quiet mode.** `--quiet` suppresses the final summary line, leaving stdout clean for shell pipelines that only care about the exit status.
- **Small, pure, easy-to-test.** The core is three short functions (`extract_ipv4_addresses`, `deduplicate_preserve_order`, `sort_ip_addresses`), all pure and callable as a library. The whole script is one file, standard library only.

---

## Installation

```bash
# No dependencies beyond the Python standard library.
git clone https://github.com/Hiroki-Tomimatsu/extract-ipv4.git
cd extract-ipv4
```

Python 3.9 or newer is recommended.

---

## Usage

### Basic

```bash
python extract-ipv4.py access.log
# -> writes access.log.ips (one IPv4 address per line)
```

### Deduplicate and sort

```bash
python extract-ipv4.py access.log --unique --sorted -o unique-sorted.ips
```

### Non-UTF-8 log files

```bash
python extract-ipv4.py windows-event.txt --encoding cp932 -o ips.txt
```

### Pipeline into lookup-ipv4

```bash
# 1. Extract
python extract-ipv4.py suspicious-traffic.log --unique -o ips.txt

# 2. Geolocate (see https://github.com/Hiroki-Tomimatsu/lookup-ipv4)
python ../lookup-ipv4/lookup-ipv4.py ips.txt --format json -o geo.json
```

### Option reference

```
positional:
  input                Path to the input text file.

options:
  -o, --output PATH    Output file. Defaults to '<input>.ips'.
  -u, --unique         Remove duplicate IP addresses (first-seen order preserved).
  -s, --sorted         Sort numerically (e.g. 9.0.0.0 before 10.0.0.0).
  -e, --encoding NAME  Text encoding for input and output (default: utf-8).
  -q, --quiet          Do not print the summary line.
```

Exit status: `0` on success, `1` on I/O error (missing input, unreadable file, unwritable output), `2` on argparse error.

---

## What matches and what doesn't

| Input line | Extracted |
|------------|-----------|
| `192.168.1.1` | `192.168.1.1` |
| `src=10.0.0.5 dst=8.8.8.8` | `10.0.0.5`, `8.8.8.8` |
| `IP is 255.255.255.255.` | `255.255.255.255` |
| `256.1.1.1` | *(nothing — octet out of range)* |
| `01.02.03.04` | *(nothing — leading zeros rejected)* |
| `1.2.3.4.5` | *(nothing — not a clean 4-tuple)* |
| `1234.1.1.1` | *(nothing — leading digit run)* |
| `1.1.1.1234` | *(nothing — trailing digit run)* |
| `client=١٩٢.١٦٨.١.١` (Arabic-Indic) | *(nothing — ASCII digits required)* |

---

## Example output

Input (`mixed.log`):

```
2026-04-21 09:12:33 connect 10.0.0.5 -> 93.184.216.34 ok
2026-04-21 09:12:34 connect 10.0.0.5 -> 1.1.1.1 ok
2026-04-21 09:12:35 version=1.2.3.4.5 client=256.0.0.1
2026-04-21 09:12:36 retry 10.0.0.5 -> 93.184.216.34 ok
```

Run:

```bash
python extract-ipv4.py mixed.log --unique --sorted
```

Output file (`mixed.log.ips`):

```
1.1.1.1
10.0.0.5
93.184.216.34
```

Stdout summary:

```
Extracted 3 IPv4 address(es) -> mixed.log.ips
```

Note that the `1.2.3.4.5` and `256.0.0.1` on line 3 produced no matches — the boundary and range rules rejected both.

---

## Use cases

**Log preparation for geo / threat-intel enrichment.** Most enrichment tools take a flat IP list as input. `extract-ipv4.py --unique --sorted` turns a gigabyte of messy logs into a minimal diffable file you can feed into the next step of the pipeline.

**Firewall / detection rule authoring.** Strip repeated IPs out of pcap text dumps or proxy logs to identify the actual distinct destinations you're dealing with, then build rules from that smaller set.

**Incident triage.** When you're handed a mixed bundle of text artifacts during an incident, this is the fast "what IPs are even in here" pass before any deeper analysis.

**Data cleaning for the `lookup-ipv4` companion.** `lookup-ipv4.py` expects one IP per line. `extract-ipv4.py --unique` is the intended producer of that file — duplicates are expensive at the geo-lookup step because of rate limits, so removing them up front is the right default.

---

## Library use

The three core functions are importable and side-effect-free, so the script can be dropped into another Python project as-is:

```python
from extract_ipv4 import (
    extract_ipv4_addresses,
    deduplicate_preserve_order,
    sort_ip_addresses,
)

text = open("access.log", encoding="utf-8").read()
ips = sort_ip_addresses(deduplicate_preserve_order(extract_ipv4_addresses(text)))
```

The compiled regex is also exposed as `IPV4_REGEX` if you need it directly.

---

## License

MIT. See `LICENSE`.

---

## See also

- [lookup-ipv4](https://github.com/Hiroki-Tomimatsu/lookup-ipv4) — geolocate an IPv4 list (one address per line) via a pluggable backend. Accepts the output of this tool directly.
