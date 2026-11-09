# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.
"""Adapt the interpreter's native Version to packaging's compatibility contracts."""

from __future__ import annotations

from importlib.version import InvalidVersion as _NativeInvalidVersion
from importlib.version import Version as _NativeVersion
from typing import TYPE_CHECKING

from ._version_support import (
    UNSET,
    BaseVersion,
    CmpKey,
    LegacyVersion,
    comparison_key,
    deprecated,
    legacy_components,
    parse_local_version,
    trim_release,
    version_parts,
)

if TYPE_CHECKING:
    from typing_extensions import Self, override
else:
    from typing import override


class InvalidVersion(_NativeInvalidVersion):
    """Raised when a version string or component is invalid."""


# BaseVersion accepts legacy subclasses that the native comparison stubs reject.
class Version(_NativeVersion, BaseVersion):  # type: ignore[misc]
    """A PEP 440 version backed by the interpreter's native value type."""

    __slots__ = ()
    __match_args__ = ("_str",)
    __mutable_version__ = True
    __invalid_version__ = InvalidVersion
    # Native values keep no Python key cache, so consumers use the operators.
    _key_cache: None = None

    def _legacy_parts(self) -> LegacyVersion:
        return LegacyVersion(
            self.epoch,
            self.release,
            None if self.dev is None else ("dev", self.dev),
            self.pre,
            None if self.post is None else ("post", self.post),
            parse_local_version(self.local),
        )

    @property
    def _key(self) -> CmpKey:
        # Legacy version classes compare using the historical tuple contract.
        parts = self._legacy_parts()
        return comparison_key(
            parts.epoch, parts.release, parts.pre, parts.post, parts.dev, parts.local
        )

    @property
    def _str(self) -> str:
        return str(self)

    @override
    def __setstate__(self, state: object) -> None:
        legacy = legacy_components(state)
        if legacy is not None:
            state = type(self).from_parts(**version_parts(legacy))
        elif type(self) is Version:
            # A plain Version carries no subclass state.
            raise TypeError(f"Cannot restore Version from {state!r}")
        super().__setstate__(state)

    @property
    @deprecated("Version._version is private and will be removed soon")
    def _version(self) -> LegacyVersion:
        return self._legacy_parts()

    @_version.setter
    @deprecated("Version._version is private and will be removed soon")
    def _version(self, value: LegacyVersion) -> None:
        super().__setstate__(_NativeVersion.from_parts(**version_parts(value)))


class TrimmedRelease(Version):
    """Build a version without unnecessary trailing release zeros."""

    __slots__ = ()

    def __new__(cls, version: str | Version = UNSET) -> Self:
        if version is UNSET:
            return super().__new__(cls)
        parsed = version if isinstance(version, Version) else Version(version)
        return cls.from_parts(
            epoch=parsed.epoch,
            release=parsed.release,
            pre=parsed.pre,
            post=parsed.post,
            dev=parsed.dev,
            local=parsed.local,
        )

    @classmethod
    @override
    def from_parts(
        cls,
        *,
        release: tuple[int, ...],
        epoch: int = 0,
        pre: tuple[str, int] | None = None,
        post: int | None = None,
        dev: int | None = None,
        local: str | None = None,
    ) -> Self:
        value = super().from_parts(
            epoch=epoch, release=release, pre=pre, post=post, dev=dev, local=local
        )
        return value.__replace__(release=trim_release(value.release))

    def __init__(self, version: str | Version) -> None:
        # __new__ returns a built value, which the native initializer rejects.
        pass
