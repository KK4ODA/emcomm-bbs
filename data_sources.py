"""
Emcomm BBS - Data sources

Every network fetcher used by the bulletin generator lives here so the GUI
module only has to orchestrate them:

    WeatherFetcher        NWS 7-day forecasts for major cities by FEMA region
    SpaceWeatherFetcher   NOAA SWPC solar indices, K-index, HF band estimate
    NewsSummarizer        BBC / NPR headlines via RSS, optional Claude summary
    PowerOutageFetcher    DOE / ORNL ODIN live outage counts by utility & state

All fetchers return plain dicts / lists and never raise for network failures;
callers check for an ``error`` key or an empty result instead.
"""

import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

from version import __version__ as APP_VERSION

log = logging.getLogger(__name__)

# NWS requires a descriptive User-Agent with a contact point.
USER_AGENT = f"EmcommBBS/{APP_VERSION} (+https://github.com/KK4ODA/emcomm-bbs)"
DEFAULT_TIMEOUT = 15


def _session():
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

FEMA_REGIONS = {
    1: "Region 1 (New England): CT, MA, ME, NH, RI, VT",
    2: "Region 2 (New York/New Jersey): NJ, NY, PR, VI",
    3: "Region 3 (Mid-Atlantic): DC, DE, MD, PA, VA, WV",
    4: "Region 4 (Southeast): AL, FL, GA, KY, MS, NC, SC, TN",
    5: "Region 5 (Midwest): IL, IN, MI, MN, OH, WI",
    6: "Region 6 (South): AR, LA, NM, OK, TX",
    7: "Region 7 (Great Plains): IA, KS, MO, NE",
    8: "Region 8 (Rocky Mountains): CO, MT, ND, SD, UT, WY",
    9: "Region 9 (Southwest/Pacific): AZ, CA, HI, NV, Guam",
    10: "Region 10 (Northwest): AK, ID, OR, WA",
}

# Short labels for the GUI.
FEMA_REGION_LABELS = {
    1: "R1  Northeast",
    2: "R2  NY / NJ",
    3: "R3  Mid-Atlantic",
    4: "R4  Southeast",
    5: "R5  Midwest",
    6: "R6  South Central",
    7: "R7  Great Plains",
    8: "R8  Mountain",
    9: "R9  Southwest",
    10: "R10 Northwest",
}

