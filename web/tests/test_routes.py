import pytest
import json
import base64
from app import create_app


@pytest.fixture
def client():
    """Create test client"""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def valid_admission_review():
    """Valid AdmissionReview request that should be mutated"""
    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "request": {
            "uid": "test-uid-123",
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "name": "test-pod",
                    "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                    "annotations": {"mutate": "true"}
                },
                "spec": {
                    "containers": [
                        {"name": "app", "image": "nginx"}
                    ]
                }
            }
        }
    }


@pytest.fixture
def admission_review_no_mutation():
    """AdmissionReview request that should NOT be mutated (missing labels)"""
    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "request": {
            "uid": "test-uid-456",
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "name": "test-pod"
                },
                "spec": {
                    "containers": [
                        {"name": "app", "image": "nginx"}
                    ]
                }
            }
        }
    }


class TestHealthEndpoint:
    """Tests for /healthz endpoint"""

    def test_health_returns_ok(self, client):
        """Health endpoint should return ok status"""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "ok"

    def test_health_returns_json(self, client):
        """Health endpoint should return JSON content type"""
        response = client.get("/healthz")
        assert response.content_type == "application/json"


class TestMutateEndpoint:
    """Tests for /mutate endpoint"""

    def test_mutate_returns_admission_review(self, client, valid_admission_review):
        """Mutate endpoint should return AdmissionReview response"""
        response = client.post(
            "/mutate",
            data=json.dumps(valid_admission_review),
            content_type="application/json"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data["apiVersion"] == "admission.k8s.io/v1"
        assert data["kind"] == "AdmissionReview"
        assert "response" in data

    def test_mutate_echoes_uid(self, client, valid_admission_review):
        """Response should echo back the request UID"""
        response = client.post(
            "/mutate",
            data=json.dumps(valid_admission_review),
            content_type="application/json"
        )
        data = json.loads(response.data)
        
        assert data["response"]["uid"] == "test-uid-123"

    def test_mutate_allows_request(self, client, valid_admission_review):
        """Response should always allow the request"""
        response = client.post(
            "/mutate",
            data=json.dumps(valid_admission_review),
            content_type="application/json"
        )
        data = json.loads(response.data)
        
        assert data["response"]["allowed"] is True

    def test_mutate_includes_patch_when_should_mutate(self, client, valid_admission_review):
        """Response should include patch when mutation criteria are met"""
        response = client.post(
            "/mutate",
            data=json.dumps(valid_admission_review),
            content_type="application/json"
        )
        data = json.loads(response.data)
        
        assert "patch" in data["response"]
        assert data["response"]["patchType"] == "JSONPatch"
        assert data["response"]["status"]["message"] == "Pod mutated successfully"

    def test_mutate_patch_is_valid_base64(self, client, valid_admission_review):
        """Patch should be valid base64-encoded JSON"""
        response = client.post(
            "/mutate",
            data=json.dumps(valid_admission_review),
            content_type="application/json"
        )
        data = json.loads(response.data)
        
        patch_b64 = data["response"]["patch"]
        patch_json = base64.b64decode(patch_b64).decode()
        patches = json.loads(patch_json)
        
        assert isinstance(patches, list)
        assert len(patches) > 0

    def test_mutate_no_patch_when_should_not_mutate(self, client, admission_review_no_mutation):
        """Response should not include patch when mutation criteria not met"""
        response = client.post(
            "/mutate",
            data=json.dumps(admission_review_no_mutation),
            content_type="application/json"
        )
        data = json.loads(response.data)
        
        assert "patch" not in data["response"]
        assert data["response"]["status"]["message"] == "No mutation applied"
        assert data["response"]["allowed"] is True

    def test_mutate_rejects_invalid_json(self, client):
        """Should return 400 for invalid JSON"""
        response = client.post(
            "/mutate",
            data="not valid json",
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_mutate_rejects_invalid_admission_review(self, client):
        """Should return 400 for invalid AdmissionReview"""
        invalid_body = {
            "apiVersion": "wrong/v1",
            "kind": "NotAdmissionReview",
            "request": {}
        }
        response = client.post(
            "/mutate",
            data=json.dumps(invalid_body),
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_mutate_rejects_missing_request(self, client):
        """Should return 400 for AdmissionReview without request"""
        invalid_body = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview"
        }
        response = client.post(
            "/mutate",
            data=json.dumps(invalid_body),
            content_type="application/json"
        )
        assert response.status_code == 400

    def test_mutate_handles_update_operation(self, client):
        """Should not mutate UPDATE operations"""
        body = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "request": {
                "uid": "test-uid-789",
                "kind": {"kind": "Pod"},
                "operation": "UPDATE",
                "object": {
                    "metadata": {
                        "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                        "annotations": {"mutate": "true"}
                    },
                    "spec": {"containers": [{"name": "app", "image": "nginx"}]}
                }
            }
        }
        response = client.post(
            "/mutate",
            data=json.dumps(body),
            content_type="application/json"
        )
        data = json.loads(response.data)
        
        assert data["response"]["allowed"] is True
        assert "patch" not in data["response"]
        assert data["response"]["status"]["message"] == "No mutation applied"

    def test_mutate_handles_non_pod_resource(self, client):
        """Should not mutate non-Pod resources"""
        body = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "request": {
                "uid": "test-uid-deployment",
                "kind": {"kind": "Deployment"},
                "operation": "CREATE",
                "object": {
                    "metadata": {
                        "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                        "annotations": {"mutate": "true"}
                    }
                }
            }
        }
        response = client.post(
            "/mutate",
            data=json.dumps(body),
            content_type="application/json"
        )
        data = json.loads(response.data)
        
        assert data["response"]["allowed"] is True
        assert "patch" not in data["response"]


