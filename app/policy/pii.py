"""Detect personal identifiers in user text. Do not log matching input."""

from __future__ import annotations

import re

# PAN: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)
_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)

# 12-digit Aadhaar, optional spaces
_AADHAAR = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

# Indian mobile: optional +91, then 10 digits starting 6–9
_MOBILE = re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}\b")

_OTP_KEYWORD = re.compile(r"\b(?:otp|one[\s-]?time(?:\s+password)?|password|pin)\b", re.IGNORECASE)
_OTP_CODE = re.compile(r"\b\d{4,8}\b")

# Account-like digit runs (not already covered as 10-digit mobile)
_ACCOUNT = re.compile(r"\b\d{9,18}\b")


def contains_pii(text: str) -> bool:
    """Return True if the text appears to contain PII. Does not log `text`."""
    if not text:
        return False

    if _PAN.search(text):
        return True
    if _EMAIL.search(text):
        return True
    if _MOBILE.search(text):
        return True
    if _AADHAAR.search(text):
        return True
    if _OTP_KEYWORD.search(text) and _OTP_CODE.search(text):
        return True
    if _ACCOUNT.search(text):
        return True
    return False
