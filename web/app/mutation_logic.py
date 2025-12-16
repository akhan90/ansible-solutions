def make_patch_for_pod(pod):
    patches = []
    spec = pod.get("spec", {})
    
    # Extract labels from Pod metadata
    metadata = pod.get("metadata", {})
    labels = metadata.get("labels", {})
    version = labels.get("version", "")
    labid = labels.get("labid", "")

    env_additions = [
        {"name": "HELP", "value": "YES"},
        {"name": "MUTATE", "value": "true"},
        {"name": "ACCEPTED", "value": "yes"},
        {"name": "VERSION", "value": version},
        {"name": "LABID", "value": labid},
    ]

    containers = spec.get("containers", [])
    for idx, container in enumerate(containers):
        env_path = f"/spec/containers/{idx}/env"
        vol_mount_path = f"/spec/containers/{idx}/volumeMounts"

        # --- Ensure 'env' exists ---
        if "env" not in container:
            patches.append({
                "op": "add",
                "path": env_path,
                "value": []
            })

        # --- Ensure 'volumeMounts' exists ---
        if "volumeMounts" not in container:
            patches.append({
                "op": "add",
                "path": vol_mount_path,
                "value": []
            })

        # --- Add env vars ---
        for env in env_additions:
            patches.append({
                "op": "add",
                "path": env_path + "/-",
                "value": env
            })

        # --- Add shared /tmp volume mount ---
        volume_mount = {"mountPath": "/tmp", "name": "tmp-shared"}
        patches.append({
            "op": "add",
            "path": vol_mount_path + "/-",
            "value": volume_mount
        })

    # --- Handle initContainers ---
    # Build download URL using version from labels
    download_url = (
        f"https://repo.maven.apache.org/maven2/aws/sdk/kotlin/"
        f"acmpca-jvm/{version}/acmpca-jvm-{version}-sources.jar"
    )
    
    init_container = {
        "name": "init-download",
        "image": "busybox",
        "command": [
            "sh", "-c",
            f"wget -O /tmp/aws.jar {download_url}"
        ],
        "volumeMounts": [{"mountPath": "/tmp", "name": "tmp-shared"}],
    }

    # If initContainers doesn't exist, create it
    if "initContainers" not in spec:
        patches.append({
            "op": "add",
            "path": "/spec/initContainers",
            "value": [init_container],
        })
    else:
        patches.append({
            "op": "add",
            "path": "/spec/initContainers/-",
            "value": init_container,
        })

    # --- Handle volumes ---
    if "volumes" not in spec:
        patches.append({
            "op": "add",
            "path": "/spec/volumes",
            "value": [{"name": "tmp-shared", "emptyDir": {}}],
        })
    else:
        patches.append({
            "op": "add",
            "path": "/spec/volumes/-",
            "value": {"name": "tmp-shared", "emptyDir": {}},
        })

    return patches
