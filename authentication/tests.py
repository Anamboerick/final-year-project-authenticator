from django.test import TestCase
from authentication.models import LoginAttempt
from authentication.anomaly_detection import run_isolation_forest

class AnomalyDetectionTest(TestCase):
    def test_not_enough_data(self):
        result = run_isolation_forest()
        self.assertIn("error", result)

    def test_returns_anomaly_stats(self):
        # create enough records first
        for i in range(10):
            LoginAttempt.objects.create(
                username="testuser",
                status="Access Denied",
                average_distance=0.6,
                valid_frames=2,
                liveness_passed=False,
                attempt_count=1,
                ip_address="127.0.0.1",
                suspicious=True,
            )
        result = run_isolation_forest()
        self.assertIn("anomalies_detected", result)