class TestMutateEndpointEdgeCases:
    """Edge case tests for /mutate endpoint"""

    def test_mutate_handles_empty_containers(self, client):
        """Should handle pod with empty containers list"""
        body = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "request": {
                "uid": "test-uid-empty",
                "kind": {"kind": "Pod"},
                "operation": "CREATE",
                "object": {
                    "metadata": {
                        "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                        "annotations": {"mutate": "true"}
                    },
                    "spec": {
                        "containers": []
                    }
                }
            }
        }
        response = client.post(
            "/mutate",
            data=json.dumps(body),
            content_type="application/json"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["response"]["allowed"] is True

    def test_mutate_handles_multiple_containers(self, client):
        """Should mutate all containers in a pod"""
        body = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "request": {
                "uid": "test-uid-multi",
                "kind": {"kind": "Pod"},
                "operation": "CREATE",
                "object": {
                    "metadata": {
                        "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                        "annotations": {"mutate": "true"}
                    },
                    "spec": {
                        "containers": [
                            {"name": "app1", "image": "nginx"},
                            {"name": "app2", "image": "redis"},
                            {"name": "sidecar", "image": "envoy"}
                        ]
                    }
                }
            }
        }
        response = client.post(
            "/mutate",
            data=json.dumps(body),
            content_type="application/json"
        )
        data = json.loads(response.data)
        
        # Decode and verify patches affect all containers
        patch_b64 = data["response"]["patch"]
        patches = json.loads(base64.b64decode(patch_b64).decode())
        
        # Should have patches for containers 0, 1, and 2
        container_paths = set()
        for p in patches:
            if "/spec/containers/" in p["path"]:
                # Extract container index
                parts = p["path"].split("/")
                if len(parts) > 3:
                    container_paths.add(parts[3])
        
        assert "0" in container_paths
        assert "1" in container_paths
        assert "2" in container_paths

    def test_mutate_preserves_existing_env_vars(self, client):
        """Mutation should add to, not replace, existing env vars"""
        body = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "request": {
                "uid": "test-uid-existing-env",
                "kind": {"kind": "Pod"},
                "operation": "CREATE",
                "object": {
                    "metadata": {
                        "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                        "annotations": {"mutate": "true"}
                    },
                    "spec": {
                        "containers": [{
                            "name": "app",
                            "image": "nginx",
                            "env": [{"name": "EXISTING", "value": "keep-me"}]
                        }]
                    }
                }
            }
        }
        response = client.post(
            "/mutate",
            data=json.dumps(body),
            content_type="application/json"
        )
        data = json.loads(response.data)
        
        # Decode patches
        patch_b64 = data["response"]["patch"]
        patches = json.loads(base64.b64decode(patch_b64).decode())
        
        # Should NOT have a patch that replaces the env array
        # All env patches should be appending (using /-)
        env_patches = [p for p in patches if "/env" in p["path"]]
        for p in env_patches:
            assert p["path"].endswith("/-"), "Env patches should append, not replace"

