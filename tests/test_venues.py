"""Tests for specs/browse-venues.md acceptance criteria."""
import re

from tests.conftest import seed_venue


def _tab_is_active(html: str, tab: str) -> bool:
    pattern = rf'<a[^>]*data-tab="{tab}"[^>]*class="[^"]*\bactive\b'
    return re.search(pattern, html) is not None


def test_index_returns_200_with_venue(client, conn):
    seed_venue(conn, ssid="VisibleNet")
    response = client.get("/")
    assert response.status_code == 200
    assert "VisibleNet" in response.text


def test_index_sorted_by_median_download_desc(client, conn):
    seed_venue(conn, ssid="SlowNet", download=5.0)
    seed_venue(conn, ssid="FastNet", download=100.0, ip="2.2.2.2")
    response = client.get("/")
    assert response.text.index("FastNet") < response.text.index("SlowNet")


def test_index_shows_ssid_download_count_and_time(client, conn):
    seed_venue(conn, ssid="InfoNet", download=42.0)
    response = client.get("/")
    assert "InfoNet" in response.text
    assert "42.0" in response.text
    assert "ago" in response.text


def test_fast_venue_has_green_class(client, conn):
    seed_venue(conn, ssid="GreenNet", download=75.0)
    response = client.get("/")
    assert "speed-fast" in response.text


def test_slow_venue_has_red_class(client, conn):
    seed_venue(conn, ssid="RedNet", download=3.0)
    response = client.get("/")
    assert "speed-slow" in response.text


def test_venue_detail_returns_200(client, conn):
    venue_id = seed_venue(conn, ssid="DetailNet")
    response = client.get(f"/venues/{venue_id}")
    assert response.status_code == 200
    assert "DetailNet" in response.text


def test_venue_detail_shows_history(client, conn):
    venue_id = seed_venue(conn, ssid="HistoryNet", download=55.0)
    response = client.get(f"/venues/{venue_id}")
    assert "55.0" in response.text


def test_venue_detail_404_for_invalid_id(client):
    response = client.get("/venues/99999")
    assert response.status_code == 404


def test_api_venues_returns_json(client, conn):
    seed_venue(conn, ssid="APINet")
    response = client.get("/api/venues")
    assert response.status_code == 200
    data = response.json()
    assert "venues" in data
    assert "page" in data
    assert isinstance(data["venues"], list)


def test_api_venues_bbox_filters(client, conn):
    seed_venue(conn, ssid="InsideNet", lat=37.77, lng=-122.41)
    seed_venue(conn, ssid="OutsideNet", lat=51.50, lng=-0.12, ip="2.2.2.2")
    response = client.get("/api/venues?bbox=-123,37,-122,38")
    data = response.json()
    ssids = [v["ssid"] for v in data["venues"]]
    assert "InsideNet" in ssids
    assert "OutsideNet" not in ssids


def test_homepage_has_both_list_and_map_tabs(client, conn):
    seed_venue(conn)
    response = client.get("/")
    assert response.status_code == 200
    assert "tab-list" in response.text
    assert "tab-map" in response.text
    assert "<table>" in response.text
    assert "leaflet" in response.text.lower()


def test_global_nav_has_two_tabs(client):
    """Report/Browse nav tabs are present in the header on every page."""
    for path in ("/", "/submit"):
        response = client.get(path)
        assert response.status_code == 200
        assert 'data-tab="report"' in response.text
        assert 'data-tab="browse"' in response.text
        # Old Map tab is removed; list+map merged into Browse
        assert 'data-tab="map"' not in response.text
        assert 'data-tab="list"' not in response.text


def test_browse_tab_active_on_homepage(client):
    response = client.get("/")
    assert _tab_is_active(response.text, "browse")
    assert not _tab_is_active(response.text, "report")


def test_report_tab_active_on_submit(client):
    response = client.get("/submit")
    assert _tab_is_active(response.text, "report")
    assert not _tab_is_active(response.text, "browse")


def test_homepage_combined_view_has_locate_button_and_responsive_layout(client, conn):
    """Browse page shows list + map together with locate-me and a desktop breakpoint."""
    seed_venue(conn, ssid="ResponsiveNet", lat=37.77, lng=-122.41)
    response = client.get("/")
    assert response.status_code == 200
    # Both panels are present in the DOM
    assert 'id="tab-list"' in response.text
    assert 'id="tab-map"' in response.text
    # Locate-me control is exposed
    assert "Locate me" in response.text
    # Desktop side-by-side breakpoint
    assert "min-width: 900px" in response.text
    # Rows expose coordinates for hover/select reactivity
    assert 'data-venue-id=' in response.text
    assert 'data-lat=' in response.text
    assert 'data-lng=' in response.text
