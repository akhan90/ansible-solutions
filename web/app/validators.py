def is_valid_admission_review(body):
    return (
        isinstance(body, dict)
        and body.get("apiVersion") == "admission.k8s.io/v1"
        and body.get("kind") == "AdmissionReview"
        and "request" in body
    )

def should_mutate(req):
    # Only mutate if resource is Pod and operation is CREATE
    if req.get("kind", {}).get("kind") != "Pod":
        return False
    if req.get("operation") != "CREATE":
        return False

    # Check labels and annotations
    obj = req.get("object", {})
    meta = obj.get("metadata", {})
    labels = meta.get("labels", {})
    annotations = meta.get("annotations", {})

    return (
        labels.get("mutate") == "true"
        and annotations.get("mutate") == "true"
        and labels.get("version") is not None
        and labels.get("labid") is not None
    )
