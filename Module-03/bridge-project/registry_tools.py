"""
Registry tools for the Vendor Onboarding Desk.

Two real sources. No API key. No pip install.

    GLEIF   https://api.gleif.org/api/v1/lei-records
            The global register of Legal Entity Identifiers. Regulators created
            it after 2008 so that "who exactly is this counterparty?" has one
            answer worldwide.

    OFAC    https://www.treasury.gov/ofac/downloads/sdn.csv
            The US Treasury sanctions list. Paying anyone on it is a criminal
            offence in most jurisdictions, including via a subsidiary.

-------------------------------------------------------------------------------
ONE OF THESE IS NOT WRITTEN.

`sanctions_screen()` is finished - read it, then leave it alone.
`gleif_lookup()` is YOUR job. Spec is in its docstring.
`verify_tools.py` will tell you the moment it is right.

Read the docs before you start:
    https://www.gleif.org/en/lei-data/gleif-api
-------------------------------------------------------------------------------

Every tool returns a STRING. Never raises, never returns a dict - same rule as
the calculator in Module 3. A tool that raises kills your graph; a tool that
returns "NO_RECORDS" is something your agent can read and react to.

    NO_RECORDS          the registry answered, and has nothing under that name
    NO_SANCTIONS_MATCH  screened, and nothing came close
    LOOKUP_UNAVAILABLE  the call did not complete (network, timeout, 5xx)

NO_RECORDS and LOOKUP_UNAVAILABLE are NOT the same thing.
And - this one matters more - NO_RECORDS does not mean the company is fake.
Work out why before you write any graph code.
"""

from __future__ import annotations

import csv
import difflib
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

NO_RECORDS = "NO_RECORDS"
NO_SANCTIONS_MATCH = "NO_SANCTIONS_MATCH"
LOOKUP_UNAVAILABLE = "LOOKUP_UNAVAILABLE"

_UA = "JHF-Agentic-AI-Bootcamp/1.0 (student project; contact: your-email@example.com)"
_TIMEOUT = 30
_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
_SDN_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sdn_cache.csv")


# ===========================================================================
# TOOL 1 - SANCTIONS SCREENING.   Finished. Read it, then leave it alone.
# ===========================================================================

