"""
Swagger/OpenAPI schema definitions for the webhook API.

This module contains all Flask-RESTX model definitions used for
API documentation and request/response validation.
"""

from flask_restx import fields


def register_models(namespace):
    """
    Register all Swagger models with the given namespace.
    
    Args:
        namespace: Flask-RESTX Namespace to register models with
        
    Returns:
        dict: Dictionary containing all registered models
    """
    
    # --- Request Models ---
    
    metadata_model = namespace.model("Metadata", {
        "name": fields.String(description="Pod name", example="my-pod"),
        "labels": fields.Raw(description="Pod labels", example={"mutate": "true"}),
        "annotations": fields.Raw(description="Pod annotations", example={"mutate": "true"})
    })

    container_model = namespace.model("Container", {
        "name": fields.String(required=True, description="Container name", example="app"),
        "image": fields.String(required=True, description="Container image", example="nginx:latest")
    })

    pod_spec_model = namespace.model("PodSpec", {
        "containers": fields.List(fields.Nested(container_model), description="List of containers")
    })

    pod_object_model = namespace.model("PodObject", {
        "metadata": fields.Nested(metadata_model, description="Pod metadata"),
        "spec": fields.Nested(pod_spec_model, description="Pod spec")
    })

    kind_model = namespace.model("Kind", {
        "kind": fields.String(required=True, description="Resource kind", example="Pod")
    })

    admission_request_model = namespace.model("AdmissionRequest", {
        "uid": fields.String(required=True, description="Unique request ID", example="abc-123"),
        "kind": fields.Nested(kind_model, description="Resource kind info"),
        "operation": fields.String(required=True, description="Operation type", example="CREATE"),
        "object": fields.Nested(pod_object_model, description="The Pod object being admitted")
    })

    admission_review_request = namespace.model("AdmissionReviewRequest", {
        "apiVersion": fields.String(required=True, description="API version", example="admission.k8s.io/v1"),
        "kind": fields.String(required=True, description="Kind", example="AdmissionReview"),
        "request": fields.Nested(admission_request_model, required=True, description="Admission request")
    })

    # --- Response Models ---
    
    status_model = namespace.model("Status", {
        "message": fields.String(description="Status message", example="Pod mutated successfully")
    })

    admission_response_model = namespace.model("AdmissionResponse", {
        "uid": fields.String(description="Request UID (echoed back)", example="abc-123"),
        "allowed": fields.Boolean(description="Whether the request is allowed", example=True),
        "patch": fields.String(description="Base64-encoded JSON Patch (if mutation applied)"),
        "patchType": fields.String(description="Patch type", example="JSONPatch"),
        "status": fields.Nested(status_model, description="Response status")
    })

    admission_review_response = namespace.model("AdmissionReviewResponse", {
        "apiVersion": fields.String(description="API version", example="admission.k8s.io/v1"),
        "kind": fields.String(description="Kind", example="AdmissionReview"),
        "response": fields.Nested(admission_response_model, description="Admission response")
    })

    health_response = namespace.model("HealthResponse", {
        "status": fields.String(description="Health status", example="ok")
    })

    # Return all models as a dictionary for easy access
    return {
        "metadata": metadata_model,
        "container": container_model,
        "pod_spec": pod_spec_model,
        "pod_object": pod_object_model,
        "kind": kind_model,
        "admission_request": admission_request_model,
        "admission_review_request": admission_review_request,
        "status": status_model,
        "admission_response": admission_response_model,
        "admission_review_response": admission_review_response,
        "health_response": health_response,
    }

