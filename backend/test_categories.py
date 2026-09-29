#!/usr/bin/env python3
"""Unit tests for categories.is_junk_title.

Dependency-free (plain asserts, stdlib only), like test_webutil.py.

Usage:
    cd backend && python test_categories.py
"""
from __future__ import annotations

import sys

import categories as cats

failures: list[str] = []


def check(label: str, actual, expected) -> None:
    if actual == expected:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         expected: {expected!r}\n         actual:   {actual!r}")
        failures.append(label)


print("junk titles are dropped")
for title in [
    "Today's horoscope: what the stars say for Leo",
    "Horoscopes for the week ahead",
    "5 easy recipes for monsoon evenings",
    "Beauty tips for glowing skin",
    "Vastu tips for your new home",
    "Viral video of dancing grandma wins hearts",
    "నేటి రాశి ఫలాలు",
    "జ్యోతిష్యం ప్రకారం ఈ వారం",
]:
    check(title, cats.is_junk_title(title), True)

# Real headlines from the curated feeds that the old substring-anywhere filter
# dropped. Each only mentions a lifestyle word in passing.
print("news that merely mentions a lifestyle word is kept")
for title in [
    "Ayodhya Ram temple donation theft case: Three accused remanded in police custody",
    "TN CBCID arrests four in Rs 100 crore Palani temple land fraud case",
    "B'luru law student murder case: Chit fund dispute, failed relationship emerge as motives",
    "We have to come out of it: Shah calls for better RBI-UCB relationship",
    "Govt sets LPG production targets for refiners; Reliance gets largest quota",
    "HKMCF India opens community kitchen to provide breakfast to 29,183 Telangana students",
    "Monte Carlo Fashions posts wider Q1 net loss of Rs 23.4 crore",
    "Pujara hits century as India A take control",
    "Japan's Diet passes the budget",
    "Temple Mount clashes leave dozens injured",
]:
    check(title, cats.is_junk_title(title), False)

print("Telugu word boundaries")
# "వంటి" ("such as") starts with the letters of "వంట" (cooking); the Telugu
# vowel sign after it must count as part of the word.
check("వంటకం matches as a word", cats.is_junk_title("సులువైన వంటకం"), True)
check("వంటి is not వంటకం", cats.is_junk_title("ఇలాంటి వంటి ఘటనలు"), False)
check("empty title", cats.is_junk_title(""), False)
check("None title", cats.is_junk_title(None), False)

if failures:
    print(f"\n{len(failures)} failure(s)")
    sys.exit(1)

print("\nall passed")
