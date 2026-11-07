Version Handling
================

A core requirement of dealing with packages is the ability to work with
versions.

See `Version Specifiers Specification`_ for more details on the exact
format implemented in this module, for use in Python Packaging tooling.

When the interpreter provides ``importlib.version``,
:class:`~packaging.version.Version` subclasses its native version type.
Other interpreters use the Python implementation.
Pickles use the public ``packaging.version`` names and can be restored with
either implementation.

.. _Version Specifiers Specification: https://packaging.python.org/en/latest/specifications/version-specifiers/

Usage
-----

.. doctest::

    >>> from packaging.version import Version, parse
    >>> v1 = parse("1.0a5")
    >>> v2 = Version("1.0")
    >>> v1
    <Version('1.0a5')>
    >>> v2
    <Version('1.0')>
    >>> v1 < v2
    True
    >>> v1.epoch
    0
    >>> v1.release
    (1, 0)
    >>> v1.pre
    ('a', 5)
    >>> v1.is_prerelease
    True
    >>> v2.is_prerelease
    False
    >>> Version("french toast")
    Traceback (most recent call last):
        ...
    InvalidVersion: Invalid version: 'french toast'
    >>> Version("1.0").post
    >>> Version("1.0").is_postrelease
    False
    >>> Version("1.0.post0").post
    0
    >>> Version("1.0.post0").is_postrelease
    True


Reference
---------

.. automodule:: packaging.version
    :members:
    :special-members:
