"""Safe redirect validation — prevents open redirect via `next` parameter."""

from urllib.parse import urlparse


def safe_next_url(next_url, default='/cron_list'):
    """Return *next_url* only if it is a safe relative path.

    Rejects absolute URLs (``https://evil.com``), protocol-relative URLs
    (``//evil.com``), and ``javascript:`` schemes.  Returns *default* for
    any value that fails the check.
    """
    if not next_url:
        return default
    parsed = urlparse(next_url)
    if parsed.scheme or parsed.netloc or next_url.startswith('//'):
        return default
    return next_url
