# wifibuddy

Wifibuddy is a FastAPI web application designed to crowdsource and map Wi-Fi speeds at various venues like cafes and shops. It uses a SQLite database for storage and integrates with OpenStreetMap for location discovery.

1. Core Architecture
The app is structured around a centralized FastAPI instance that mounts several functional routers:

main.py: The entry point that initializes the database and includes routes for venues, reports, administration, and speed testing.

db.py: Manages the SQLite connection and defines the schema. It uses a PRAGMA foreign_keys = ON setting to ensure data integrity.

config.py: Centralizes settings like speed thresholds (10 Mbps for slow, 50 Mbps for fast), pagination limits, and rate-limiting durations.

2. Data Model & Storage
The database consists of two primary tables:

venues: Stores the SSID (Network Name), venue name, and geographical coordinates (Latitude/Longitude).

speed_reports: Linked to venues via a foreign key, this table stores download/upload speeds, ping results, submission timestamps, and the submitter's IP address for rate-limiting purposes.

3. Key Workflows

    A. Reporting Speed (reports.py)
    When a user submits a report, the app performs several checks:

    Validation: It ensures speeds are within realistic bounds (0 to 10,000 Mbps) and that the SSID is valid.

    Deduplication: It uses the Haversine formula to check if a venue with the same SSID already exists within a 50-meter radius. If it does, the report is attached to the existing venue instead of creating a new one.

    Rate Limiting: Users are limited to one report per venue per hour (configurable) based on their IP address to prevent spam.

    B. Discovery & Geolocation (venues.py)
    The app uses a hybrid approach to help users find where they are:

    Local Data: It first searches the internal database for existing venues within a 100m radius.

    External Data (OSM): If local data is sparse, or to provide better suggestions, it queries the Overpass API (OpenStreetMap) to find any named shops or cafes nearby.

    UI Integration: JavaScript in the browser requests the user's coordinates and populates a dropdown menu with these results as soon as the page loads.

    C. Browsing & Stats
    Ranking: Venues are displayed in the "Browse" tab, sorted by their median download speed.

    Pagination: The list is paginated to show 5 rows at a time for better performance.

    Venue Details: For each venue, the app calculates median statistics for all historical reports and color-codes them (e.g., "fast" or "slow") based on the thresholds in the config.

4. Admin & Utilities
Administration: Protected by HTTP Basic Auth, admins can list all recent reports and delete specific reports or entire venues.

Speedtest API: Provides lightweight endpoints (/ping, /download, /upload) that the frontend can use to actually measure the network performance before submission.