# 'City, ST': (latitude, longitude, FEMA region). Two or three cities per
# state - the largest plus the capital.
MAJOR_US_CITIES = {
    'Birmingham, AL': (33.5186, -86.8104, 4),
    'Montgomery, AL': (32.3792, -86.3077, 4),
    'Anchorage, AK': (61.2181, -149.9003, 10),
    'Juneau, AK': (58.3019, -134.4197, 10),
    'Phoenix, AZ': (33.4484, -112.0740, 9),
    'Tucson, AZ': (32.2226, -110.9747, 9),
    'Little Rock, AR': (34.7465, -92.2896, 6),
    'Fort Smith, AR': (35.3859, -94.3985, 6),
    'Los Angeles, CA': (34.0522, -118.2437, 9),
    'San Diego, CA': (32.7157, -117.1611, 9),
    'San Jose, CA': (37.3382, -121.8863, 9),
    'San Francisco, CA': (37.7749, -122.4194, 9),
    'Fresno, CA': (36.7378, -119.7871, 9),
    'Sacramento, CA': (38.5816, -121.4944, 9),
    'Denver, CO': (39.7392, -104.9903, 8),
    'Colorado Springs, CO': (38.8339, -104.8214, 8),
    'Bridgeport, CT': (41.1865, -73.1952, 1),
    'Hartford, CT': (41.7658, -72.6734, 1),
    'Wilmington, DE': (39.7391, -75.5398, 3),
    'Dover, DE': (39.1582, -75.5244, 3),
    'Jacksonville, FL': (30.3322, -81.6557, 4),
    'Miami, FL': (25.7617, -80.1918, 4),
    'Tampa, FL': (27.9506, -82.4572, 4),
    'Orlando, FL': (28.5383, -81.3792, 4),
    'Tallahassee, FL': (30.4383, -84.2807, 4),
    'Atlanta, GA': (33.7490, -84.3880, 4),
    'Augusta, GA': (33.4735, -82.0105, 4),
    'Honolulu, HI': (21.3099, -157.8581, 9),
    'Hilo, HI': (19.7070, -155.0835, 9),
    'Boise, ID': (43.6150, -116.2023, 10),
    'Meridian, ID': (43.6121, -116.3915, 10),
    'Chicago, IL': (41.8781, -87.6298, 5),
    'Springfield, IL': (39.7817, -89.6501, 5),
    'Indianapolis, IN': (39.7684, -86.1581, 5),
    'Fort Wayne, IN': (41.0793, -85.1394, 5),
    'Des Moines, IA': (41.5868, -93.6250, 7),
    'Cedar Rapids, IA': (41.9779, -91.6656, 7),
    'Wichita, KS': (37.6872, -97.3301, 7),
    'Topeka, KS': (39.0558, -95.6890, 7),
    'Louisville, KY': (38.2527, -85.7585, 4),
    'Lexington, KY': (38.0406, -84.5037, 4),
    'New Orleans, LA': (29.9511, -90.0715, 6),
    'Baton Rouge, LA': (30.4515, -91.1871, 6),
    'Portland, ME': (43.6591, -70.2568, 1),
    'Augusta, ME': (44.3106, -69.7795, 1),
    'Baltimore, MD': (39.2904, -76.6122, 3),
    'Annapolis, MD': (38.9784, -76.4922, 3),
    'Boston, MA': (42.3601, -71.0589, 1),
    'Worcester, MA': (42.2626, -71.8023, 1),
    'Detroit, MI': (42.3314, -83.0458, 5),
    'Grand Rapids, MI': (42.9634, -85.6681, 5),
    'Minneapolis, MN': (44.9778, -93.2650, 5),
    'St. Paul, MN': (44.9537, -93.0900, 5),
    'Jackson, MS': (32.2988, -90.1848, 4),
    'Gulfport, MS': (30.3674, -89.0928, 4),
    'Kansas City, MO': (39.0997, -94.5786, 7),
    'St. Louis, MO': (38.6270, -90.1994, 7),
    'Billings, MT': (45.7833, -108.5007, 8),
    'Helena, MT': (46.5891, -112.0391, 8),
    'Omaha, NE': (41.2565, -95.9345, 7),
    'Lincoln, NE': (40.8136, -96.7026, 7),
    'Las Vegas, NV': (36.1699, -115.1398, 9),
    'Reno, NV': (39.5296, -119.8138, 9),
    'Manchester, NH': (42.9956, -71.4548, 1),
    'Concord, NH': (43.2081, -71.5376, 1),
    'Newark, NJ': (40.7357, -74.1724, 2),
    'Jersey City, NJ': (40.7178, -74.0431, 2),
    'Albuquerque, NM': (35.0844, -106.6504, 6),
    'Santa Fe, NM': (35.6870, -105.9378, 6),
    'New York, NY': (40.7128, -74.0060, 2),
    'Buffalo, NY': (42.8864, -78.8784, 2),
    'Albany, NY': (42.6526, -73.7562, 2),
    'Charlotte, NC': (35.2271, -80.8431, 4),
    'Raleigh, NC': (35.7796, -78.6382, 4),
    'Fargo, ND': (46.8772, -96.7898, 8),
    'Bismarck, ND': (46.8083, -100.7837, 8),
    'Columbus, OH': (39.9612, -82.9988, 5),
    'Cleveland, OH': (41.4993, -81.6944, 5),
    'Cincinnati, OH': (39.1031, -84.5120, 5),
    'Oklahoma City, OK': (35.4676, -97.5164, 6),
    'Tulsa, OK': (36.1540, -95.9928, 6),
    'Portland, OR': (45.5152, -122.6784, 10),
    'Salem, OR': (44.9429, -123.0351, 10),
    'Philadelphia, PA': (39.9526, -75.1652, 3),
    'Pittsburgh, PA': (40.4406, -79.9959, 3),
    'Harrisburg, PA': (40.2732, -76.8867, 3),
    'Providence, RI': (41.8240, -71.4128, 1),
    'Warwick, RI': (41.7001, -71.4162, 1),
    'Columbia, SC': (34.0007, -81.0348, 4),
    'Charleston, SC': (32.7765, -79.9311, 4),
    'Sioux Falls, SD': (43.5446, -96.7311, 8),
    'Pierre, SD': (44.3683, -100.3510, 8),
    'Nashville, TN': (36.1627, -86.7816, 4),
    'Memphis, TN': (35.1495, -90.0490, 4),
    'Houston, TX': (29.7604, -95.3698, 6),
    'San Antonio, TX': (29.4241, -98.4936, 6),
    'Dallas, TX': (32.7767, -96.7970, 6),
    'Austin, TX': (30.2672, -97.7431, 6),
    'Fort Worth, TX': (32.7555, -97.3308, 6),
    'El Paso, TX': (31.7619, -106.4850, 6),
    'Salt Lake City, UT': (40.7608, -111.8910, 8),
    'Provo, UT': (40.2338, -111.6585, 8),
    'Burlington, VT': (44.4759, -73.2121, 1),
    'Montpelier, VT': (44.2601, -72.5754, 1),
    'Virginia Beach, VA': (36.8529, -75.9780, 3),
    'Richmond, VA': (37.5407, -77.4360, 3),
    'Seattle, WA': (47.6062, -122.3321, 10),
    'Spokane, WA': (47.6588, -117.4260, 10),
    'Olympia, WA': (47.0379, -122.9007, 10),
    'Charleston, WV': (38.3498, -81.6326, 3),
    'Huntington, WV': (38.4192, -82.4452, 3),
    'Milwaukee, WI': (43.0389, -87.9065, 5),
    'Madison, WI': (43.0731, -89.4012, 5),
    'Cheyenne, WY': (41.1400, -104.8202, 8),
    'Casper, WY': (42.8500, -106.3250, 8),
}


