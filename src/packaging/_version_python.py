# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.
"""The Python implementation used when no native Version is available."""

from __future__ import annotations

import re
import typing
from functools import partial
from typing import Literal

from ._version_support import (
    SIMPLE_VERSION_INDICATORS,
    UNSET,
    VERSION_PATTERN,
    BaseVersion,
    CmpKey,
    InvalidVersion,
    LegacyVersion,
    LocalType,
    comparison_key,
    deprecated,
    legacy_components,
    parse_letter_version,
    parse_local_version,
    restore_subclass_state,
    subclass_state,
    trim_release,
    validate_dev,
    validate_epoch,
    validate_local,
    validate_post,
    validate_pre,
    validate_release,
)

__all__ = ["InvalidVersion", "TrimmedRelease", "Version"]

if typing.TYPE_CHECKING:
    from typing_extensions import Self


class Version(BaseVersion):
    """This class abstracts handling of a project's versions.

    A :class:`Version` instance is comparison aware and can be compared and
    sorted using the standard Python interfaces.

    >>> v1 = Version("1.0a5")
    >>> v2 = Version("1.0")
    >>> v1
    <Version('1.0a5')>
    >>> v2
    <Version('1.0')>
    >>> v1 < v2
    True
    >>> v1 == v2
    False
    >>> v1 > v2
    False
    >>> v1 >= v2
    False
    >>> v1 <= v2
    True

    :class:`Version` is immutable; use :meth:`__replace__` to change
    part of a version.

    Instances are safe to serialize with :mod:`pickle`. They use a stable
    format so the same pickle can be loaded in future packaging releases.

    .. versionchanged:: 26.2

        Added a stable pickle format. Pickles created with packaging 26.2+ can
        be unpickled with future releases.  Backward compatibility with pickles
        from packaging < 26.2 is supported but may be removed in a future
        release.
    """

    __slots__ = (
        "_dev",
        "_epoch",
        "_hash_cache",
        "_key_cache",
        "_local",
        "_post",
        "_pre",
        "_release",
    )
    __match_args__ = ("_str",)
    """
    Pattern matching is supported on Python 3.10+.

    .. versionadded:: 26.0

    :meta hide-value:
    """

    _regex = re.compile(r"\s*" + VERSION_PATTERN + r"\s*", re.VERBOSE | re.IGNORECASE)

    _epoch: int
    _release: tuple[int, ...]
    _dev: tuple[Literal["dev"], int] | None
    _pre: tuple[Literal["a", "b", "rc"], int] | None
    _post: tuple[Literal["post"], int] | None
    _local: LocalType | None

    _hash_cache: int | None
    _key_cache: CmpKey | None

    def __init__(self, version: str) -> None:
        """Initialize a Version object.

        :param version:
            The string representation of a version which will be parsed and normalized
            before use.
        :raises InvalidVersion:
            If the ``version`` does not conform to PEP 440 in any way then this
            exception will be raised.
        """
        try:
            is_simple = SIMPLE_VERSION_INDICATORS.issuperset(version)
        except TypeError:
            raise InvalidVersion(f"Invalid version: {version!r}") from None

        if is_simple:
            try:
                self._release = tuple(map(int, version.split(".")))
            except AttributeError:
                raise InvalidVersion(f"Invalid version: {version!r}") from None
            except ValueError:
                # Empty parts (from "1..2", ".1", etc.) are invalid versions.
                # Any other ValueError (e.g. int str-digits limit) should
                # propagate to the caller.
                if "" in version.split("."):
                    raise InvalidVersion(f"Invalid version: {version!r}") from None
                raise

            self._epoch = 0
            self._pre = None
            self._post = None
            self._dev = None
            self._local = None
            self._key_cache = None
            self._hash_cache = None
            return

        # Validate the version and parse it into pieces
        try:
            match = self._regex.fullmatch(version)
        except TypeError:
            raise InvalidVersion(f"Invalid version: {version!r}") from None
        if not match:
            raise InvalidVersion(f"Invalid version: {version!r}")
        self._epoch = int(match.group("epoch")) if match.group("epoch") else 0
        self._release = tuple(map(int, match.group("release").split(".")))
        # We can type ignore the assignments below because the regex guarantees
        # the correct strings
        self._pre = parse_letter_version(match.group("pre_l"), match.group("pre_n"))  # type: ignore[assignment]
        self._post = parse_letter_version(  # type: ignore[assignment]
            match.group("post_l"), match.group("post_n1") or match.group("post_n2")
        )
        self._dev = parse_letter_version(match.group("dev_l"), match.group("dev_n"))  # type: ignore[assignment]
        self._local = parse_local_version(match.group("local"))

        # Key which will be used for sorting
        self._key_cache = None
        self._hash_cache = None

    @classmethod
    def from_parts(
        cls,
        *,
        epoch: int = 0,
        release: tuple[int, ...],
        pre: tuple[str, int] | None = None,
        post: int | None = None,
        dev: int | None = None,
        local: str | None = None,
    ) -> Self:
        """
        Return a new version composed of the various parts.

        This allows you to build a version without going though a string and
        running a regular expression. It normalizes pre-release strings. The
        ``release=`` keyword argument is required.

        >>> Version.from_parts(release=(1,2,3))
        <Version('1.2.3')>
        >>> Version.from_parts(release=(0,1,0), pre=("b", 1))
        <Version('0.1.0b1')>

        :param epoch:
        :param release: This version tuple is required

        .. versionadded:: 26.1
        """
        _epoch = validate_epoch(epoch)
        _release = validate_release(release)
        _pre = validate_pre(pre) if pre is not None else None
        _post = validate_post(post) if post is not None else None
        _dev = validate_dev(dev) if dev is not None else None
        _local = validate_local(local) if local is not None else None

        new_version = object.__new__(cls)
        new_version._key_cache = None
        new_version._hash_cache = None
        new_version._epoch = _epoch
        new_version._release = _release
        new_version._pre = _pre
        new_version._post = _post
        new_version._dev = _dev
        new_version._local = _local

        return new_version

    def __replace__(
        self,
        *,
        epoch: int | None = UNSET,
        release: tuple[int, ...] | None = UNSET,
        pre: tuple[str, int] | None = UNSET,
        post: int | None = UNSET,
        dev: int | None = UNSET,
        local: str | None = UNSET,
    ) -> Self:
        """
        __replace__(*, epoch=..., release=..., pre=..., post=..., dev=..., local=...)

        Return a new version with parts replaced.

        This returns a new version (unless no parts were changed). The
        pre-release is normalized. Setting a value to ``None`` clears it.

        >>> v = Version("1.2.3")
        >>> v.__replace__(pre=("a", 1))
        <Version('1.2.3a1')>

        :param int | None epoch:
        :param tuple[int, ...] | None release:
        :param tuple[str, int] | None pre:
        :param int | None post:
        :param int | None dev:
        :param str | None local:

        .. versionadded:: 26.0
        .. versionchanged:: 26.1

           The pre-release portion is now normalized.

        .. versionchanged:: 26.4

           Unknown keyword arguments now raise :exc:`TypeError` instead of
           being silently ignored.
        """
        _epoch = self._epoch if epoch is UNSET else validate_epoch(epoch)
        _release = self._release if release is UNSET else validate_release(release)
        _pre = self._pre if pre is UNSET else validate_pre(pre)
        _post = self._post if post is UNSET else validate_post(post)
        _dev = self._dev if dev is UNSET else validate_dev(dev)
        _local = self._local if local is UNSET else validate_local(local)

        if (
            _epoch == self._epoch
            and _release == self._release
            and _pre == self._pre
            and _post == self._post
            and _dev == self._dev
            and _local == self._local
        ):
            return self

        new_version = object.__new__(self.__class__)
        new_version._key_cache = None
        new_version._hash_cache = None
        new_version._epoch = _epoch
        new_version._release = _release
        new_version._pre = _pre
        new_version._post = _post
        new_version._dev = _dev
        new_version._local = _local

        return new_version

    @property
    def _key(self) -> CmpKey:
        if self._key_cache is None:
            self._key_cache = comparison_key(
                self._epoch,
                self._release,
                self._pre,
                self._post,
                self._dev,
                self._local,
            )
        return self._key_cache

    # __hash__ must be defined when __eq__ is overridden,
    # otherwise Python sets __hash__ to None.
    def __hash__(self) -> int:
        if (cached_hash := self._hash_cache) is not None:
            return cached_hash

        if (key := self._key_cache) is None:
            self._key_cache = key = comparison_key(
                self._epoch,
                self._release,
                self._pre,
                self._post,
                self._dev,
                self._local,
            )
        self._hash_cache = cached_hash = hash(key)
        return cached_hash

    # Override comparison methods to use direct _key_cache access
    # This is faster than property access, especially before Python 3.12
    def __lt__(self, other: BaseVersion) -> bool:
        if isinstance(other, Version):
            if self._key_cache is None:
                self._key_cache = comparison_key(
                    self._epoch,
                    self._release,
                    self._pre,
                    self._post,
                    self._dev,
                    self._local,
                )
            if other._key_cache is None:
                other._key_cache = comparison_key(
                    other._epoch,
                    other._release,
                    other._pre,
                    other._post,
                    other._dev,
                    other._local,
                )
            return self._key_cache < other._key_cache

        if not isinstance(other, BaseVersion):
            return NotImplemented

        return super().__lt__(other)

    def __le__(self, other: BaseVersion) -> bool:
        if isinstance(other, Version):
            if self._key_cache is None:
                self._key_cache = comparison_key(
                    self._epoch,
                    self._release,
                    self._pre,
                    self._post,
                    self._dev,
                    self._local,
                )
            if other._key_cache is None:
                other._key_cache = comparison_key(
                    other._epoch,
                    other._release,
                    other._pre,
                    other._post,
                    other._dev,
                    other._local,
                )
            return self._key_cache <= other._key_cache

        if not isinstance(other, BaseVersion):
            return NotImplemented

        return super().__le__(other)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Version):
            if self._key_cache is None:
                self._key_cache = comparison_key(
                    self._epoch,
                    self._release,
                    self._pre,
                    self._post,
                    self._dev,
                    self._local,
                )
            if other._key_cache is None:
                other._key_cache = comparison_key(
                    other._epoch,
                    other._release,
                    other._pre,
                    other._post,
                    other._dev,
                    other._local,
                )
            return self._key_cache == other._key_cache

        if not isinstance(other, BaseVersion):
            return NotImplemented

        return super().__eq__(other)

    def __ge__(self, other: BaseVersion) -> bool:
        if isinstance(other, Version):
            if self._key_cache is None:
                self._key_cache = comparison_key(
                    self._epoch,
                    self._release,
                    self._pre,
                    self._post,
                    self._dev,
                    self._local,
                )
            if other._key_cache is None:
                other._key_cache = comparison_key(
                    other._epoch,
                    other._release,
                    other._pre,
                    other._post,
                    other._dev,
                    other._local,
                )
            return self._key_cache >= other._key_cache

        if not isinstance(other, BaseVersion):
            return NotImplemented

        return super().__ge__(other)

    def __gt__(self, other: BaseVersion) -> bool:
        if isinstance(other, Version):
            if self._key_cache is None:
                self._key_cache = comparison_key(
                    self._epoch,
                    self._release,
                    self._pre,
                    self._post,
                    self._dev,
                    self._local,
                )
            if other._key_cache is None:
                other._key_cache = comparison_key(
                    other._epoch,
                    other._release,
                    other._pre,
                    other._post,
                    other._dev,
                    other._local,
                )
            return self._key_cache > other._key_cache

        if not isinstance(other, BaseVersion):
            return NotImplemented

        return super().__gt__(other)

    def __ne__(self, other: object) -> bool:
        if isinstance(other, Version):
            if self._key_cache is None:
                self._key_cache = comparison_key(
                    self._epoch,
                    self._release,
                    self._pre,
                    self._post,
                    self._dev,
                    self._local,
                )
            if other._key_cache is None:
                other._key_cache = comparison_key(
                    other._epoch,
                    other._release,
                    other._pre,
                    other._post,
                    other._dev,
                    other._local,
                )
            return self._key_cache != other._key_cache

        if not isinstance(other, BaseVersion):
            return NotImplemented

        return super().__ne__(other)

    def __reduce__(self) -> tuple[object, ...]:
        constructor = partial(
            type(self).from_parts,
            epoch=self._epoch,
            release=self._release,
            pre=self._pre,
            post=None if self._post is None else self._post[1],
            dev=None if self._dev is None else self._dev[1],
            local=self.local,
        )
        return constructor, (), self.__getstate__()

    def __getstate__(self) -> object:
        # Core components are constructor arguments; state belongs to subclasses.
        if type(self) is Version:
            return None
        return subclass_state(self, Version.__slots__)

    def __setstate__(self, state: object) -> None:
        legacy = legacy_components(state)
        if legacy is None:
            if type(self) is Version:
                # A plain Version carries no subclass state.
                raise TypeError(f"Cannot restore Version from {state!r}")
            restore_subclass_state(self, state)
            return
        # Discard cached values: old pickles may hold stale references
        # (e.g. packaging._structures.InfinityType from pre-26.1 pickles).
        self._key_cache = None
        self._hash_cache = None
        (
            self._epoch,
            self._release,
            self._dev,
            self._pre,
            self._post,
            self._local,
        ) = legacy

    @property
    @deprecated("Version._version is private and will be removed soon")
    def _version(self) -> LegacyVersion:
        return LegacyVersion(
            self._epoch, self._release, self._dev, self._pre, self._post, self._local
        )

    @_version.setter
    @deprecated("Version._version is private and will be removed soon")
    def _version(self, value: LegacyVersion) -> None:
        self._epoch = value.epoch
        self._release = value.release
        self._dev = value.dev
        self._pre = value.pre
        self._post = value.post
        self._local = value.local
        self._key_cache = None
        self._hash_cache = None

    def __repr__(self) -> str:
        """A representation of the Version that shows all internal state.

        >>> Version('1.0.0')
        <Version('1.0.0')>
        """
        return f"<{self.__class__.__name__}({str(self)!r})>"

    def __str__(self) -> str:
        """A string representation of the version that can be round-tripped.

        >>> str(Version("1.0a5"))
        '1.0a5'
        """
        # This is a hot function, so not calling self.base_version
        version = ".".join(map(str, self.release))

        # Epoch
        if self.epoch:
            version = f"{self.epoch}!{version}"

        # Pre-release
        if self.pre is not None:
            version += "".join(map(str, self.pre))

        # Post-release
        if self.post is not None:
            version += f".post{self.post}"

        # Development release
        if self.dev is not None:
            version += f".dev{self.dev}"

        # Local version segment
        if self.local is not None:
            version += f"+{self.local}"

        return version

    @property
    def _str(self) -> str:
        """Internal property for match_args"""
        return str(self)

    @property
    def epoch(self) -> int:
        """The epoch of the version.

        >>> Version("2.0.0").epoch
        0
        >>> Version("1!2.0.0").epoch
        1
        """
        return self._epoch

    @property
    def release(self) -> tuple[int, ...]:
        """The components of the "release" segment of the version.

        >>> Version("1.2.3").release
        (1, 2, 3)
        >>> Version("2.0.0").release
        (2, 0, 0)
        >>> Version("1!2.0.0.post0").release
        (2, 0, 0)

        Includes trailing zeroes but not the epoch or any pre-release / development /
        post-release suffixes.
        """
        return self._release

    @property
    def pre(self) -> tuple[Literal["a", "b", "rc"], int] | None:
        """The pre-release segment of the version.

        >>> print(Version("1.2.3").pre)
        None
        >>> Version("1.2.3a1").pre
        ('a', 1)
        >>> Version("1.2.3b1").pre
        ('b', 1)
        >>> Version("1.2.3rc1").pre
        ('rc', 1)
        """
        return self._pre

    @property
    def post(self) -> int | None:
        """The post-release number of the version.

        >>> print(Version("1.2.3").post)
        None
        >>> Version("1.2.3.post1").post
        1
        """
        return self._post[1] if self._post else None

    @property
    def dev(self) -> int | None:
        """The development number of the version.

        >>> print(Version("1.2.3").dev)
        None
        >>> Version("1.2.3.dev1").dev
        1
        """
        return self._dev[1] if self._dev else None

    @property
    def local(self) -> str | None:
        """The local version segment of the version.

        >>> print(Version("1.2.3").local)
        None
        >>> Version("1.2.3+abc").local
        'abc'
        """
        if self._local:
            return ".".join(str(x) for x in self._local)
        else:
            return None

    @property
    def public(self) -> str:
        """The public portion of the version.

        This returns a string. If you want a :class:`Version` again and care
        about performance, use ``v.__replace__(local=None)`` instead.

        >>> Version("1.2.3").public
        '1.2.3'
        >>> Version("1.2.3+abc").public
        '1.2.3'
        >>> Version("1!1.2.3dev1+abc").public
        '1!1.2.3.dev1'
        """
        return str(self).split("+", 1)[0]

    @property
    def base_version(self) -> str:
        """The "base version" of the version.

        This returns a string. If you want a :class:`Version` again and care
        about performance, use
        ``v.__replace__(pre=None, post=None, dev=None, local=None)`` instead.

        >>> Version("1.2.3").base_version
        '1.2.3'
        >>> Version("1.2.3+abc").base_version
        '1.2.3'
        >>> Version("1!1.2.3dev1+abc").base_version
        '1!1.2.3'

        The "base version" is the public version of the project without any pre or post
        release markers.
        """
        release_segment = ".".join(map(str, self.release))
        return f"{self.epoch}!{release_segment}" if self.epoch else release_segment

    @property
    def is_prerelease(self) -> bool:
        """Whether this version is a pre-release.

        >>> Version("1.2.3").is_prerelease
        False
        >>> Version("1.2.3a1").is_prerelease
        True
        >>> Version("1.2.3b1").is_prerelease
        True
        >>> Version("1.2.3rc1").is_prerelease
        True
        >>> Version("1.2.3dev1").is_prerelease
        True
        """
        return self.dev is not None or self.pre is not None

    @property
    def is_postrelease(self) -> bool:
        """Whether this version is a post-release.

        >>> Version("1.2.3").is_postrelease
        False
        >>> Version("1.2.3.post1").is_postrelease
        True
        """
        return self.post is not None

    @property
    def is_devrelease(self) -> bool:
        """Whether this version is a development release.

        >>> Version("1.2.3").is_devrelease
        False
        >>> Version("1.2.3.dev1").is_devrelease
        True
        """
        return self.dev is not None

    @property
    def major(self) -> int:
        """The first item of :attr:`release` or ``0`` if unavailable.

        >>> Version("1.2.3").major
        1

        .. versionadded:: 20.0
        """
        return self.release[0] if len(self.release) >= 1 else 0

    @property
    def minor(self) -> int:
        """The second item of :attr:`release` or ``0`` if unavailable.

        >>> Version("1.2.3").minor
        2
        >>> Version("1").minor
        0

        .. versionadded:: 20.0
        """
        return self.release[1] if len(self.release) >= 2 else 0

    @property
    def micro(self) -> int:
        """The third item of :attr:`release` or ``0`` if unavailable.

        >>> Version("1.2.3").micro
        3
        >>> Version("1").micro
        0

        .. versionadded:: 20.0
        """
        return self.release[2] if len(self.release) >= 3 else 0


class TrimmedRelease(Version):
    __slots__ = ()

    def __init__(self, version: str | Version) -> None:
        if isinstance(version, Version):
            self._epoch = version._epoch
            self._release = version._release
            self._dev = version._dev
            self._pre = version._pre
            self._post = version._post
            self._local = version._local
            self._key_cache = version._key_cache
            self._hash_cache = version._hash_cache
            return
        super().__init__(version)  # pragma: no cover

    @property
    def release(self) -> tuple[int, ...]:
        """
        Release segment without any trailing zeros.

        >>> _TrimmedRelease('1.0.0').release
        (1,)
        >>> _TrimmedRelease('0.0').release
        (0,)
        """
        return trim_release(super().release)
