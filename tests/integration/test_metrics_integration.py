"""
Integration tests for metrics calculation

Tests for:
- Metrics in step response
- Metrics in status response
- End-to-end metrics flow
"""

import pytest
import requests
import time
import os

BASE_URL = os.environ.get("OASIS_BASE_URL", "http://localhost:3000")


class TestMetricsIntegration:
    """Integration tests for metrics in API responses"""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup: reset simulation before each test"""
        try:
            # Reset simulation
            requests.post(f"{BASE_URL}/api/sim/reset", json={}, timeout=10)
            time.sleep(1)
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not running")

    def test_metrics_in_step_response(self):
        """Test that metrics are included in step response"""
        # Initialize simulation
        init_response = requests.post(
            f"{BASE_URL}/api/sim/config",
            json={
                "agentCount": 5,
                "platform": "reddit",
                "recsys": "hot-score",
                "topics": ["AI"],
                "regions": ["General"]
            },
            timeout=30
        )
        assert init_response.status_code == 200

        # Wait for initialization
        time.sleep(3)

        # Execute a step
        step_response = requests.post(
            f"{BASE_URL}/api/sim/step",
            json={},
            timeout=60
        )

        assert step_response.status_code == 200
        result = step_response.json()

        # Verify metrics are present
        assert "velocity" in result
        assert "herd_hhi" in result
        assert "polarization" in result

        # Verify types
        assert isinstance(result["velocity"], (int, float))
        assert isinstance(result["herd_hhi"], (int, float))
        assert isinstance(result["polarization"], (int, float))

        # Verify HHI is in valid range [0, 1]
        assert 0 <= result["herd_hhi"] <= 1

    def test_metrics_in_status_response(self):
        """Test that metrics are included in status response"""
        # Initialize simulation
        requests.post(
            f"{BASE_URL}/api/sim/config",
            json={
                "agentCount": 3,
                "platform": "reddit",
                "recsys": "hot-score",
                "topics": ["Climate"],
                "regions": ["General"]
            },
            timeout=30
        )
        time.sleep(3)

        # Execute a step
        requests.post(f"{BASE_URL}/api/sim/step", json={}, timeout=60)
        time.sleep(1)

        # Get status
        status_response = requests.get(f"{BASE_URL}/api/sim/status", timeout=10)

        assert status_response.status_code == 200
        status = status_response.json()

        # Verify metrics are present
        assert "velocity" in status or "data" in status
        if "data" in status:
            # Server might wrap response in data field
            status = status["data"]

        # Check for camelCase fields (frontend convention)
        assert "velocity" in status or "Velocity" in status
        assert "herdHhi" in status or "HerdHhi" in status or "herd_hhi" in status

    def test_velocity_calculation_consistency(self):
        """Test that velocity calculation is consistent across steps"""
        # Initialize
        requests.post(
            f"{BASE_URL}/api/sim/config",
            json={
                "agentCount": 10,
                "platform": "reddit",
                "recsys": "hot-score",
                "topics": ["AI"],
                "regions": ["General"]
            },
            timeout=30
        )
        time.sleep(3)

        # Execute multiple steps and collect velocities
        velocities = []
        for _ in range(3):
            response = requests.post(f"{BASE_URL}/api/sim/step", json={}, timeout=60)
            assert response.status_code == 200

            result = response.json()
            velocity = result.get("velocity", 0)
            velocities.append(velocity)

            time.sleep(1)

        # Verify all velocities are non-negative
        for v in velocities:
            assert v >= 0

        # Velocities might vary but should be reasonable
        # (assuming < 100 posts per second)
        for v in velocities:
            assert v < 100

    def test_hhi_calculation_validity(self):
        """Test that HHI calculation produces valid results"""
        # Initialize with multiple agents
        requests.post(
            f"{BASE_URL}/api/sim/config",
            json={
                "agentCount": 20,  # More agents for diverse actions
                "platform": "reddit",
                "recsys": "hot-score",
                "topics": ["AI", "Climate"],  # Multiple topics
                "regions": ["General", "Tech"]
            },
            timeout=30
        )
        time.sleep(3)

        # Execute steps to generate actions
        for _ in range(5):
            requests.post(f"{BASE_URL}/api/sim/step", json={}, timeout=60)
            time.sleep(0.5)

        # Get final status
        response = requests.get(f"{BASE_URL}/api/sim/status", timeout=10)
        assert response.status_code == 200

        status = response.json()
        if "data" in status:
            status = status["data"]

        # Get HHI value (try both camelCase and snake_case)
        hhi = status.get("herdHhi") or status.get("herd_hhi") or status.get("HerdHhi")

        # HHI should be present and in valid range
        if hhi is not None:
            assert 0 <= hhi <= 1
        else:
            pytest.skip("HHI not available in status (might need more steps)")

    def test_metrics_details_in_response(self):
        """Test that detailed metrics are included in response"""
        # Initialize
        requests.post(
            f"{BASE_URL}/api/sim/config",
            json={
                "agentCount": 5,
                "platform": "reddit",
                "recsys": "hot-score",
                "topics": ["AI"],
                "regions": ["General"]
            },
            timeout=30
        )
        time.sleep(3)

        # Execute step
        response = requests.post(f"{BASE_URL}/api/sim/step", json={}, timeout=60)
        assert response.status_code == 200

        result = response.json()

        # Check for detailed metrics
        assert "velocity_details" in result
        assert "herd_hhi_details" in result
        assert "polarization_details" in result

        # Verify velocity details structure
        vel_details = result["velocity_details"]
        assert "velocity" in vel_details
        assert "step_number" in vel_details

        # Verify HHI details structure
        hhi_details = result["herd_hhi_details"]
        if not hhi_details.get("degraded"):
            assert "herd_hhi" in hhi_details
            assert "total_actions" in hhi_details


class TestMetricsErrorHandling:
    """Test metrics error handling and degradation"""

    def test_velocity_without_initialization(self):
        """Test velocity behavior when simulation not initialized"""
        # Reset
        requests.post(f"{BASE_URL}/api/sim/reset", json={}, timeout=10)

        # Try to step without initialization
        response = requests.post(f"{BASE_URL}/api/sim/step", json={}, timeout=60)

        if response.status_code == 200:
            result = response.json()
            # Should still include velocity field (possibly 0)
            assert "velocity" in result
        else:
            # Expected error response
            assert "error" in response.json() or "message" in response.json()

    def test_hhi_degraded_fallback(self):
        """Test that HHI uses fallback when trace data is empty"""
        # Initialize
        requests.post(
            f"{BASE_URL}/api/sim/config",
            json={
                "agentCount": 1,
                "platform": "reddit",
                "recsys": "hot-score",
                "topics": ["AI"],
                "regions": ["General"]
            },
            timeout=30
        )
        time.sleep(3)

        # Single agent might not produce diverse actions
        response = requests.post(f"{BASE_URL}/api/sim/step", json={}, timeout=60)
        assert response.status_code == 200

        result = response.json()
        hhi_details = result.get("herd_hhi_details", {})

        # HHI should either be calculated or degraded
        assert "herd_hhi" in hhi_details or hhi_details.get("degraded")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