# ---------------------------------------------------------------------------
# Weather (NWS)
# ---------------------------------------------------------------------------

class WeatherFetcher:
    """7-day forecasts from api.weather.gov for the cities in MAJOR_US_CITIES."""

    BASE_URL = "https://api.weather.gov"
    MAX_WORKERS = 4          # NWS tolerates modest concurrency
    PERIODS = 14             # 7 days = 14 day/night periods

    def __init__(self):
        self.session = _session()

    def get_forecast(self, lat, lon, city_name, fema_region):
        """Return {'city', 'fema_region', 'forecast': [periods]} or None."""
        try:
            point = self.session.get(f"{self.BASE_URL}/points/{lat},{lon}",
                                     timeout=DEFAULT_TIMEOUT)
            point.raise_for_status()
            forecast_url = point.json()['properties']['forecast']

            forecast = self.session.get(forecast_url, timeout=DEFAULT_TIMEOUT)
            forecast.raise_for_status()
            periods = forecast.json()['properties']['periods'][:self.PERIODS]
            return {
                'city': city_name,
                'fema_region': fema_region,
                'current': periods[0] if periods else None,
                'forecast': periods,
            }
        except (requests.RequestException, KeyError, ValueError) as exc:
            log.warning("NWS forecast failed for %s: %s", city_name, exc)
            return None

    def get_all_forecasts(self, selected_regions=None, log_callback=None, stop_event=None):
        """Fetch forecasts for every city in the selected FEMA regions.

        Returns {region_number: [forecast, ...]} in MAJOR_US_CITIES order.
        ``stop_event`` (threading.Event) aborts the run early when set.
        """
        if selected_regions is None:
            selected_regions = list(range(1, 11))
        selected = set(selected_regions)

        cities = [(city, loc) for city, loc in MAJOR_US_CITIES.items() if loc[2] in selected]
        results = {r: [] for r in selected_regions}
        total = len(cities)
        if log_callback:
            log_callback(f"Fetching weather for {total} cities in {len(selected)} region(s)...")

        def worker(item):
            city, (lat, lon, region) = item
            if stop_event is not None and stop_event.is_set():
                return None
            return self.get_forecast(lat, lon, city, region)

        done = 0
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as pool:
            for forecast in pool.map(worker, cities):
                done += 1
                if forecast:
                    results[forecast['fema_region']].append(forecast)
                if log_callback and (done % 5 == 0 or done == total):
                    log_callback(f"  {done}/{total} cities done")
        return results


# ---------------------------------------------------------------------------
# Space weather (NOAA SWPC)
# ---------------------------------------------------------------------------

