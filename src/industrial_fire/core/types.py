"""Shared primitive type aliases and enums used across layers."""

from __future__ import annotations

from enum import Enum


class ThermalSource(str, Enum):
    VIIRS_SNPP_NRT = "VIIRS_SNPP_NRT"
    VIIRS_NOAA20_NRT = "VIIRS_NOAA20_NRT"
    MODIS_NRT = "MODIS_NRT"


class FacilityType(str, Enum):
    REFINERY = "refinery"
    POWER_PLANT = "power_plant"
    STEEL = "steel"
    MINE = "mine"
    LNG = "lng"
    CHEMICAL = "chemical"
    OTHER = "other"


class ClassificationLabel(str, Enum):
    GAS_FLARE_NORMAL_INDUSTRIAL = "gas_flare_normal_industrial"
    POTENTIAL_INDUSTRIAL_FIRE = "potential_industrial_fire"
    WILDFIRE = "wildfire"
    UNKNOWN_NEEDS_REVIEW = "unknown_needs_review"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ModelSource(str, Enum):
    """Which classification strategy produced a `ClassificationResult`."""

    RULE_BASED_V1 = "rule_based_v1"
    CELSTM_V1 = "celstm_v1"
    XGBOOST_V1 = "xgboost_v1"
