"""
API route handlers for the webhook endpoints.

This module contains the actual endpoint implementations
for the mutating admission webhook.
"""

import base64
import json
import logging

from flask import request
from flask_restx import Namespace, Resource

from app.mutation_logic import make_patch_for_pod
from app.schemas import register_models
from app.validators import is_valid_admission_review, should_mutate

# Create namespace
webhook_ns = Namespace("webhook", description="Kubernetes Admission Webhook operations")

# Register Swagger models
models = register_models(webhook_ns)


@webhook_ns.route("/mutate")
class MutateResource(Resource):
    """Kubernetes Mutating Admission Webhook endpoint."""

    @webhook_ns.doc("mutate_pod")
    @webhook_ns.expect(models["admission_review_request"], validate=False)
    @webhook_ns.marshal_with(models["admission_review_response"], code=200)
    @webhook_ns.response(400, "Invalid request")
    def post(self):
        """
        Mutate Pod admission request.

        This endpoint receives AdmissionReview requests from Kubernetes API server.
        If the Pod has label `mutate: "true"` AND annotation `mutate: "true"`,
        it will inject:
        - Environment variables (HELP, MUTATE, ACCEPTED)
        - An init container that downloads a JAR file
        - A shared emptyDir volume mounted at /tmp
        """
        # Debug: Log raw request info
        logging.info("=" * 60)
        logging.info("🔍 RAW REQUEST DEBUG")
        logging.info(f"  Content-Type: {request.content_type}")
        logging.info(f"  Content-Length: {request.content_length}")
        logging.info(f"  Raw Data: {request.data[:500] if request.data else 'EMPTY'}")
        
        # Parse request body
        try:
            body = request.get_json(force=True)
            logging.info(f"  Parsed Body Type: {type(body)}")
            logging.info(f"  Parsed Body: {body}")
        except Exception as e:
            logging.error(f"  JSON Parse Error: {e}")
            webhook_ns.abort(400, "Invalid JSON")

        # Validate AdmissionReview format
        if not is_valid_admission_review(body):
            logging.error(f"  Validation Failed - body: {body}")
            logging.error(f"  apiVersion: {body.get('apiVersion') if body else 'N/A'}")
            logging.error(f"  kind: {body.get('kind') if body else 'N/A'}")
            logging.error(f"  has request: {'request' in body if body else False}")
            webhook_ns.abort(400, "Invalid AdmissionReview")

        # Extract request details
        req = body.get("request")
        uid = req.get("uid")
        response = {"uid": uid, "allowed": True}

        # Debug: Log incoming request
        logging.info("=" * 60)
        logging.info("📥 INCOMING REQUEST")
        logging.info(f"  UID: {uid}")
        logging.info(f"  Kind: {req.get('kind', {}).get('kind', 'N/A')}")
        logging.info(f"  Operation: {req.get('operation', 'N/A')}")
        
        pod_meta = req.get("object", {}).get("metadata", {})
        logging.info(f"  Pod Name: {pod_meta.get('name', 'N/A')}")
        logging.info(f"  Labels: {pod_meta.get('labels', {})}")
        logging.info(f"  Annotations: {pod_meta.get('annotations', {})}")

        # Apply mutation if criteria are met
        try:
            if should_mutate(req):
                logging.info("✅ MUTATION CRITERIA MET - Applying patches")
                pod = req.get("object", {})
                patch = make_patch_for_pod(pod)
                patch_b64 = base64.b64encode(json.dumps(patch).encode()).decode()

                # Debug: Log patches
                logging.info(f"  Patches generated: {len(patch)}")
                for i, p in enumerate(patch):
                    logging.info(f"    [{i}] {p['op']} {p['path']}")

                response.update({
                    "patch": patch_b64,
                    "patchType": "JSONPatch",
                    "status": {"message": "Pod mutated successfully"}
                })
            else:
                logging.info("⏭️  MUTATION SKIPPED - Criteria not met")
                response.update({"status": {"message": "No mutation applied"}})
        except Exception as e:
            logging.exception("❌ MUTATION FAILED")
            response.update({
                "status": {"message": f"Mutation webhook error: {str(e)}"},
                "allowed": True
            })

        # Debug: Log response
        logging.info("📤 RESPONSE")
        logging.info(f"  Allowed: {response.get('allowed')}")
        logging.info(f"  Status: {response.get('status', {}).get('message', 'N/A')}")
        logging.info(f"  Has Patch: {'patch' in response}")
        logging.info("=" * 60)

        return {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": response
        }


@webhook_ns.route("/healthz")
class HealthResource(Resource):
    """Health check endpoint for Kubernetes probes."""

    @webhook_ns.doc("health_check")
    @webhook_ns.marshal_with(models["health_response"], code=200)
    def get(self):
        """
        Health check endpoint.

        Returns the health status of the webhook server.
        Used by Kubernetes liveness/readiness probes.
        """
        return {"status": "ok"}
