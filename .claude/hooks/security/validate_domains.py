"""Domain allowlist hook — denies WebFetch to non-allowlisted domains.

Parses the requested URL down to its hostname and checks it against the
configured ``safe_domains`` list, accepting an exact host match or any
subdomain of an allowlisted host.
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.utils.hook import Hook  # type: ignore
from scripts.config.config import Config  # type: ignore


def get_safe_domains() -> list[str]:
    config = Config()
    return config.safe_domains


def extract_hostname(url: str) -> str:
    # Prefix bare hostnames so urlparse populates netloc instead of path
    target = url if "://" in url else f"//{url}"
    hostname = urlparse(target, scheme="https").hostname or ""
    return hostname.lower()


def is_allowlisted(hostname: str, safe_domains: list[str]) -> bool:
    # Match the exact host or any subdomain; the leading dot on the
    # suffix check rejects spoofs like "evilgithub.com" or
    # "github.com.evil.com"
    for safe_domain in safe_domains:
        safe_domain = safe_domain.lower()
        if hostname == safe_domain or hostname.endswith(f".{safe_domain}"):
            return True
    return False


def validate_domain(url: str, safe_domains: list[str]) -> tuple[bool, str]:
    hostname = extract_hostname(url)
    if not hostname:
        return False, f"Could not parse a hostname from URL: {url!r}"
    if is_allowlisted(hostname, safe_domains):
        return True, f"Domain is safe: {hostname}"
    return False, f"Domain is not in the allowlist: {hostname}"


def main() -> None:
    hook_input = Hook.read_stdin()
    url = hook_input.get("tool_input", {}).get("url", "")
    safe_domains = get_safe_domains()

    is_safe, message = validate_domain(url, safe_domains)
    if not is_safe:
        Hook.advanced_block("PreToolUse", message)
        return

    Hook.system_message(message)


if __name__ == "__main__":
    main()
