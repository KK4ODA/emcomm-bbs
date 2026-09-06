"""
Emcomm BBS - Emergency information sources

    EmergencyDataFetcher          NWS alerts, USGS earthquakes, FEMA declarations,
                                  NIFC wildfire counts
    SocialMediaEmergencyFetcher   Recent posts from official accounts on X (API v2)
    EmergencyResourcesFetcher     Static preparedness reference (phone numbers, kit list)

List-returning fetchers return ``[{'error': ...}]`` on failure so callers can
render the failure inline; dict-returning fetchers return ``{'error': ...}``.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from version import __version__

log = logging.getLogger(__name__)

USER_AGENT = f"EmcommBBS/{__version__} (+https://github.com/KK4ODA/emcomm-bbs)"
TIMEOUT = 15


class EmergencyDataFetcher:
    """Public government feeds. No API keys required."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT, 'Accept': 'application/json'})

    def get_all_emergency_data(self, user_state=None):
        return {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'nws_alerts': self.get_nws_alerts(user_state),
            'usgs_earthquakes': self.get_recent_earthquakes(),
            'fema_disasters': self.get_fema_disasters(),
            'fire_incidents': self.get_active_fires(),
        }

    def get_nws_alerts(self, state=None, limit=20):
        """Active NWS alerts, optionally filtered to a two-letter state code."""
        url = "https://api.weather.gov/alerts/active"
        params = {'area': state} if state else None
        try:
            r = self.session.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            features = r.json().get('features', [])
        except (requests.RequestException, ValueError) as exc:
            return [{'error': f"NWS: {exc}"}]

        alerts = []
        for feature in features[:limit]:
            props = feature.get('properties', {})
            alerts.append({
                'event': props.get('event'),
                'severity': props.get('severity'),
                'urgency': props.get('urgency'),
                'areas': props.get('areaDesc'),
                'headline': props.get('headline'),
                'description': (props.get('description') or '')[:1500],
                'effective': props.get('effective'),
                'expires': props.get('expires'),
            })
        return alerts

    def get_recent_earthquakes(self, limit=15):
        """M4.5+ earthquakes worldwide in the last 7 days (USGS)."""
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
        try:
            r = self.session.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            features = r.json().get('features', [])
        except (requests.RequestException, ValueError) as exc:
            return [{'error': f"USGS: {exc}"}]

        quakes = []
        for feature in features[:limit]:
            props = feature.get('properties', {})
            coords = feature.get('geometry', {}).get('coordinates', [])
            when = datetime.fromtimestamp((props.get('time') or 0) / 1000, tz=timezone.utc)
            quakes.append({
                'magnitude': props.get('mag'),
                'location': props.get('place'),
                'time': when.strftime('%Y-%m-%d %H:%M UTC'),
                'depth': round(coords[2]) if len(coords) > 2 and coords[2] is not None else None,
                'url': props.get('url'),
            })
        return quakes

    def get_fema_disasters(self, days=30, limit=20):
        """FEMA disaster declarations from the last ``days`` days."""
        url = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        params = {
            '$filter': f"declarationDate ge '{since}'",
            '$orderby': 'declarationDate desc',
            '$top': str(limit),
        }
        try:
            r = self.session.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            items = r.json().get('DisasterDeclarationsSummaries', [])
        except (requests.RequestException, ValueError) as exc:
            return [{'error': f"FEMA: {exc}"}]

        return [{
            'disaster_number': item.get('disasterNumber'),
            'state': item.get('state'),
            'declaration_type': item.get('declarationType'),
            'incident_type': item.get('incidentType'),
            'title': item.get('declarationTitle'),
            'date': (item.get('declarationDate') or '')[:10],
            'incident_begin': item.get('incidentBeginDate'),
        } for item in items]

    WFIGS_URL = ("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
                 "WFIGS_Incident_Locations_Current/FeatureServer/0/query")

    def get_active_fires(self, top=8, min_acres=100):
        """Current wildfire incidents from NIFC's WFIGS feed (no key needed).

        Returns the national count plus the ``top`` largest fires of at
        least ``min_acres`` acres.
        """
        try:
            r = self.session.get(self.WFIGS_URL, timeout=TIMEOUT, params={
                'where': "IncidentTypeCategory='WF'", 'returnCountOnly': 'true', 'f': 'json'})
            r.raise_for_status()
            count = int(r.json().get('count', 0))

            r = self.session.get(self.WFIGS_URL, timeout=TIMEOUT, params={
                'where': f"IncidentTypeCategory='WF' AND IncidentSize >= {int(min_acres)}",
                'outFields': 'IncidentName,POOState,POOCounty,IncidentSize,PercentContained',
                'orderByFields': 'IncidentSize DESC', 'resultRecordCount': int(top), 'f': 'json'})
            r.raise_for_status()
            features = r.json().get('features', [])
        except (requests.RequestException, ValueError) as exc:
            return {'error': f"NIFC WFIGS: {exc}"}

        largest = []
        for feature in features:
            a = feature.get('attributes', {})
            largest.append({
                'name': (a.get('IncidentName') or '').strip().title(),
                'state': (a.get('POOState') or '').replace('US-', ''),
                'county': a.get('POOCounty') or '',
                'acres': int(a.get('IncidentSize') or 0),
                'contained': a.get('PercentContained'),
            })
        return {
            'active_fires': count,
            'largest': largest,
            'message': f'{count} active wildfire incidents nationwide',
            'source': 'NIFC WFIGS',
            'url': 'https://data-nifc.opendata.arcgis.com/',
        }


