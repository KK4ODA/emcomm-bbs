#!/usr/bin/env python3
"""
Test script to verify Welfare Board time windows
"""

from datetime import datetime
from aggregator import WelfareAggregator

# Test configuration
config = {
    'time_windows': [
        {'name': 'All Day', 'start': '00:00', 'end': '23:59'}
    ]
}

print("=" * 60)
print("WELFARE BOARD TIME WINDOW TEST")
print("=" * 60)
print()

# Create aggregator
agg = WelfareAggregator(config)

# Get current time
now = datetime.now()
print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Current time (time only): {now.strftime('%H:%M')}")
print()

# Test windows
print("Configured windows:")
for window in config['time_windows']:
    print(f"  • {window['name']}: {window['start']}-{window['end']}")
print()

# Check current window
window_info = agg.get_current_window()

if window_info:
    print("✓ ACTIVE WINDOW FOUND")
    print(f"  Name: {window_info['name']}")
    print(f"  Start: {window_info['start']}")
    print(f"  End: {window_info['end']}")
    print(f"  Key: {window_info['key']}")
else:
    print("✗ NO ACTIVE WINDOW")
    print("  This means check-ins will be rejected!")

print()
print("=" * 60)

# Test with your actual settings
print()
print("Now testing YOUR settings from the app:")
print()

your_config = {
    'time_windows': [
        {'name': 'Morning Net', 'start': '00:00', 'end': '23:59'},
        {'name': 'Afternoon Net', 'start': '00:00', 'end': '23:59'},
        {'name': 'Evening Net', 'start': '00:00', 'end': '23:59'}
    ]
}

agg2 = WelfareAggregator(your_config)

print("Configured windows:")
for window in your_config['time_windows']:
    print(f"  • {window['name']}: {window['start']}-{window['end']}")
print()

window_info2 = agg2.get_current_window()

if window_info2:
    print("✓ ACTIVE WINDOW FOUND")
    print(f"  Name: {window_info2['name']}")
    print(f"  Start: {window_info2['start']}")
    print(f"  End: {window_info2['end']}")
else:
    print("✗ NO ACTIVE WINDOW")

print()
print("=" * 60)
