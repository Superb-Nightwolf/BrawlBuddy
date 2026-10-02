"""Shared, versioned economy configuration for readiness and roster upgrades."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_readiness_config(path: Path | None = None) -> dict[str, Any]:
    path = path or Path(__file__).resolve().parents[2] / "config" / "readiness.json"
    with path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    for level in range(1, config["targetPower"]):
        cost = config["powerUpgrades"][str(level)]
        if any(not isinstance(cost[key], int) or cost[key] < 0 for key in ("coins", "powerPoints")):
            raise ValueError("Power upgrade costs must be nonnegative integers")
    if any(value < 0 for value in config["weights"].values()) or not sum(config["weights"].values()):
        raise ValueError("Readiness weights must be nonnegative with a positive total")
    if config["buffie"]["defaultDirectGemPrice"] < 0:
        raise ValueError("Buffie Gem price cannot be negative")
    price_records = list(config["buffie"].get("directGemPricesByCategory", {}).values())
    for prices in config["buffie"].get("directGemPrices", {}).values():
        price_records.extend(prices.values())
    for record in price_records:
        price = record.get("gems") if isinstance(record, dict) else record
        if not isinstance(price, int) or isinstance(price, bool) or price < 0:
            raise ValueError("Buffie Gem prices must be nonnegative integers")
    return config


READINESS_CONFIG = load_readiness_config()
