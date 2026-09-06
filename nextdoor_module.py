"""
Emcomm BBS - Nextdoor integration

Fetches neighborhood posts for a set of ZIP codes and ranks them by urgency.

NOTE: Nextdoor has no general public API. This module targets the Public
Agency API (https://nextdoor.com/agency/), which requires a verified
government or public-safety organisation. The endpoint shape below is a
best guess and must be adapted to the documentation you receive with
your credentials.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import requests

log = logging.getLogger(__name__)

URGENCY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}


class NextdoorFetcher:

    BASE_URL = "https://api.nextdoor.com/v2"   # placeholder - see module docstring
    TIMEOUT = 15

    # category -> lookback window, result cap, urgency bucket
    STRATEGIES = {
        'urgent_alert':       {'window_hours': 6,  'max_results': 20, 'urgency': 'critical'},
        'crime_safety':       {'window_hours': 12, 'max_results': 15, 'urgency': 'high'},
        'lost_found':         {'window_hours': 24, 'max_results': 10, 'urgency': 'high'},
        'general_crime':      {'window_hours': 24, 'max_results': 10, 'urgency': 'medium'},
        'emergency_planning': {'window_hours': 48, 'max_results': 8,  'urgency': 'medium'},
        'local_news':         {'window_hours': 24, 'max_results': 5,  'urgency': 'low'},
        'recommendations':    {'window_hours': 48, 'max_results': 5,  'urgency': 'low'},
    }

    CRITICAL_KEYWORDS = (
        'fire', 'shooting', 'robbery', 'break-in', 'assault', 'suspicious person',
        'active shooter', 'police activity', 'evacuate', 'shelter in place', 'emergency', 'danger',
    )
    HIGH_KEYWORDS = (
        'burglary', 'theft', 'stolen', 'vandalism', 'missing person', 'lost pet', 'found pet',
        'suspicious vehicle', 'scam', 'power outage', 'gas leak', 'flood', 'accident',
    )

    def __init__(self, api_key=None, zip_codes=None):
        self.api_key = api_key
        self.zip_codes = list(zip_codes or [])

    def get_local_posts(self):
        """Urgency-sorted list of posts, or a dict describing why none were fetched."""
        if not self.api_key:
            return {'error': 'Nextdoor API key not configured',
                    'message': 'Public Agency API access is required (nextdoor.com/agency)'}
        if not self.zip_codes:
            return {'error': 'No ZIP codes configured',
                    'message': 'Add ZIP codes to monitor in Settings'}

        headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}
        posts, errors = [], []
        for zip_code in self.zip_codes:
            for category, strategy in self.STRATEGIES.items():
                try:
                    posts.extend(self._fetch(zip_code, category, strategy, headers))
                except requests.RequestException as exc:
                    errors.append(f"ZIP {zip_code} {category}: {exc}")
            time.sleep(0.5)

        if posts:
            posts.sort(key=lambda p: (URGENCY_ORDER.get(p['urgency'], 2), p['age_hours']))
            return posts
        if errors:
            return {'error': 'Failed to retrieve posts', 'details': errors}
        return {'message': 'No recent posts in monitored areas', 'zip_codes': self.zip_codes}

    def _fetch(self, zip_code, category, strategy, headers):
        since = datetime.now(timezone.utc) - timedelta(hours=strategy['window_hours'])
        params = {
            'zip_code': zip_code,
            'category': category,
            'start_time': since.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'max_results': strategy['max_results'],
            'sort': 'recent',
        }
        r = requests.get(f"{self.BASE_URL}/posts/search", headers=headers, params=params,
                         timeout=self.TIMEOUT)
        if r.status_code != 200:
            log.warning("Nextdoor %s/%s: HTTP %s", zip_code, category, r.status_code)
            return []

        results = []
        for post in r.json().get('posts', []):
            text = post.get('text', '')
            if not text:
                continue
            created = post.get('created_at', '')
            results.append({
                'zip_code': zip_code,
                'category': category,
                'text': text,
                'author': post.get('author', {}).get('name', 'Unknown'),
                'created_at': created,
                'age_hours': self._age_hours(created),
                'urgency': self.classify(text, strategy['urgency']),
            })
        return results

    @classmethod
    def classify(cls, text, default):
        """Escalate a post's urgency when its text contains alarm keywords."""
        lowered = text.lower()
        if any(k in lowered for k in cls.CRITICAL_KEYWORDS):
            return 'critical'
        if any(k in lowered for k in cls.HIGH_KEYWORDS) and URGENCY_ORDER.get(default, 2) > 1:
            return 'high'
        return default

    @staticmethod
    def _age_hours(created_at):
        if not created_at:
            return 999.0
        try:
            posted = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except ValueError:
            return 999.0
        return (datetime.now(timezone.utc) - posted).total_seconds() / 3600

    @staticmethod
    def get_statistics(posts):
        if not isinstance(posts, list):
            return None
        stats = {'total_posts': len(posts), 'by_urgency': {}, 'by_zip': {}, 'by_category': {}}
        for post in posts:
            for bucket, key in (('by_urgency', 'urgency'), ('by_zip', 'zip_code'), ('by_category', 'category')):
                value = post.get(key, 'unknown')
                stats[bucket][value] = stats[bucket].get(value, 0) + 1
        return stats
