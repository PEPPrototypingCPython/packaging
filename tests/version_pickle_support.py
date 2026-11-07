# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.
"""Importable pickle fixtures without a dependency on the test runner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from packaging.version import Version

if TYPE_CHECKING:
    from typing_extensions import Self


class LabeledVersion(Version):
    __slots__ = ("__dict__", "label")
    label: str
    extra: dict[str, str]


class RequiredLabelVersion(Version):
    __slots__ = ("label",)

    def __new__(cls, version: str, _label: str) -> Self:
        parsed = Version(version)
        return cls.from_parts(release=parsed.release)

    def __init__(self, _version: str, label: str) -> None:
        self.label = label


class CustomStateVersion(Version):
    __slots__ = ("label",)

    def __getstate__(self) -> str:
        return self.label

    def __setstate__(self, state: object) -> None:
        if not isinstance(state, str):
            raise TypeError("Expected the custom string state")
        self.label = state


class PrivateSlotsVersion(Version):
    __slots__ = "__label"  # noqa: PLC0205 - Exercise the supported string-slot form.

    def set_label(self, label: str) -> None:
        self.__label = label

    def get_label(self) -> str:
        return self.__label


class DictionaryVersion(Version):
    note: str
