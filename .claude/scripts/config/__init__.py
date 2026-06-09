"""Process-wide cached accessor for the workflow ``Config`` singleton."""

from functools import lru_cache

from .config import Config


@lru_cache(maxsize=1)
def get_config() -> Config:
    """
    Return a process-wide cached :class:`Config` instance.

    The ``lru_cache(maxsize=1)`` means ``config.json`` is read from disk
    exactly once per process, and every caller sees the same ``Config``
    object — important because Config exposes skill lookups via
    pre-built dicts (``_skill_map``, ``_skill_list``) that would be wasteful
    to rebuild on every call. Tests that mutate config state or rely on
    isolated defaults must call ``get_config.cache_clear()`` so the next
    invocation re-reads the file; the conftest ``config`` fixture does this
    automatically between tests.

    Returns:
        Config: The shared, lazily-constructed configuration object.

    Example:
        >>> from config import get_config
        >>> cfg = get_config()
        >>> cfg is get_config()  # same instance on subsequent calls
        True
    """
    return Config()


__all__ = ["Config", "get_config"]
