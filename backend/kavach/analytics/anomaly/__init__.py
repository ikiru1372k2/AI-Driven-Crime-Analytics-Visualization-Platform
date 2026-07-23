"""Point-anomaly detection (FLAG tab, C2-R10): stats + IsolationForest + GLM."""

from kavach.analytics.anomaly.engine import (
    METHOD_NAME,
    METHOD_VERSION,
    MODEL_VERSION,
    detect_anomalies,
)

__all__ = ["METHOD_NAME", "METHOD_VERSION", "MODEL_VERSION", "detect_anomalies"]
