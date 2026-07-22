"""Area-risk forecasting (FORECAST tab): live QuickML predictor + plain facts."""

from kavach.analytics.risk.engine import (
    METHOD_NAME,
    METHOD_VERSION,
    MODEL_VERSION,
    forecast_area_risk,
)

__all__ = ["METHOD_NAME", "METHOD_VERSION", "MODEL_VERSION", "forecast_area_risk"]
