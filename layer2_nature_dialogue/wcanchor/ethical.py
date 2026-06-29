"""S9 -- ethical sanitizer: replace explicit PII spans before public release.

Two operations:

1. For each unified record, scan ``spec.essential_info``, ``spec.helpful_info``
   and ``spec.nonessential_sensitive_info`` for spans whose ``attribute`` is
   in cfg.replace_attributes (default: name, email, phone, address, ssn,
   driver license). Replace each such span IN ``raw_prompt`` and IN
   ``gold_reformulation`` with a deterministic Faker-generated pseudonym.
   Original surface form is recorded under ``meta.replacements``.

2. Optionally drop rows that look high-re-identification (4+ of:
   full address, employer, dates, name).

Faker is used when available; if not, we fall back to type-specific
placeholders (``[NAME]``, ``[EMAIL]`` ...).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from faker import Faker  # type: ignore
    _FAKER_OK = True
except Exception:  # pragma: no cover
    _FAKER_OK = False


@dataclass
class EthicalConfig:
    faker_locale: str = "en_US"
    replace_attributes: Tuple[str, ...] = (
        "name", "email", "phone_number", "address", "ssn", "driver_license",
    )
    drop_high_reidentification: bool = True
    high_reid_attributes: Tuple[str, ...] = (
        "name", "address", "employment", "dates",
    )
    high_reid_threshold: int = 4
    placeholders: Dict[str, str] = field(default_factory=lambda: {
        "name":           "[NAME]",
        "email":          "[EMAIL]",
        "phone_number":   "[PHONE]",
        "address":        "[ADDRESS]",
        "ssn":            "[SSN]",
        "driver_license": "[DRIVER_LICENSE]",
    })


class _PseudonymPool:
    """Deterministic pseudonym generator keyed on (attr, original_text).

    Same original text always maps to the same pseudonym within a run. Across
    runs, the pseudonym is deterministic if a salt is set in cfg.
    """

    def __init__(self, locale: str = "en_US", salt: str = ""):
        self.salt = salt
        self.cache: Dict[Tuple[str, str], str] = {}
        if _FAKER_OK:
            self.faker = Faker(locale)
        else:
            self.faker = None

    def _det_seed(self, attr: str, orig: str) -> int:
        h = hashlib.sha256((self.salt + "|" + attr + "|" + orig).encode("utf-8")).digest()
        return int.from_bytes(h[:8], "big", signed=False) % (2 ** 32)

    def get(self, attr: str, orig: str, placeholder: str) -> str:
        key = (attr, orig)
        if key in self.cache:
            return self.cache[key]
        if self.faker is not None:
            self.faker.seed_instance(self._det_seed(attr, orig))
            try:
                if attr == "name":
                    val = self.faker.name()
                elif attr == "email":
                    val = self.faker.email()
                elif attr == "phone_number":
                    val = self.faker.phone_number()
                elif attr == "address":
                    val = self.faker.address().replace("\n", ", ")
                elif attr == "ssn":
                    val = self.faker.ssn()
                elif attr == "driver_license":
                    val = self.faker.bothify(text="??######")
                else:
                    val = placeholder
            except Exception:  # noqa: BLE001
                val = placeholder
        else:
            val = placeholder
        self.cache[key] = val
        return val


def _replace_in_text(text: str, replacements: List[Tuple[str, str]]) -> str:
    """Apply replacements one at a time. Sort by descending length to avoid
    'New York' being replaced before 'New York City' is detected."""
    if not text:
        return text
    out = text
    for orig, new in sorted(replacements, key=lambda t: -len(t[0])):
        if orig and orig in out:
            out = out.replace(orig, new)
    return out


def _high_reid_count(spec: Dict[str, Any], cfg: EthicalConfig) -> int:
    """Count distinct cfg.high_reid_attributes that appear in any of the
    three info lists."""
    seen = set()
    for key in ("essential_info", "helpful_info", "nonessential_sensitive_info"):
        for s in spec.get(key, []) or []:
            attr = s.get("attribute")
            if attr in cfg.high_reid_attributes:
                seen.add(attr)
    return len(seen)


def sanitize(
    record: Dict[str, Any],
    pool: _PseudonymPool,
    cfg: EthicalConfig,
) -> Optional[Dict[str, Any]]:
    """Return a sanitized copy of a unified record, or None if dropped."""
    spec = record.get("spec") or {}
    if cfg.drop_high_reidentification and _high_reid_count(spec, cfg) >= cfg.high_reid_threshold:
        return None

    rec = {**record, "spec": {**spec}}
    replacements: List[Tuple[str, str, str, str]] = []  # (attr, orig, new, info_key)

    for key in ("essential_info", "helpful_info", "nonessential_sensitive_info"):
        new_list = []
        for s in spec.get(key, []) or []:
            attr = s.get("attribute")
            new_s = dict(s)
            if attr in cfg.replace_attributes:
                placeholder = cfg.placeholders.get(attr, f"[{attr.upper()}]")
                pseud = pool.get(attr, str(s.get("value", "")), placeholder)
                replacements.append((attr, str(s.get("value", "")), pseud, key))
                new_s["value"] = pseud
                new_s["sanitized"] = True
            new_list.append(new_s)
        rec["spec"][key] = new_list

    pairs = [(orig, new) for _, orig, new, _ in replacements if orig]
    rec["raw_prompt"] = _replace_in_text(rec.get("raw_prompt", ""), pairs)
    if rec.get("gold_reformulation"):
        rec["gold_reformulation"] = _replace_in_text(rec["gold_reformulation"], pairs)

    rec.setdefault("meta", {})
    rec["meta"]["replacements"] = [
        {"attribute": a, "info_key": k, "original": o, "replacement": n}
        for a, o, n, k in replacements
    ]
    return rec


def sanitize_all(
    records: List[Dict[str, Any]],
    cfg: EthicalConfig,
    salt: str = "",
) -> Tuple[List[Dict[str, Any]], int]:
    """Returns (kept, dropped_count)."""
    pool = _PseudonymPool(cfg.faker_locale, salt)
    kept: List[Dict[str, Any]] = []
    dropped = 0
    for r in records:
        s = sanitize(r, pool, cfg)
        if s is None:
            dropped += 1
        else:
            kept.append(s)
    return kept, dropped
