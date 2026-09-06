"""
Emcomm BBS - Plain-text bulletin formatters

Every bulletin is written as compact plain text so it can be moved over
low-bandwidth links (VarAC, Winlink, packet). A typical set is 20-30 KB,
roughly 95% smaller than the PDF equivalents this project started with.

Lines are wrapped to WIDTH characters so they display cleanly in the
80-column terminals most digital-mode clients use.
"""

import textwrap
from datetime import datetime

WIDTH = 75
RULE = "=" * 40


def wrap(text, width=WIDTH, indent="", first_indent=None):
    """Word-wrap ``text`` into a list of lines.

    Whitespace runs are collapsed. Words longer than the width (URLs) are
    kept intact on their own line rather than split mid-word.
    """
    text = " ".join(str(text or "").split())
    if not text:
        return []
    return textwrap.wrap(
        text, width=width,
        initial_indent=indent if first_indent is None else first_indent,
        subsequent_indent=indent,
        break_long_words=False, break_on_hyphens=False,
    )


def _stamp():
    return datetime.now().strftime("%m/%d %H:%M")


def _write(filename, lines):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        f.write('\n')


def _has_data(items):
    """True for a non-empty list whose first entry is not an error record."""
    return bool(items) and isinstance(items, list) and not items[0].get('error')


def _section(lines, title):
    """Append a blank separator (unless one is already there) and a title."""
    if lines and lines[-1] != "":
        lines.append("")
    lines.append(title)


def _iso_short(value):
    """'2026-09-06T14:00:00-04:00' -> '2026-09-06 14:00'."""
    if not value or 'T' not in value:
        return value or ''
    date, _, rest = value.partition('T')
    return f"{date} {rest[:5]}"


# ---------------------------------------------------------------------------

