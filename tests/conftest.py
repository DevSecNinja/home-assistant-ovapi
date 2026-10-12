"""Deterministic synthetic Home Assistant fixtures."""

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations: None) -> None:
    """Enable the custom integration without replacing HA interfaces."""


@pytest.fixture
def api(aioclient_mock):
    """Intercept upstream HTTP; unmatched network requests fail."""
    return aioclient_mock


@pytest.fixture
def payload() -> dict:
    """Synthetic source shape; never capture real OVAPI responses."""
    return {
        "01234567": {
            "Passes": {
                "SYNTHETIC_TRIP": {
                    "TransportType": "TRAM",
                    "LinePublicNumber": "X1",
                    "DestinationName50": "Synthetic destination",
                    "TargetDepartureTime": "2030-01-15T13:10:00",
                    "ExpectedDepartureTime": "2030-01-15T13:12:00",
                    "TripStopStatus": "DRIVING",
                    "JourneyStopType": "INTERMEDIATE",
                }
            }
        }
    }
