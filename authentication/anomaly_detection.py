import pandas as pd
from sklearn.ensemble import IsolationForest
from .models import LoginAttempt

def run_isolation_forest():
    attempts = LoginAttempt.objects.exclude(average_distance=None)

    data = []
    for a in attempts:
        data.append({
            "average_distance": a.average_distance,
            "valid_frames": a.valid_frames,
            "attempt_count": a.attempt_count,
            "liveness_passed": 1 if a.liveness_passed else 0,
            "status": 1 if a.status == "Access Granted" else 0,
            "suspicious": 1 if a.suspicious else 0, 
        })

    if len(data) < 5:
        return {"error": "Not enough data for Isolation Forest."}
    df = pd.DataFrame(data)

    model = IsolationForest(contamination=0.1, random_state=42)
    preds = model.fit_predict(df)

    anomalies = sum(1 for p in preds if p == -1)

    return {
        "total_attempts": len(data),
        "anomalies_detected": anomalies,
        "anomaly_percentage": anomalies / len(data) * 100
    }  