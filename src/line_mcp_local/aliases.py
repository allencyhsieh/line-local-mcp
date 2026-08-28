from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class AliasFileError(RuntimeError):
    """Raised for invalid contact alias configuration."""


@dataclass(frozen=True)
class ResolvedContact:
    requested: str
    canonical: str
    aliases: tuple[str, ...]

    @property
    def candidates(self) -> tuple[str, ...]:
        values = (self.requested, self.canonical, *self.aliases)
        return tuple(dict.fromkeys(value for value in values if value))


class ContactAliases:
    def __init__(self, records: dict[str, tuple[str, ...]] | None = None):
        self._records = records or {}
        self._index: dict[str, str] = {}
        for canonical, aliases in self._records.items():
            for name in (canonical, *aliases):
                folded = name.casefold()
                if folded in self._index and self._index[folded] != canonical:
                    raise AliasFileError(f"contact name {name!r} belongs to multiple records")
                self._index[folded] = canonical

    @classmethod
    def load(cls, path: str | None) -> ContactAliases:
        if not path:
            return cls()
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AliasFileError(f"cannot read alias file: {exc}") from exc
        if not isinstance(raw, dict):
            raise AliasFileError("alias file must be a JSON object")

        records: dict[str, tuple[str, ...]] = {}
        for canonical, aliases in raw.items():
            if not isinstance(canonical, str) or not canonical.strip():
                raise AliasFileError("canonical contact names must be non-empty strings")
            if not isinstance(aliases, list) or not all(
                isinstance(alias, str) and alias.strip() for alias in aliases
            ):
                raise AliasFileError(f"aliases for {canonical!r} must be non-empty strings")
            records[canonical.strip()] = tuple(alias.strip() for alias in aliases)
        return cls(records)

    def resolve(self, name: str) -> ResolvedContact:
        requested = name.strip()
        canonical = self._index.get(requested.casefold(), requested)
        return ResolvedContact(requested, canonical, self._records.get(canonical, ()))