class SocialMediaEmergencyFetcher:
    """Recent posts from official emergency accounts via the X API v2.

    Each account has a lookback window and result cap tuned to how often it
    posts, so high-volume accounts (NWS) don't crowd out rare but important
    ones (USGS big quakes).
    """

    DEFAULT_ACCOUNTS = [
        'NWS', 'fema', 'USGS_Quakes', 'NWSAlerts', 'CDCgov', 'NHC_Atlantic',
        'USGSBigQuakes', 'FBI', 'DHSgov', 'EPA', 'USCG', 'USNationalGuard',
    ]
    DEFAULT_STRATEGY = {'window_hours': 12, 'max_results': 10, 'priority': 'medium'}
    STRATEGIES = {
        'NWS':            {'window_hours': 6,  'max_results': 25, 'priority': 'critical'},
        'NWSAlerts':      {'window_hours': 6,  'max_results': 25, 'priority': 'critical'},
        'NHC_Atlantic':   {'window_hours': 8,  'max_results': 20, 'priority': 'critical'},
        'USGS_Quakes':    {'window_hours': 24, 'max_results': 20, 'priority': 'high'},
        'USGSBigQuakes':  {'window_hours': 48, 'max_results': 15, 'priority': 'high'},
        'fema':           {'window_hours': 12, 'max_results': 15, 'priority': 'high'},
        'CDCgov':         {'window_hours': 24, 'max_results': 10, 'priority': 'medium'},
        'DHSgov':         {'window_hours': 24, 'max_results': 10, 'priority': 'medium'},
        'FBI':            {'window_hours': 48, 'max_results': 5,  'priority': 'low'},
        'EPA':            {'window_hours': 48, 'max_results': 5,  'priority': 'low'},
        'USCG':           {'window_hours': 24, 'max_results': 8,  'priority': 'low'},
        'USNationalGuard': {'window_hours': 48, 'max_results': 5, 'priority': 'low'},
    }
    PRIORITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

    def __init__(self, bearer_token=None, custom_accounts=None):
        self.twitter_token = bearer_token
        self.emergency_accounts = list(custom_accounts) if custom_accounts else list(self.DEFAULT_ACCOUNTS)

    def get_emergency_tweets(self):
        """Return a priority-sorted list of tweets, or a dict describing why not."""
        if not self.twitter_token:
            return {
                'error': 'X API token not configured',
                'message': 'Add a bearer token in Settings to enable the feed',
            }

        headers = {'Authorization': f'Bearer {self.twitter_token}', 'User-Agent': USER_AGENT}
        tweets, errors = [], []
        for account in self.emergency_accounts:
            strategy = self.STRATEGIES.get(account, self.DEFAULT_STRATEGY)
            since = datetime.now(timezone.utc) - timedelta(hours=strategy['window_hours'])
            params = {
                'query': f'from:{account} -is:retweet',
                'start_time': since.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'max_results': strategy['max_results'],
                'tweet.fields': 'created_at,text',
            }
            try:
                r = requests.get(self.SEARCH_URL, headers=headers, params=params, timeout=TIMEOUT)
            except requests.RequestException as exc:
                errors.append(f"{account}: {exc}")
                continue

            if r.status_code == 401:
                errors.append("Authentication failed - check the bearer token")
                break
            if r.status_code == 429:
                errors.append("Rate limit exceeded - try again later")
                break
            if r.status_code != 200:
                errors.append(f"{account}: HTTP {r.status_code}")
                continue

            for tweet in r.json().get('data', []):
                text = tweet.get('text', '')
                if not text:
                    continue
                created = tweet.get('created_at', '')
                tweets.append({
                    'account': account,
                    'text': text,
                    'created_at': created,
                    'age_hours': self._age_hours(created),
                    'priority': strategy['priority'],
                })
            time.sleep(0.5)   # be polite to the rate limiter

        if tweets:
            tweets.sort(key=lambda t: (self.PRIORITY_ORDER.get(t['priority'], 2), t['age_hours']))
            return tweets
        if errors:
            return {'error': 'Failed to retrieve tweets', 'details': errors,
                    'message': 'Check token and rate limits at developer.x.com'}
        return {'message': 'No recent posts from the monitored accounts'}

    @staticmethod
    def _age_hours(created_at):
        if not created_at:
            return 999.0
        try:
            posted = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except ValueError:
            return 999.0
        return (datetime.now(timezone.utc) - posted).total_seconds() / 3600


class EmergencyResourcesFetcher:
    """Static preparedness reference used by the console checker."""

    @staticmethod
    def get_emergency_resources():
        return {
            'emergency_contacts': {
                '911': 'Fire, Medical, Police Emergency',
                '311': 'Non-emergency city services',
                '1-800-222-1222': 'Poison Control',
                '1-800-985-5990': 'Disaster Distress Helpline',
                '1-800-733-2767': 'American Red Cross',
            },
            'supply_checklist': [
                'Water (1 gallon per person per day for 3 days)',
                'Non-perishable food (3-day supply)',
                'Battery or hand-crank radio',
                'Flashlight and extra batteries',
                'First aid kit',
                'Whistle for signaling',
                'Dust masks or N95 respirators',
                'Plastic sheeting and duct tape',
                'Moist towelettes and garbage bags',
                'Wrench or pliers (to turn off utilities)',
                'Manual can opener',
                'Local maps',
                'Cell phone with chargers and backup battery',
            ],
        }
