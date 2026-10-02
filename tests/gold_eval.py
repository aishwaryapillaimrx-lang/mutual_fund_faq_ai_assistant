"""Gold-set evaluation (PRD §11): runs the real pipeline and scores each item."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from app.pipeline import answer_question

GOLD_PATH = Path(__file__).with_name("gold_set.json")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def load_gold() -> list[dict]:
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))


def _host_ok(url: str, allowed: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == a or host.endswith("." + a) for a in allowed)


def score_item(item: dict, response: dict) -> list[str]:
    """Return a list of failure reasons (empty = pass)."""
    problems = []
    if response["type"] != item["expect_type"]:
        problems.append(f"type {response['type']} != {item['expect_type']}")
    answer = response["answer"]
    for needle in item.get("must_include", []):
        if needle.lower() not in answer.lower():
            problems.append(f"missing '{needle}'")
    if not response["source_url"] or not _host_ok(response["source_url"], item["source_host_allowlist"]):
        problems.append(f"source host not allowed: {response['source_url'][:60]}")
    if not response["last_updated"]:
        problems.append("no last_updated")
    if len([s for s in _SENTENCE_SPLIT.split(answer) if s]) > 3:
        problems.append("more than 3 sentences")
    if item["expect_type"] == "not_found" and re.search(r"\d+(\.\d+)?\s*%|Rs\.?\s*\d", answer):
        problems.append("number appeared in a not_found answer")
    return problems


def run_gold() -> list[tuple[dict, dict, list[str]]]:
    rows = []
    for item in load_gold():
        response = answer_question(item["question"])
        rows.append((item, response, score_item(item, response)))
    return rows
