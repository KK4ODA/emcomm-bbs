#!/usr/bin/env python3
"""
Console emergency check - prints current conditions without the GUI.

    python emergency_checker.py        national view
    python emergency_checker.py GA     NWS alerts filtered to one state
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from emergency_module import EmergencyDataFetcher, EmergencyResourcesFetcher  # noqa: E402
from data_sources import PowerOutageFetcher  # noqa: E402

SEVERITY_TAGS = {'Extreme': '[EXTREME]', 'Severe': '[SEVERE] ', 'Moderate': '[MODERATE]'}


def section(title):
    print(f"\n{'=' * 70}\n  {title}\n{'=' * 70}")


def failed(items):
    """True when a list-returning fetcher gave back an error record."""
    return bool(items) and isinstance(items, list) and items[0].get('error')


def show_alerts(alerts, limit=10):
    if failed(alerts):
        print(f"  Error: {alerts[0]['error']}")
        return
    if not alerts:
        print("  No active alerts")
        return
    for a in alerts[:limit]:
        tag = SEVERITY_TAGS.get(a.get('severity'), '[INFO]   ')
        print(f"\n  {tag} {a.get('event', 'Unknown event')}")
        print(f"  Area: {a.get('areas', 'Unknown')}")
        if a.get('headline'):
            print(f"  {a['headline']}")


def show_quakes(quakes, limit=10):
    if failed(quakes):
        print(f"  Error: {quakes[0]['error']}")
        return
    if not quakes:
        print("  No M4.5+ earthquakes in the past 7 days")
        return
    for q in quakes[:limit]:
        print(f"  M{q.get('magnitude')}  {q.get('location')}  ({q.get('time')}, {q.get('depth')} km)")


def show_disasters(disasters, limit=10):
    if failed(disasters):
        print(f"  Error: {disasters[0]['error']}")
        return
    if not disasters:
        print("  No declarations in the last 30 days")
        return
    for d in disasters[:limit]:
        print(f"  {d.get('disaster_number')}  {d.get('state')}  {d.get('incident_type')}: "
              f"{d.get('title')}  ({d.get('date')})")


def show_fires(fires):
    if fires.get('error'):
        print(f"  Error: {fires['error']}")
        return
    print(f"  {fires.get('message', 'No data available')}")
    for fire in fires.get('largest', []):
        contained = fire.get('contained')
        pct = f"{contained:.0f}% contained" if contained is not None else "containment n/a"
        print(f"    {fire['name']:<28} {fire['state']:<3} {fire['acres']:>9,} ac  {pct}")


def show_outages(outages):
    if outages.get('error'):
        print(f"  Error: {outages['error']}")
        return
    print(f"  {outages['national_summary']}")
    for s in outages['states'][:10]:
        print(f"    {s['state']:<4} {s['outages']:>8,}  ({s['utilities']} utilities)")


def show_resources(resources):
    print("\n  Emergency numbers:")
    for number, purpose in resources['emergency_contacts'].items():
        print(f"    {number:<16} {purpose}")
    print("\n  Kit checklist:")
    for i, item in enumerate(resources['supply_checklist'], 1):
        print(f"    {i:>2}. {item}")


def main():
    state = sys.argv[1].upper() if len(sys.argv) > 1 else None
    print(f"\n{'=' * 70}\n  EMERGENCY INFORMATION CHECK  {datetime.now():%B %d, %Y %H:%M}")
    if state:
        print(f"  NWS alerts filtered to: {state}")
    print("=" * 70)
    print("  Fetching from NWS, USGS, FEMA, NIFC and ODIN (30-60 s)...")

    fetcher = EmergencyDataFetcher()
    try:
        section("NATIONAL WEATHER SERVICE ALERTS")
        show_alerts(fetcher.get_nws_alerts(state))
        section("EARTHQUAKES  M4.5+ last 7 days")
        show_quakes(fetcher.get_recent_earthquakes())
        section("FEMA DISASTER DECLARATIONS  last 30 days")
        show_disasters(fetcher.get_fema_disasters())
        section("ACTIVE WILDFIRES  NIFC")
        show_fires(fetcher.get_active_fires())
        section("POWER OUTAGES  DOE / ORNL ODIN")
        show_outages(PowerOutageFetcher().get_outages())
        section("PREPAREDNESS REFERENCE")
        show_resources(EmergencyResourcesFetcher.get_emergency_resources())
        print(f"\n{'=' * 70}\n  Done {datetime.now():%H:%M:%S}. "
              "Tip: pass a state code to filter alerts, e.g. python emergency_checker.py TX\n")
    except KeyboardInterrupt:
        print("\n  Interrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
