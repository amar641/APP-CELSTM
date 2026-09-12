"""
Integration-level tests for the FIRMS adapter that don't require a live
network call — CSV parsing and config validation. A test hitting the real
FIRMS API belongs behind a `--run-live` flag, not in the default suite.
"""

import pytest

from industrial_fire.core.exceptions import ExternalServiceError
from industrial_fire.infrastructure.firms.client import FirmsClient

SAMPLE_CSV = (
    "latitude,longitude,bright_ti4,frp,confidence,acq_date,acq_time,satellite\n"
    "22.470,70.050,330.5,12.3,high,2026-01-01,0530,N\n"
    "not-a-number,70.050,330.5,12.3,high,2026-01-01,0530,N\n"  # malformed row, should be skipped
)


def test_client_rejects_missing_map_key():
    with pytest.raises(ExternalServiceError):
        FirmsClient(map_key="", base_url="https://example.invalid", source="VIIRS_SNPP_NRT")


def test_parse_csv_skips_malformed_rows():
    client = FirmsClient(map_key="dummy", base_url="https://example.invalid", source="VIIRS_SNPP_NRT")
    events = client._parse_csv(SAMPLE_CSV)
    assert len(events) == 1
    assert events[0].location.latitude == pytest.approx(22.470)
    assert events[0].frp_mw == pytest.approx(12.3)
