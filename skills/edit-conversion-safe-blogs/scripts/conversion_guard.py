#!/usr/bin/env python3
"""Snapshot and verify conversion-critical Markdown structure."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


START_RE = re.compile(
    r'<!--\s*conversion-safe:start\s+id=(?:"([^"]+)"|([^\s>]+))\s*-->',
    re.IGNORECASE,
)
END_RE = re.compile(r"<!--\s*conversion-safe:end\s*-->", re.IGNORECASE)
H2_RE = re.compile(r"^##(?!#)\s+(.+?)\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
BULLET_RE = re.compile(r"^\s*[-*+]\s+\S", re.MULTILINE)
NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+\S", re.MULTILINE)
WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)


def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def clean_heading(text: str) -> str:
    return re.sub(r"\s+#+\s*$", "", text).strip()


def links(text: str) -> Counter[str]:
    return Counter(match.group(2) for match in LINK_RE.finditer(text))


def extract_protected(text: str) -> dict[str, dict]:
    blocks: dict[str, dict] = {}
    cursor = 0

    while True:
        start = START_RE.search(text, cursor)
        if not start:
            break
        block_id = start.group(1) or start.group(2)
        end = END_RE.search(text, start.end())
        if not end:
            raise ValueError(
                f'Protected block "{block_id}" has no conversion-safe:end marker.'
            )
        if block_id in blocks:
            raise ValueError(f'Duplicate protected block id "{block_id}".')

        content = text[start.end() : end.start()]
        block_headings = [
            {"level": len(match.group(1)), "text": clean_heading(match.group(2))}
            for match in HEADING_RE.finditer(content)
        ]
        blocks[block_id] = {
            "headings": block_headings,
            "links": dict(links(content)),
            "bullet_count": len(BULLET_RE.findall(content)),
            "numbered_count": len(NUMBERED_RE.findall(content)),
            "word_count": len(WORD_RE.findall(content)),
        }
        cursor = end.end()

    return blocks


def snapshot(path: Path) -> dict:
    text = read_markdown(path)
    protected = extract_protected(text)
    if not protected:
        raise ValueError(
            "No protected blocks found. Add conversion-safe:start/end markers "
            "around every conversion-critical section before snapshotting."
        )

    return {
        "version": 1,
        "source": str(path),
        "h2_outline": [clean_heading(item) for item in H2_RE.findall(text)],
        "links": dict(links(text)),
        "protected": protected,
    }


def is_subsequence(required: list[str], current: list[str]) -> bool:
    iterator = iter(current)
    return all(any(candidate == item for candidate in iterator) for item in required)


def verify(
    path: Path,
    contract: dict,
    *,
    allow_structure_change: bool,
    allow_link_removal: bool,
    min_word_ratio: float,
) -> list[str]:
    text = read_markdown(path)
    current_blocks = extract_protected(text)
    failures: list[str] = []

    current_outline = [clean_heading(item) for item in H2_RE.findall(text)]
    required_outline = contract.get("h2_outline", [])
    if not allow_structure_change and not is_subsequence(
        required_outline, current_outline
    ):
        failures.append("The original H2 outline was deleted, renamed, or reordered.")

    if not allow_link_removal:
        current_links = links(text)
        for url, required_count in contract.get("links", {}).items():
            if current_links[url] < required_count:
                failures.append(
                    f'Link "{url}" decreased from {required_count} to '
                    f"{current_links[url]}."
                )

    for block_id, required in contract.get("protected", {}).items():
        current = current_blocks.get(block_id)
        if current is None:
            failures.append(f'Protected block "{block_id}" is missing.')
            continue

        if not allow_structure_change and current["headings"] != required["headings"]:
            failures.append(
                f'Protected block "{block_id}" changed its heading structure.'
            )

        for url, required_count in required["links"].items():
            current_count = current["links"].get(url, 0)
            if current_count < required_count:
                failures.append(
                    f'Protected block "{block_id}" lost link "{url}" '
                    f"({required_count} -> {current_count})."
                )

        if current["bullet_count"] < required["bullet_count"]:
            failures.append(
                f'Protected block "{block_id}" lost bullet capabilities '
                f'({required["bullet_count"]} -> {current["bullet_count"]}).'
            )
        if current["numbered_count"] < required["numbered_count"]:
            failures.append(
                f'Protected block "{block_id}" lost numbered items '
                f'({required["numbered_count"]} -> {current["numbered_count"]}).'
            )

        required_words = required["word_count"]
        if required_words:
            ratio = current["word_count"] / required_words
            if ratio < min_word_ratio:
                failures.append(
                    f'Protected block "{block_id}" shrank to {ratio:.0%} of its '
                    f"original word count; minimum is {min_word_ratio:.0%}."
                )

    return failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Protect conversion-critical Markdown during editorial passes."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = subparsers.add_parser(
        "snapshot", help="Capture a draft's conversion contract."
    )
    snapshot_parser.add_argument("draft", type=Path)
    snapshot_parser.add_argument("--output", required=True, type=Path)

    verify_parser = subparsers.add_parser(
        "verify", help="Verify an edited draft against a saved contract."
    )
    verify_parser.add_argument("draft", type=Path)
    verify_parser.add_argument("--contract", required=True, type=Path)
    verify_parser.add_argument("--allow-structure-change", action="store_true")
    verify_parser.add_argument("--allow-link-removal", action="store_true")
    verify_parser.add_argument(
        "--min-protected-word-ratio",
        type=float,
        default=0.8,
        metavar="RATIO",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        if args.command == "snapshot":
            contract = snapshot(args.draft)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(
                f"PASS: captured {len(contract['protected'])} protected block(s), "
                f"{len(contract['h2_outline'])} H2 heading(s), and "
                f"{sum(contract['links'].values())} link(s)."
            )
            return 0

        if not 0 < args.min_protected_word_ratio <= 1:
            raise ValueError("--min-protected-word-ratio must be above 0 and at most 1.")

        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        failures = verify(
            args.draft,
            contract,
            allow_structure_change=args.allow_structure_change,
            allow_link_removal=args.allow_link_removal,
            min_word_ratio=args.min_protected_word_ratio,
        )
        if failures:
            for failure in failures:
                print(f"FAIL: {failure}", file=sys.stderr)
            return 1

        print(
            "PASS: conversion contract preserved "
            f"({len(contract.get('protected', {}))} protected block(s))."
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
