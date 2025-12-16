import pytest
from app.validators import is_valid_admission_review, should_mutate


class TestIsValidAdmissionReview:
    """Tests for is_valid_admission_review function"""

    def test_valid_admission_review(self):
        """Valid AdmissionReview should return True"""
        body = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "request": {"uid": "test-123"}
        }
        assert is_valid_admission_review(body) is True

    def test_missing_api_version(self):
        """Missing apiVersion should return False"""
        body = {
            "kind": "AdmissionReview",
            "request": {"uid": "test-123"}
        }
        assert is_valid_admission_review(body) is False

    def test_wrong_api_version(self):
        """Wrong apiVersion should return False"""
        body = {
            "apiVersion": "admission.k8s.io/v1beta1",
            "kind": "AdmissionReview",
            "request": {"uid": "test-123"}
        }
        assert is_valid_admission_review(body) is False

    def test_missing_kind(self):
        """Missing kind should return False"""
        body = {
            "apiVersion": "admission.k8s.io/v1",
            "request": {"uid": "test-123"}
        }
        assert is_valid_admission_review(body) is False

    def test_wrong_kind(self):
        """Wrong kind should return False"""
        body = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "SomethingElse",
            "request": {"uid": "test-123"}
        }
        assert is_valid_admission_review(body) is False

    def test_missing_request(self):
        """Missing request should return False"""
        body = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview"
        }
        assert is_valid_admission_review(body) is False

    def test_none_input(self):
        """None input should return False"""
        assert is_valid_admission_review(None) is False

    def test_empty_dict(self):
        """Empty dict should return False"""
        assert is_valid_admission_review({}) is False

    def test_non_dict_input(self):
        """Non-dict input should return False"""
        assert is_valid_admission_review("string") is False
        assert is_valid_admission_review([]) is False
        assert is_valid_admission_review(123) is False


class TestShouldMutate:
    """Tests for should_mutate function"""

    def test_should_mutate_with_correct_labels_and_annotations(self):
        """Pod with all required labels AND annotation should be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                    "annotations": {"mutate": "true"}
                }
            }
        }
        assert should_mutate(req) is True

    def test_should_not_mutate_without_label(self):
        """Pod without mutate label should not be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "labels": {},
                    "annotations": {"mutate": "true"}
                }
            }
        }
        assert should_mutate(req) is False

    def test_should_not_mutate_without_annotation(self):
        """Pod without mutate annotation should not be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                    "annotations": {}
                }
            }
        }
        assert should_mutate(req) is False

    def test_should_not_mutate_with_false_label(self):
        """Pod with mutate=false label should not be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "labels": {"mutate": "false"},
                    "annotations": {"mutate": "true"}
                }
            }
        }
        assert should_mutate(req) is False

    def test_should_not_mutate_with_false_annotation(self):
        """Pod with mutate=false annotation should not be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                    "annotations": {"mutate": "false"}
                }
            }
        }
        assert should_mutate(req) is False

    def test_should_not_mutate_non_pod_resource(self):
        """Non-Pod resources should not be mutated"""
        req = {
            "kind": {"kind": "Deployment"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                    "annotations": {"mutate": "true"}
                }
            }
        }
        assert should_mutate(req) is False

    def test_should_not_mutate_non_create_operation(self):
        """Non-CREATE operations should not be mutated"""
        for operation in ["UPDATE", "DELETE", "CONNECT"]:
            req = {
                "kind": {"kind": "Pod"},
                "operation": operation,
                "object": {
                    "metadata": {
                        "labels": {"mutate": "true", "version": "1.0", "labid": "lab-123"},
                        "annotations": {"mutate": "true"}
                    }
                }
            }
            assert should_mutate(req) is False, f"Failed for operation: {operation}"

    def test_should_not_mutate_missing_metadata(self):
        """Pod without metadata should not be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {}
        }
        assert should_mutate(req) is False

    def test_should_not_mutate_missing_object(self):
        """Request without object should not be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE"
        }
        assert should_mutate(req) is False

    def test_should_not_mutate_empty_request(self):
        """Empty request should not be mutated"""
        assert should_mutate({}) is False

    def test_should_not_mutate_without_version_label(self):
        """Pod without version label should not be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "labels": {"mutate": "true", "labid": "lab-123"},
                    "annotations": {"mutate": "true"}
                }
            }
        }
        assert should_mutate(req) is False

    def test_should_not_mutate_without_labid_label(self):
        """Pod without labid label should not be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "labels": {"mutate": "true", "version": "1.0"},
                    "annotations": {"mutate": "true"}
                }
            }
        }
        assert should_mutate(req) is False

    def test_should_not_mutate_with_null_version_label(self):
        """Pod with null version label should not be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "labels": {"mutate": "true", "version": None, "labid": "lab-123"},
                    "annotations": {"mutate": "true"}
                }
            }
        }
        assert should_mutate(req) is False

    def test_should_not_mutate_with_null_labid_label(self):
        """Pod with null labid label should not be mutated"""
        req = {
            "kind": {"kind": "Pod"},
            "operation": "CREATE",
            "object": {
                "metadata": {
                    "labels": {"mutate": "true", "version": "1.0", "labid": None},
                    "annotations": {"mutate": "true"}
                }
            }
        }
        assert should_mutate(req) is False

