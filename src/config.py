import os

SPEED_SLOW_MBPS = 10.0
SPEED_FAST_MBPS = 50.0
PAGE_SIZE = 5
VENUE_DEDUPE_RADIUS_M = 50
RATE_LIMIT_HOURS = 1

# Nearby-places search radius (metres) — controls the /submit slider and API cap
NEARBY_RADIUS_DEFAULT_M = 500
NEARBY_RADIUS_MIN_M     = 100
NEARBY_RADIUS_MAX_M     = 10000
NEARBY_RADIUS_STEP_M    = 200
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")