def _load_sdn() -> list[tuple[str, str]]:
    """The SDN list is ~5 MB. Download once, then read from disk."""
    if not os.path.exists(_SDN_CACHE):
        req = urllib.request.Request(_SDN_URL, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            with open(_SDN_CACHE, "wb") as f:
                f.write(r.read())

    with open(_SDN_CACHE, "r", encoding="utf-8", errors="replace") as f:
        rows = csv.reader(f)
        # col1 = name, col2 = type, col3 = sanctions programme
        return [(r[1].strip(), r[3].strip())
                for r in rows
                if len(r) > 3 and r[2].strip().lower() == "-0-" and r[1].strip()]


def _normalise(name: str) -> str:
    """Lowercase, drop punctuation, drop the legal-form suffix."""
    s = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    for suffix in (" ltd", " llc", " inc", " plc", " ag", " a s", " pjsc",
                   " fze", " aps", " gmbh", " sa", " nv", " bv"):
        s = s.replace(suffix, " ")
    return " ".join(s.split())


def sanctions_screen(name: str, top: int = 5) -> str:
    """
    Screen a name against the OFAC sanctions list.

    Returns the CLOSEST NAMES and how similar they are - 0.0 to 1.0.

    ---------------------------------------------------------------------------
    READ THIS CAREFULLY. It does NOT tell you whether the company is sanctioned.
    It tells you what the list contains that looks a bit like the name you gave
    it. Deciding whether any of that is a real match is YOUR AGENT'S JOB.

    That is not a limitation of this tool - it is the actual problem. Every
    bank on earth employs people to clear false positives from screens exactly
    like this one. Fuzzy name matching produces near-misses constantly:
    "Trading Company" resembles a thousand other "Trading Companies".

    Set your threshold too low and you refuse to pay honest suppliers.
    Set it too high and you wire money to a sanctioned entity.
    Both are real failures. You will have to pick a number and defend it.
    ---------------------------------------------------------------------------
    """
    try:
        sdn = _load_sdn()
    except Exception:                                     # noqa: BLE001
        return LOOKUP_UNAVAILABLE

    target = _normalise(name)
    if not target:
        return NO_SANCTIONS_MATCH

    scored = []
    for listed, programme in sdn:
        ratio = difflib.SequenceMatcher(None, target, _normalise(listed)).ratio()
        scored.append((ratio, listed, programme))
    scored.sort(reverse=True)

    best = scored[:top]
    if not best or best[0][0] < 0.55:
        return NO_SANCTIONS_MATCH

    lines = [f"closest entries on the OFAC list to '{name}' "
             f"(similarity 0.0-1.0, NOT a verdict):"]
    for ratio, listed, programme in best:
        lines.append(f"  {ratio:.2f}  {listed}   [programme: {programme}]")
    return "\n".join(lines)


# ===========================================================================
# TOOL 2 - GLEIF.   YOU WRITE THIS ONE.
# ===========================================================================

def gleif_lookup(legal_name: str) -> str:
    """
    Ask the global LEI register what it holds under this company name.

    ---------------------------------------------------------------------------
    THIS IS THE PART YOU RESEARCH AND WRITE.
        https://www.gleif.org/en/lei-data/gleif-api

    Endpoint:
        https://api.gleif.org/api/v1/lei-records

    Three things you have to work out for yourself:

      1. The filter parameter is  filter[entity.legalName]  - square brackets,
         inside a URL. Send them raw and you will get nothing useful back.
         Work out what has to happen to them.

      2. The response is JSON:API. Nothing you want is at the top level - the
         company sits several layers down under data[] -> attributes ->
         entity / registration. Print the raw JSON once and read it before
         you write the parsing.

      3. THE SEARCH IS NOT EXACT, AND THIS IS THE WHOLE EXERCISE.
         A name may return several DIFFERENT legal entities. Your function
         must return ALL the candidates it found, not just the first one.

         If you return only data[0], you have hidden the hardest decision in
         this project inside your tool, and your agent will confidently
         approve a company nobody asked about.

    Return a STRING, never raise:
      - a readable list of every candidate, each with:
            legal name, LEI code, country,
            entity status         (ACTIVE / INACTIVE)
            registration status   (ISSUED / LAPSED / RETIRED / ...)
      - NO_RECORDS when the register answered and holds nothing
      - LOOKUP_UNAVAILABLE when the call did not complete

    Those two status fields are different things and both matter. Go and find
    out what a LAPSED registration means before you decide how to report it -
    it is not in your course notes, and it changes the verdict.

    Run  python verify_tools.py  to check yourself.
    ---------------------------------------------------------------------------
    """
    if not isinstance(legal_name, str):
        legal_name = ""

    query = legal_name.strip()
    if not query:
        return NO_RECORDS

    params = {"filter[entity.legalName]": query}
    url = "https://api.gleif.org/api/v1/lei-records?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/vnd.api+json"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return LOOKUP_UNAVAILABLE

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or not data:
        return NO_RECORDS

    def normalise_name(value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        lower = text.lower()
        lower = lower.replace("&", " and ")
        lower = re.sub(r"[^a-z0-9 ]+", " ", lower)
        return " ".join(lower.split())

    normalized_input = normalise_name(query)
    exact_count = 0
    lines = [f"GLEIF search results for '{legal_name}':"]

    for index, item in enumerate(data, start=1):
        attrs = item.get("attributes", {}) if isinstance(item, dict) else {}
        entity = attrs.get("entity") if isinstance(attrs, dict) else {}
        registration = attrs.get("registration") if isinstance(attrs, dict) else {}

        legal_obj = entity.get("legalName") if isinstance(entity, dict) else ""
        legal = legal_obj.get("name") if isinstance(legal_obj, dict) else (legal_obj or "")
        lei = attrs.get("lei") if isinstance(attrs, dict) else ""
        if not lei:
            lei = item.get("id") if isinstance(item, dict) else ""

        address = entity.get("legalAddress") if isinstance(entity, dict) else {}
        country = address.get("country") if isinstance(address, dict) else ""
        entity_status = str(entity.get("status") or "UNKNOWN").upper()
        reg_status = str(registration.get("status") or "UNKNOWN").upper()

        match_label = "exact" if normalise_name(str(legal)) == normalized_input else "not exact"
        if match_label == "exact":
            exact_count += 1

        lines.append(
            f"{index}. {legal or 'Unknown legal name'} | "
            f"LEI: {lei or 'n/a'} | country: {country or 'n/a'} | "
            f"entity status: {entity_status} | registration status: {reg_status} | match: {match_label}"
        )

    lines.append(f"exact matches: {exact_count} of {len(data)}")
    if exact_count == 0:
        lines.append("0 exactly")
    else:
        lines.append(f"{exact_count} exactly")
    return "\n".join(lines)
