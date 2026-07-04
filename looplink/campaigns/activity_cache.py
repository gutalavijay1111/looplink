from django.core.cache import cache

from looplink.campaigns import selectors

RECENT_LIMIT = 10
CACHE_TTL = 60 * 60 * 24  # a day; cheap to recompute from Postgres on a miss/eviction


def _count_key(campaign_id):
    return f"campaign:{campaign_id}:enrollment_count"


def _recent_key(campaign_id):
    return f"campaign:{campaign_id}:recent_enrollments"


def _serialize(enrollment):
    return {
        "identity": enrollment.normalized_identity,
        "identity_type": enrollment.identity_type,
        "created_at": enrollment.created_at,
    }


def get_enrollment_count(campaign):
    key = _count_key(campaign.pk)
    count = cache.get(key)
    if count is None:
        count = selectors.enrollment_count(campaign)
        cache.set(key, count, timeout=CACHE_TTL)
    return count


def get_recent_enrollments(campaign, limit=RECENT_LIMIT):
    key = _recent_key(campaign.pk)
    recent = cache.get(key)
    if recent is None:
        recent = [_serialize(e) for e in selectors.recent_enrollments(campaign, limit=limit)]
        cache.set(key, recent, timeout=CACHE_TTL)
    return recent


def record_enrollment(campaign, enrollment):
    """
    Called only for a genuinely new enrollment (never for a recognized repeat),
    right after the DB write, to keep the cache from ever serving a stale count
    or list instead of falling back to Postgres on every read.
    """
    count_key = _count_key(campaign.pk)
    try:
        cache.incr(count_key)
    except ValueError:
        # Cold cache: prime it from Postgres, which already includes this row.
        cache.set(count_key, selectors.enrollment_count(campaign), timeout=CACHE_TTL)

    recent_key = _recent_key(campaign.pk)
    recent = cache.get(recent_key)
    if recent is None:
        cache.set(recent_key, [_serialize(e) for e in selectors.recent_enrollments(campaign)], timeout=CACHE_TTL)
    else:
        recent = [_serialize(enrollment), *recent][:RECENT_LIMIT]
        cache.set(recent_key, recent, timeout=CACHE_TTL)