class PlainTextGenerator:
    """Namespace for the bulletin writers. Each writes one file and returns."""

    @staticmethod
    def create_news_txt(filename, summary_text, news_data, max_per_source=10):
        lines = [f"NEWS {_stamp()}", RULE]
        if summary_text and summary_text.strip():
            lines.append("SUMMARY:")
            for para in summary_text.strip().split('\n'):
                lines.extend(wrap(para) or [""])
            lines.append("")
        for source, headlines in news_data.items():
            lines.append(f"{source}:")
            for i, headline in enumerate(headlines[:max_per_source], 1):
                lines.extend(wrap(headline, first_indent=f"{i}. ", indent="   "))
            lines.append("")
        _write(filename, lines)

    @staticmethod
    def create_weather_txt(filename, region_number, forecasts, region_desc, periods=4):
        """One block per city, next ``periods`` NWS periods (4 = two days)."""
        lines = [f"WX R{region_number} {_stamp()}", region_desc, RULE]
        for forecast in forecasts:
            lines.append(forecast['city'])
            for period in forecast.get('forecast', [])[:periods]:
                name = period.get('name', '')[:3]      # "Tonight" -> "Ton"
                temp = period.get('temperature', '')
                lines.append(f"{name} {temp}F {period.get('shortForecast', '')}")
            lines.append("")
        _write(filename, lines)

    @staticmethod
    def create_space_txt(filename, conditions):
        lines = [
            f"SPACE {_stamp()}", RULE,
            f"SFI:{conditions.get('solar_flux', 'N/A')}",
            f"SSN:{conditions.get('sunspot_number', 'N/A')}",
            f"A:{conditions.get('a_index', 'N/A')}",
            f"K:{conditions.get('k_index', 'N/A')}",
            "",
        ]
        bands = conditions.get('band_conditions', {})
        if bands:
            lines.append("BANDS:")
            lines.extend(f"{band}: {cond}" for band, cond in bands.items())
        else:
            lines.append("BANDS: No data available")

        forecast = conditions.get('forecast', '')
        if forecast:
            lines += ["", "FORECAST:"]
            for raw in forecast.split('\n'):
                if raw.strip():
                    lines.extend(wrap(raw))
        _write(filename, lines)

    @staticmethod
    def create_emergency_txt(filename, emergency_data, max_alerts=15,
                             max_desc_lines=8, max_quakes=10, max_disasters=5):
        timestamp = emergency_data.get('timestamp', _stamp())
        lines = [f"EMRG {timestamp}", RULE]

        alerts = emergency_data.get('nws_alerts', [])
        if _has_data(alerts):
            lines.append("ALERTS:")
            for alert in alerts[:max_alerts]:
                marker = "!" if alert.get('severity') in ('Extreme', 'Severe') else " "
                header = f"{alert.get('event', 'Unknown Event')} - {alert.get('areas', 'Unknown Area')}"
                lines.extend(wrap(header, first_indent=f"{marker} ", indent="  "))

                timing = []
                if alert.get('effective'):
                    timing.append(f"From {_iso_short(alert['effective'])}")
                if alert.get('expires'):
                    timing.append(f"Until {_iso_short(alert['expires'])}")
                if timing:
                    lines.append("  " + " ".join(timing))

                headline = alert.get('headline')
                if headline and headline != alert.get('event'):
                    lines.extend(wrap(headline, indent="  "))

                desc = wrap(alert.get('description', ''), indent="  ")
                if len(desc) > max_desc_lines:
                    desc = desc[:max_desc_lines] + ["  [...]"]
                lines.extend(desc)
                lines.append("")

        quakes = emergency_data.get('usgs_earthquakes', [])
        if _has_data(quakes):
            _section(lines, "QUAKES:")
            for q in quakes[:max_quakes]:
                if q.get('error'):
                    continue
                details = [d for d in (q.get('time'), f"{q['depth']}km" if q.get('depth') else None) if d]
                text = f"M{q.get('magnitude', '')} {q.get('location', '')}"
                if details:
                    text += f" ({', '.join(details)})"
                lines.extend(wrap(text, indent="  ", first_indent=""))

        disasters = emergency_data.get('fema_disasters', [])
        if _has_data(disasters):
            _section(lines, "FEMA:")
            for d in disasters[:max_disasters]:
                if d.get('error'):
                    continue
                text = f"{d.get('disaster_number', '')} {d.get('state', '')} {d.get('incident_type', '')}"
                if d.get('title'):
                    text += f": {d['title']}"
                if d.get('date'):
                    text += f" ({d['date']})"
                lines.extend(wrap(text, indent="  ", first_indent=""))

        fires = emergency_data.get('fire_incidents') or {}
        if fires.get('active_fires'):
            _section(lines, f"FIRES: {fires['active_fires']} active wildfire incidents (NIFC)")
            for fire in fires.get('largest', []):
                contained = fire.get('contained')
                pct = f", {contained:.0f}% contained" if contained is not None else ""
                lines.extend(wrap(f"{fire['name']} ({fire['state']}) {fire['acres']:,} ac{pct}",
                                  indent="    ", first_indent="  "))

        _write(filename, lines)

    @staticmethod
    def create_tweets_txt(filename, tweets, max_tweets=20):
        lines = [f"TWEETS {_stamp()}", RULE]
        if isinstance(tweets, dict) and tweets.get('error'):
            lines.append(f"ERR: {tweets['error']}")
            if tweets.get('details'):
                lines += ["", "Details:"]
                lines.extend(f"  {d}" for d in tweets['details'][:3])
        elif isinstance(tweets, dict):
            lines.append(tweets.get('message', 'No tweets available'))
        elif tweets:
            lines += [f"Total: {len(tweets)} tweets", ""]
            for tweet in tweets[:max_tweets]:
                lines.append(f"@{tweet.get('account', 'Unknown')}:")
                lines.extend(wrap(tweet.get('text', ''), indent="  "))
                lines.append("")
        else:
            lines.append("No tweets available")
        _write(filename, lines)

    @staticmethod
    def create_nextdoor_txt(filename, posts, zip_codes):
        rule = "=" * WIDTH
        lines = [f"NEXTDOOR {_stamp()}", rule, f"MONITORING: {', '.join(zip_codes)}", rule, ""]

        if not isinstance(posts, list) or not posts:
            lines += ["No recent posts in monitored ZIP codes", ""]
            _write(filename, lines)
            return

        sections = [
            ('critical', "CRITICAL POSTS (Immediate Attention):", "! "),
            ('high', "HIGH PRIORITY (Safety Concerns):", "* "),
            ('medium', "MEDIUM PRIORITY (Community Updates):", "- "),
            ('low', "LOW PRIORITY (Informational):", "  "),
        ]
        counts = {}
        for urgency, title, bullet in sections:
            group = [p for p in posts if p.get('urgency') == urgency]
            counts[urgency] = len(group)
            if not group:
                continue
            lines += [title, ""]
            for post in group:
                category = post.get('category', '').replace('_', ' ').title()
                head = f"ZIP {post.get('zip_code', 'Unknown')} [{_age(post.get('age_hours', 0))}]"
                lines.append(f"{head} - {category}:" if category else f"{head}:")
                lines.extend(wrap(post.get('text', ''), width=WIDTH - 2,
                                  first_indent=bullet, indent="  "))
                lines.append("")

        lines += [
            rule,
            f"TOTAL POSTS: {len(posts)}",
            f"CRITICAL: {counts['critical']} | HIGH: {counts['high']} | "
            f"MEDIUM: {counts['medium']} | LOW: {counts['low']}",
            rule,
        ]
        _write(filename, lines)

    @staticmethod
    def create_power_txt(filename, outage_data):
        lines = [
            f"POWER OUTAGE REPORT {outage_data.get('timestamp', '')}",
            "Source: DOE/ORNL ODIN  odin.ornl.gov",
            "=" * 42,
        ]
        if outage_data.get('error'):
            lines += [f"Data unavailable: {outage_data['error']}",
                      "Check poweroutage.us for current info"]
            _write(filename, lines)
            return

        lines += [
            f"TOTAL OUTAGES : {outage_data.get('total_outages', 0):,}",
            f"UTILITIES     : {outage_data.get('utilities_with_outages', 0)} reporting / "
            f"{outage_data.get('utility_count', 0)} monitored",
            "",
        ]
        if outage_data.get('national_summary'):
            lines.extend(wrap(outage_data['national_summary'], width=60))
            lines.append("")

        states = outage_data.get('states', [])
        if states:
            lines += ["OUTAGES BY STATE:", f"  {'ST':<6} {'OUTAGES':>8}  UTILS", "  " + "-" * 24]
            lines.extend(f"  {s['state']:<6} {s['outages']:>8,}  {s['utilities']}" for s in states)
            lines.append("")

        top = outage_data.get('top_utilities', [])
        if top:
            lines += ["TOP UTILITIES:", f"  {'ST':<4} {'UTILITY':<32} {'OUTAGES':>8}", "  " + "-" * 46]
            lines.extend(f"  {u['state']:<4} {u['name'][:31]:<32} {u['outages']:>8,}" for u in top)

        lines += ["", "NOTE: ODIN covers participating utilities only.", "END POWER OUTAGE REPORT"]
        _write(filename, lines)


    @staticmethod
    def create_stations_txt(filename, data, hours, health=None, max_rows=60):
        """Stations heard on VarAC, from VarMap's station list.

        ``data`` is ``VarMapClient.stations()``; ``health`` (optional) is
        ``VarMapClient.health()`` for the own-station line.
        """
        stations = data.get("stations", [])
        lines = [f"STATIONS HEARD {_stamp()}  last {int(hours)}h  (VarAC via VarMap)"]
        varac = (health or {}).get("varac") or {}
        own = data.get("own") or {}
        if varac.get("mycall") or own:
            me = varac.get("mycall") or "own station"
            grid = varac.get("my_locator") or ""
            pos = f" {own['lat']:.2f},{own['lon']:.2f}" if own.get("lat") is not None else ""
            lines.append(f"Own: {me} {grid}{pos}".rstrip())
        lines.append(RULE)

        located = sum(1 for s in stations if s.get("lat") is not None)
        emcomm = sum(1 for s in stations if s.get("is_emcomm"))
        bbs = sum(1 for s in stations if s.get("is_bbs"))
        welfare = sum(1 for s in stations if (s.get("welfare") or {}).get("status"))
        summary = f"{len(stations)} stations, {located} located, {emcomm} EmComm, {bbs} BBS"
        if welfare:
            summary += f", {welfare} welfare check-ins"
        lines += [summary, ""]

        if not stations:
            lines.append("No stations heard in this period.")
            _write(filename, lines)
            return

        lines.append(f"{'CALL':<10} {'GRID':<6} {'DIST':>6} {'BRG':>3} {'BAND':<4} {'SNR':>3} {'HEARD':>5}  TAGS")
        lines.append("-" * WIDTH)
        for s in stations[:max_rows]:
            dist = (s.get("distance_display") or "").replace(" ", "")
            brg = f"{s['bearing_deg']:03d}" if s.get("bearing_deg") is not None else "   "
            snr = f"{s['last_snr_db']:+d}" if s.get("last_snr_db") is not None else "  -"
            tags = []
            if s.get("is_emcomm"):
                tags.append("EMCOMM")
            if s.get("is_bbs"):
                tags.append("BBS")
            if s.get("is_email_gateway"):
                tags.append("EMAIL")
            if s.get("is_away"):
                tags.append("AWAY")
            if s.get("last_cq_tag"):
                tags.append(str(s["last_cq_tag"]))
            wf = (s.get("welfare") or {}).get("status")
            if wf:
                tags.append("WF:" + {"SAFE": "SAFE", "NEED ASSISTANCE": "NEED", "TRAFFIC": "TRAF"}.get(wf, wf[:4]))
            lines.append(f"{s.get('callsign', '')[:10]:<10} {(s.get('grid') or '-')[:6]:<6} {dist[:6]:>6} {brg} "
                         f"{(s.get('last_band') or '')[:4]:<4} {snr:>3} {_age_short(s.get('heard_age_s')):>5}  "
                         f"{' '.join(tags)}".rstrip())
        if len(stations) > max_rows:
            lines.append(f"... {len(stations) - max_rows} more not listed")
        lines += ["", "DIST/BRG from own station. HEARD = time since last frame."]
        _write(filename, lines)


def _age_short(seconds):
    if seconds is None:
        return "-"
    seconds = int(seconds)
    if seconds < 3600:
        return f"{max(1, seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _age(hours):
    if hours < 1:
        return f"{int(hours * 60)}m ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours / 24)}d ago"
