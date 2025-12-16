"""Tests for Swagger schema definitions."""

import pytest
from flask_restx import Namespace

from app.schemas import register_models


class TestRegisterModels:
    """Tests for register_models function."""

    @pytest.fixture
    def namespace(self):
        """Create a test namespace."""
        return Namespace("test", description="Test namespace")

    def test_register_models_returns_dict(self, namespace):
        """register_models should return a dictionary."""
        models = register_models(namespace)
        assert isinstance(models, dict)

    def test_register_models_contains_required_keys(self, namespace):
        """All required model keys should be present."""
        models = register_models(namespace)
        
        required_keys = [
            "metadata",
            "container",
            "pod_spec",
            "pod_object",
            "kind",
            "admission_request",
            "admission_review_request",
            "status",
            "admission_response",
            "admission_review_response",
            "health_response",
        ]
        
        for key in required_keys:
            assert key in models, f"Missing model: {key}"

    def test_models_are_registered_with_namespace(self, namespace):
        """Models should be registered with the namespace."""
        register_models(namespace)
        
        # Check that models are in namespace.models
        assert "AdmissionReviewRequest" in namespace.models
        assert "AdmissionReviewResponse" in namespace.models
        assert "HealthResponse" in namespace.models

    def test_admission_review_request_has_required_fields(self, namespace):
        """AdmissionReviewRequest model should have required fields."""
        models = register_models(namespace)
        model = models["admission_review_request"]
        
        # Check model has expected fields
        assert "apiVersion" in model
        assert "kind" in model
        assert "request" in model

    def test_health_response_has_status_field(self, namespace):
        """HealthResponse model should have status field."""
        models = register_models(namespace)
        model = models["health_response"]
        
        assert "status" in model