class SpaceWeatherFetcher:
    """Solar flux, sunspot number, K/A index and an HF band-condition estimate."""

    BASE_URL = "https://services.swpc.noaa.gov"

    # Planetary K -> approximate A index (standard conversion table).
    _K_TO_A = [(1, 2), (2, 6), (3, 12), (4, 22), (5, 40), (6, 70), (7, 120), (8, 200)]

    FALLBACK_BANDS = {
        '80m': 'Good', '40m': 'Good', '30m': 'Good', '20m': 'Good',
        '17m': 'Fair', '15m': 'Fair', '12m': 'Fair', '10m': 'Fair',
    }

    def __init__(self):
        self.session = _session()

    def _get_json(self, path):
        try:
            r = self.session.get(f"{self.BASE_URL}{path}", timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            log.warning("SWPC %s failed: %s", path, exc)
            return None

    def get_conditions(self):
        conditions = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'solar_flux': None,
            'sunspot_number': None,
            'a_index': None,
            'k_index': None,
            'forecast': '',
        }

        indices = self._get_json("/json/solar-cycle/observed-solar-cycle-indices.json")
        if indices:
            latest = indices[-1]
            conditions['solar_flux'] = latest.get('f10.7')
            conditions['sunspot_number'] = latest.get('ssn')

        kp = self._get_json("/json/planetary_k_index_1m.json")
        if kp:
            latest = kp[-1]
            conditions['k_index'] = latest.get('kp_index', latest.get('kp', latest.get('k_index')))

        k = _to_float(conditions['k_index'])
        if k is not None:
            conditions['a_index'] = next((a for limit, a in self._K_TO_A if k < limit), 300)

        try:
            r = self.session.get(f"{self.BASE_URL}/text/3-day-forecast.txt",
                                 timeout=DEFAULT_TIMEOUT)
            if r.ok:
                conditions['forecast'] = r.text[:3000]
        except requests.RequestException as exc:
            log.warning("SWPC 3-day forecast failed: %s", exc)

        conditions['band_conditions'] = self.estimate_bands(
            _to_float(conditions['solar_flux']), k)
        return conditions

    @classmethod
    def estimate_bands(cls, sfi, k):
        """Rough HF band conditions from solar flux (SFI) and planetary K."""
        if sfi is None or k is None:
            return dict(cls.FALLBACK_BANDS)
        if k <= 2:      # quiet
            return {
                '80m': 'Good', '40m': 'Good', '30m': 'Good',
                '20m': 'Excellent' if sfi > 100 else 'Good',
                '17m': 'Excellent' if sfi > 100 else 'Good',
                '15m': 'Excellent' if sfi > 120 else 'Good',
                '12m': 'Good' if sfi > 120 else 'Fair',
                '10m': 'Excellent' if sfi > 150 else 'Good' if sfi > 100 else 'Fair',
            }
        if k <= 4:      # unsettled
            return {
                '80m': 'Good', '40m': 'Fair', '30m': 'Fair',
                '20m': 'Good' if sfi > 100 else 'Fair',
                '17m': 'Fair', '15m': 'Fair', '12m': 'Fair',
                '10m': 'Fair' if sfi > 100 else 'Poor',
            }
        return {        # disturbed
            '80m': 'Fair', '40m': 'Fair', '30m': 'Poor', '20m': 'Poor',
            '17m': 'Poor', '15m': 'Poor', '12m': 'Poor', '10m': 'Poor',
        }


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

