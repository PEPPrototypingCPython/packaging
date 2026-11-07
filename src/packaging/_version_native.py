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
    legacy_version_parts,
    parse_local_version,
    restore_subclass_state,
)

if TYPE_CHECKING:
    from typing_extensions import Self, override
else:
    from typing import override


class InvalidVersion(_NativeInvalidVersion):
    """Raised when a version string or component is invalid."""


class Version(_NativeVersion):
    """A PEP 440 version backed by the interpreter's native value type."""

    __slots__ = ()
    __match_args__ = ("_str",)
    __mutable_version__ = True
    __invalid_version__ = InvalidVersion

    @property
    def _key(self) -> CmpKey:
        # Legacy version classes compare using the historical tuple contract.
        return comparison_key(
            self.epoch,
            self.release,
            self.pre,
            None if self.post is None else ("post", self.post),
            None if self.dev is None else ("dev", self.dev),
            parse_local_version(self.local),
        )

    @property
    def _str(self) -> str:
        return str(self)

    @override
    def __setstate__(self, state: object) -> None:
        if type(self) is not Version and restore_subclass_state(self, state):
            return
        restored = Version.from_parts(**legacy_version_parts(state))
        super().__setstate__(restored)

    @property
    @deprecated("Version._version is private and will be removed soon")
    def _version(self) -> LegacyVersion:
        local = self.local
        return LegacyVersion(
            self.epoch,
            self.release,
            None if self.dev is None else ("dev", self.dev),
            self.pre,
            None if self.post is None else ("post", self.post),
            parse_local_version(local),
        )

    @_version.setter
    @deprecated("Version._version is private and will be removed soon")
    def _version(self, value: LegacyVersion) -> None:
        snapshot = _NativeVersion.from_parts(
            epoch=value.epoch,
            release=value.release,
            pre=value.pre,
            post=None if value.post is None else value.post[1],
            dev=None if value.dev is None else value.dev[1],
            local=None if value.local is None else ".".join(map(str, value.local)),
        )
        super().__setstate__(snapshot)


BaseVersion.register(Version)


class TrimmedRelease(Version):
    """Build a version without unnecessary trailing release zeros."""

    __slots__ = ()

    def __new__(cls, version: str | Version = UNSET) -> Self:
        if version is UNSET:
            return super().__new__(cls)
        parsed = version if isinstance(version, Version) else Version(version)
        release = parsed.release
        end = len(release)
        while end > 1 and release[end - 1] == 0:
            end -= 1
        return cls.from_parts(
            epoch=parsed.epoch,
            release=release[:end],
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
        normalized = value.release
        end = len(normalized)
        while end > 1 and normalized[end - 1] == 0:
            end -= 1
        if end == len(normalized):
            return value
        return _NativeVersion.__replace__(value, release=normalized[:end])

    def __init__(self, version: str | Version) -> None:
        pass

    @override
    def __setstate__(self, state: object) -> None:
        if restore_subclass_state(self, state):
            return
        value = TrimmedRelease.from_parts(**legacy_version_parts(state))
        _NativeVersion.__setstate__(self, value)