class RssSource:
    """Headlines from an RSS feed. Far more stable than scraping front pages,
    which increasingly block automated clients."""

    def __init__(self, name, url):
        self.name = name
        self.url = url

    def fetch_headlines(self, max_articles=15):
        try:
            r = requests.get(self.url, headers={'User-Agent': USER_AGENT}, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except (requests.RequestException, ET.ParseError) as exc:
            log.warning("News fetch failed for %s: %s", self.name, exc)
            return []

        headlines = []
        for item in root.iter('item'):
            title = " ".join((item.findtext('title') or '').split())
            if title and title not in headlines:
                headlines.append(title)
                if len(headlines) >= max_articles:
                    break
        return headlines


NEWS_SOURCES = [
    RssSource("BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
    RssSource("NPR News", "https://feeds.npr.org/1001/rss.xml"),
]

CLAUDE_MODEL = "claude-opus-5"

SUMMARY_SYSTEM_PROMPT = (
    "You write situational-awareness news digests that are transmitted over "
    "low-bandwidth amateur radio links. Output plain text only: no markdown, "
    "no headings, no bullet symbols. Keep it under 220 words."
)


class NewsSummarizer:
    """Fetch headlines and, when an Anthropic key is present, summarize them."""

    def __init__(self, api_key=None, sources=None):
        self.api_key = api_key or None
        self.sources = sources or NEWS_SOURCES

    def set_api_key(self, api_key):
        self.api_key = api_key or None

    def fetch_all_news(self):
        return {source.name: source.fetch_headlines() for source in self.sources}

    def generate_summary(self, news_data):
        if not self.api_key:
            return self._basic_summary(news_data)
        try:
            return self._claude_summary(news_data)
        except ImportError:
            return ("[AI summary unavailable: 'anthropic' package not installed]\n\n"
                    + self._basic_summary(news_data))
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator in the bulletin
            log.warning("Claude summary failed: %s", exc)
            return f"[AI summary unavailable: {exc}]\n\n" + self._basic_summary(news_data)

    def _claude_summary(self, news_data):
        import anthropic  # optional dependency, imported lazily

        news_text = "\n".join(
            f"\n{source}:\n" + "\n".join(f"{i}. {h}" for i, h in enumerate(headlines, 1))
            for source, headlines in news_data.items()
        )
        prompt = (
            "Summarize today's top stories from these headlines. Give a short "
            "overview of the most important developments, then note any "
            "emerging themes or developing situations relevant to public "
            f"safety.\n\nHeadlines:{news_text}"
        )
        client = anthropic.Anthropic(api_key=self.api_key)
        try:
            response = client.beta.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1500,
                system=SUMMARY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError:
            raise RuntimeError("Anthropic API key was rejected") from None
        except anthropic.RateLimitError:
            raise RuntimeError("Anthropic rate limit reached, try again later") from None
        except anthropic.APIConnectionError:
            raise RuntimeError("could not reach the Anthropic API") from None

        if response.stop_reason == "refusal":
            raise RuntimeError("the model declined to summarize this content")
        return "".join(block.text for block in response.content if block.type == "text").strip()

    @staticmethod
    def _basic_summary(news_data):
        total = sum(len(h) for h in news_data.values())
        sources = ", ".join(news_data.keys())
        return (f"Headline digest from {sources}: {total} headlines retrieved.\n"
                "Set an Anthropic API key in Settings for an AI-written summary.")


# ---------------------------------------------------------------------------
# Power outages (DOE / ORNL ODIN)
# ---------------------------------------------------------------------------

class PowerOutageFetcher:
    """Live outage counts from ODIN, enriched with a utility -> state lookup."""

    STATUS_URL = "https://odin.ornl.gov/odi/status"
    TOP_UTILITIES = 15

    # EIA utility ID -> primary state, built from EIA Form 861 and
    # cross-referenced against ODIN participants.
    EIA_STATE_LOOKUP = {
        "14354": "UT", "17609": "CA", "8319": "IA", "9991": "MN",
        "329": "IA", "17040": "IL", "19157": "MN", "15248": "OR",
        "5417": "WI", "6894": "SC", "14653": "WA", "11011": "KY",
        "16368": "MN", "12227": "MN", "2652": "IA", "15257": "CO",
        "3644": "WA", "12341": "IA", "13700": "MN", "3502": "FL",
        "155": "MN", "1884": "MN", "19791": "VT", "15500": "WA",
        "4346": "MN", "7887": "GA", "3597": "PA", "22355": "WA",
        "10799": "TN", "9837": "NC", "8773": "CO", "4442": "WA",
        "40220": "IL", "38084": "MI", "5326": "WA", "19820": "KS",
        "19189": "AZ", "13651": "KY", "5961": "TN", "24590": "NH",
        "1613": "SC", "14468": "MN", "20169": "WA", "18448": "WA",
        "4265": "NM", "15845": "MN", "3249": "NY", "3264": "OR",
        "26939": "ND", "59013": "WA", "11804": "NY", "6782": "MN",
        "14349": "ME", "13762": "VA", "803": "AZ", "13573": "MA",
        "19981": "NC", "18957": "NC", "19108": "NC", "18339": "NC",
        "17572": "NC", "16101": "NC", "16496": "NC", "15671": "NC",
        "8333": "NC", "7978": "NC", "14717": "NC", "21632": "NC",
        "6784": "NC", "6640": "NC", "5656": "NC", "3250": "NC",
        "3107": "NC", "240": "NC", "2982": "NC", "19499": "CO",
        "8901": "TX", "5487": "PA", "8796": "MA", "13839": "MA",
        "16868": "WA", "12546": "MN", "12377": "MI", "20639": "MN",
        "2641": "KS", "12470": "TN", "19156": "WY", "17267": "SD",
        "1251": "WI", "4041": "WA", "22822": "IN", "10000": "KS",
        "9575": "KY", "13684": "MN", "14170": "WA", "10618": "MN",
        "12692": "MT", "1579": "WA", "5327": "OR", "5574": "MN",
        "16382": "NE", "577": "TN", "3739": "ID", "11910": "MN",
        "19547": "HI", "14716": "PA", "20387": "PA", "18997": "OH",
        "15263": "MD", "21081": "CO", "14711": "PA", "13998": "OH",
        "12796": "WV", "12390": "PA", "9726": "NJ", "3755": "OH",
        "5862": "CO", "10539": "CO", "17470": "WA", "24889": "NC",
        "13550": "OR", "3293": "WI", "25177": "MN", "18019": "MN",
        "12651": "MN", "7460": "MN", "7559": "TX", "15419": "WA",
        "13758": "ID", "5202": "AL", "11291": "NC", "10697": "MN",
        "12929": "IN", "4743": "OR", "20996": "MN", "15023": "NC",
        "5070": "DE", "9336": "CO", "19266": "TN", "1889": "NC",
        "1529": "MN", "13955": "FL", "8786": "SC", "15507": "TN",
        "12988": "TN", "3413": "GA", "7140": "FL", "6452": "FL",
        "3366": "IN", "3265": "OH", "3257": "KY", "18642": "NC",
        "5416": "NC", "9417": "IL", "1228": "MO", "14232": "MO",
        "9516": "MI", "12427": "MI", "11371": "MN", "19545": "CO",
        "18454": "NM", "4716": "WI", "20856": "WI", "6186": "OR",
        "18195": "ID", "5701": "AZ", "11070": "AZ", "13610": "NV",
        "19561": "NV", "14328": "CA", "17260": "CA", "7367": "CT",
        "8192": "MA", "195": "AL", "11241": "LA", "13478": "MS",
        "16572": "MS", "11957": "TX", "22500": "GA", "17543": "TX",
        "4169": "MN", "30151": "MN", "14348": "WA", "14647": "WA",
        "30844": "OR", "20382": "PA", "31568": "OH", "6127": "PA",
        "40229": "MI", "17718": "TX", "1430": "WA",
    }

    _STATE_NAMES = {
        'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
        'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
        'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'HAWAIIAN': 'HI', 'IDAHO': 'ID',
        'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
        'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
        'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
        'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
        'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
        'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
        'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'PENN': 'PA', 'RHODE ISLAND': 'RI',
        'SOUTH CAROLINA': 'SC', 'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX',
        'UTAH': 'UT', 'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA',
        'WEST VIRGINIA': 'WV', 'WISCONSIN': 'WI', 'WYOMING': 'WY',
        'PUGET': 'WA', 'SAN DIEGO': 'CA', 'SOUTHERN CALIFORNIA': 'CA',
        'PACIFIC GAS': 'CA', 'NEW ENGLAND': 'MA', 'CHESAPEAKE': 'VA',
    }
    # Longest names first so "WEST VIRGINIA" wins over "VIRGINIA".
    _NAME_PATTERN = re.compile(
        r'\b(' + '|'.join(sorted(map(re.escape, _STATE_NAMES), key=len, reverse=True)) + r')\b'
    )
    _SUFFIX_PATTERN = re.compile(r'\(([A-Z]{2})\)$')

    def __init__(self):
        self.session = _session()

    @classmethod
    def get_state(cls, eia_id, name):
        """Two-letter state for a utility, or None when it cannot be inferred."""
        state = cls.EIA_STATE_LOOKUP.get(str(eia_id))
        if state:
            return state
        name_upper = (name or '').upper()
        m = cls._SUFFIX_PATTERN.search(name_upper)
        if m:
            return m.group(1)
        m = cls._NAME_PATTERN.search(name_upper)
        return cls._STATE_NAMES[m.group(1)] if m else None

    def get_outages(self, log_callback=None):
        result = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'total_outages': 0,
            'utility_count': 0,
            'utilities_with_outages': 0,
            'top_utilities': [],
            'states': [],
            'national_summary': '',
            'error': None,
        }
        try:
            if log_callback:
                log_callback("  Querying ODIN (odin.ornl.gov)...")
            resp = self.session.get(self.STATUS_URL, timeout=20)
            resp.raise_for_status()
            self._parse_response(resp.json(), result)
            if log_callback:
                log_callback(f"  ODIN: {result['total_outages']:,} outages across "
                             f"{result['utilities_with_outages']} utilities "
                             f"in {len(result['states'])} states")
        except requests.Timeout:
            result['error'] = "ODIN request timed out after 20s"
        except (requests.RequestException, ValueError) as exc:
            result['error'] = f"ODIN request failed: {exc}"
        if result['error'] and log_callback:
            log_callback(f"  {result['error']}")
        return result

    def _parse_response(self, data, result):
        if not isinstance(data, list):
            result['error'] = "Unexpected response format from ODIN"
            return

        state_totals = {}
        with_outages = []
        total = 0
        for utility in data:
            outages = int(utility.get('totalOutages') or 0)
            name = utility.get('name', 'Unknown')
            state = self.get_state(utility.get('eiaId', ''), name)
            total += outages
            if outages <= 0:
                continue
            with_outages.append({
                'name': name,
                'outages': outages,
                'state': state or '??',
                'resolution': utility.get('dataResolution', ''),
            })
            if state:
                bucket = state_totals.setdefault(state, {'outages': 0, 'utilities': 0})
                bucket['outages'] += outages
                bucket['utilities'] += 1

        with_outages.sort(key=lambda u: u['outages'], reverse=True)
        states = sorted(
            ({'state': s, **v} for s, v in state_totals.items()),
            key=lambda s: s['outages'], reverse=True,
        )

        result.update(
            total_outages=total,
            utility_count=len(data),
            utilities_with_outages=len(with_outages),
            top_utilities=with_outages[:self.TOP_UTILITIES],
            states=states,
        )
        if total > 0:
            top = ', '.join(f"{s['state']} ({s['outages']:,})" for s in states[:4])
            result['national_summary'] = (
                f"{total:,} active outages across {len(with_outages)} utilities "
                f"in {len(states)} states. Most affected: {top}."
            )
        else:
            result['national_summary'] = (
                f"No significant outages reported across {len(data)} monitored utilities."
            )


# ---------------------------------------------------------------------------
# VarMap (companion app) - stations heard on VarAC
# ---------------------------------------------------------------------------

class VarMapUnavailable(Exception):
    """VarMap is not running, or not reachable at the configured URL."""


class VarMapClient:
    """Reads the station list from a running VarMap (github.com/KK4ODA/VarMap).

    VarMap serves JSON on localhost only. Every method raises
    ``VarMapUnavailable`` with an operator-readable message when it cannot
    be reached, so callers can skip the bulletin quietly.
    """

    DEFAULT_URL = "http://127.0.0.1:5001"

    def __init__(self, base_url=None, timeout=5):
        self.base_url = (base_url or self.DEFAULT_URL).strip().rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            self.base_url = "http://" + self.base_url
        self.timeout = timeout

    def _get(self, path):
        try:
            r = requests.get(f"{self.base_url}{path}", timeout=self.timeout,
                             headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            r.raise_for_status()
            return r.json()
        except requests.ConnectionError as exc:
            raise VarMapUnavailable(f"VarMap is not running at {self.base_url}") from exc
        except requests.Timeout as exc:
            raise VarMapUnavailable(f"VarMap at {self.base_url} did not answer within {self.timeout}s") from exc
        except (requests.RequestException, ValueError) as exc:
            raise VarMapUnavailable(f"VarMap at {self.base_url}: {exc}") from exc

    def health(self):
        """VarMap's /api/health: version, VarAC state, own station, counts."""
        data = self._get("/api/health")
        if not isinstance(data, dict) or "version" not in data:
            raise VarMapUnavailable(f"{self.base_url} answered, but it is not VarMap")
        return data

    def stations(self, hours=24):
        """Stations heard within ``hours``, newest first.

        Returns {'stations': [...], 'own': {...} or None, 'now': iso}. Each
        station keeps VarMap's own fields (callsign, grid, distance_display,
        bearing_deg, last_band, last_snr_db, heard_age_s, flags, welfare...).
        """
        data = self._get("/api/stations")
        limit = max(0.0, float(hours)) * 3600
        rows = []
        for st in data.get("stations", []):
            age = st.get("heard_age_s")
            if age is None or (limit and age > limit):
                continue
            if st.get("is_hidden"):
                continue
            rows.append(st)
        rows.sort(key=lambda s: s.get("heard_age_s", 1e12))
        return {"stations": rows, "own": data.get("own"), "now": data.get("now")}
