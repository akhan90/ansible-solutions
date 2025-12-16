import pytest
from app.mutation_logic import make_patch_for_pod


class TestMakePatchForPod:
    """Tests for make_patch_for_pod function"""

    def test_basic_pod_mutation(self):
        """Basic pod with one container should get all patches"""
        pod = {
            "metadata": {"name": "test-pod"},
            "spec": {
                "containers": [
                    {"name": "app", "image": "nginx"}
                ]
            }
        }
        patches = make_patch_for_pod(pod)
        
        # Should have patches for: env array, volumeMounts array, 3 env vars, 
        # 1 volume mount, initContainers, volumes
        assert len(patches) > 0
        
        # Verify patch operations
        ops = [p["op"] for p in patches]
        assert all(op == "add" for op in ops)

    def test_env_vars_added(self):
        """Should add HELP, MUTATE, ACCEPTED, VERSION, LABID env vars"""
        pod = {
            "metadata": {
                "labels": {"version": "1.0.0", "labid": "lab-123"}
            },
            "spec": {
                "containers": [{"name": "app", "image": "nginx"}]
            }
        }
        patches = make_patch_for_pod(pod)
        
        env_patches = [p for p in patches if "/env" in p["path"] and p["path"].endswith("/-")]
        env_names = [p["value"]["name"] for p in env_patches]
        
        assert "HELP" in env_names
        assert "MUTATE" in env_names
        assert "ACCEPTED" in env_names
        assert "VERSION" in env_names
        assert "LABID" in env_names

    def test_version_and_labid_env_vars_have_correct_values(self):
        """VERSION and LABID env vars should have values from labels"""
        pod = {
            "metadata": {
                "labels": {"version": "2.5.0", "labid": "my-lab-456"}
            },
            "spec": {
                "containers": [{"name": "app", "image": "nginx"}]
            }
        }
        patches = make_patch_for_pod(pod)
        
        env_patches = [p for p in patches if "/env" in p["path"] and p["path"].endswith("/-")]
        env_dict = {p["value"]["name"]: p["value"]["value"] for p in env_patches}
        
        assert env_dict["VERSION"] == "2.5.0"
        assert env_dict["LABID"] == "my-lab-456"

    def test_env_array_created_if_missing(self):
        """Should create env array if container doesn't have one"""
        pod = {
            "spec": {
                "containers": [{"name": "app", "image": "nginx"}]
            }
        }
        patches = make_patch_for_pod(pod)
        
        # Find patch that creates the env array
        env_init_patches = [p for p in patches 
                           if p["path"] == "/spec/containers/0/env" and p["value"] == []]
        assert len(env_init_patches) == 1

    def test_env_array_not_duplicated_if_exists(self):
        """Should not create env array if container already has one"""
        pod = {
            "spec": {
                "containers": [{
                    "name": "app", 
                    "image": "nginx",
                    "env": [{"name": "EXISTING", "value": "val"}]
                }]
            }
        }
        patches = make_patch_for_pod(pod)
        
        # Should NOT have a patch creating empty env array
        env_init_patches = [p for p in patches 
                           if p["path"] == "/spec/containers/0/env" and p["value"] == []]
        assert len(env_init_patches) == 0

    def test_volume_mount_added(self):
        """Should add /tmp volume mount"""
        pod = {
            "spec": {
                "containers": [{"name": "app", "image": "nginx"}]
            }
        }
        patches = make_patch_for_pod(pod)
        
        vol_mount_patches = [p for p in patches 
                            if "/volumeMounts/-" in p["path"]]
        assert len(vol_mount_patches) == 1
        assert vol_mount_patches[0]["value"]["mountPath"] == "/tmp"
        assert vol_mount_patches[0]["value"]["name"] == "tmp-shared"

    def test_init_container_added(self):
        """Should add init container for downloading JAR"""
        pod = {
            "metadata": {
                "labels": {"version": "1.0.0", "labid": "lab-123"}
            },
            "spec": {
                "containers": [{"name": "app", "image": "nginx"}]
            }
        }
        patches = make_patch_for_pod(pod)
        
        init_patches = [p for p in patches if "initContainers" in p["path"]]
        assert len(init_patches) == 1
        
        # When initContainers doesn't exist, should create array with container
        init_patch = init_patches[0]
        assert init_patch["path"] == "/spec/initContainers"
        assert len(init_patch["value"]) == 1
        assert init_patch["value"][0]["name"] == "init-download"
        assert init_patch["value"][0]["image"] == "busybox"

    def test_init_container_uses_version_in_url(self):
        """Init container download URL should use version from labels"""
        pod = {
            "metadata": {
                "labels": {"version": "3.2.1", "labid": "lab-123"}
            },
            "spec": {
                "containers": [{"name": "app", "image": "nginx"}]
            }
        }
        patches = make_patch_for_pod(pod)
        
        init_patches = [p for p in patches if "initContainers" in p["path"]]
        init_container = init_patches[0]["value"]
        if isinstance(init_container, list):
            init_container = init_container[0]
        
        command = init_container["command"]
        wget_command = command[2]  # The actual wget command string
        
        assert "3.2.1" in wget_command
        assert "acmpca-jvm/3.2.1/acmpca-jvm-3.2.1-sources.jar" in wget_command

    def test_init_container_appended_if_exists(self):
        """Should append to initContainers if it already exists"""
        pod = {
            "spec": {
                "containers": [{"name": "app", "image": "nginx"}],
                "initContainers": [{"name": "existing-init", "image": "alpine"}]
            }
        }
        patches = make_patch_for_pod(pod)
        
        init_patches = [p for p in patches if "initContainers" in p["path"]]
        assert len(init_patches) == 1
        
        # Should use /- to append
        init_patch = init_patches[0]
        assert init_patch["path"] == "/spec/initContainers/-"
        assert init_patch["value"]["name"] == "init-download"

    def test_volume_added(self):
        """Should add tmp-shared emptyDir volume"""
        pod = {
            "spec": {
                "containers": [{"name": "app", "image": "nginx"}]
            }
        }
        patches = make_patch_for_pod(pod)
        
        vol_patches = [p for p in patches 
                      if p["path"] == "/spec/volumes" or p["path"] == "/spec/volumes/-"]
        assert len(vol_patches) == 1
        
        # When volumes doesn't exist, should create array
        vol_patch = vol_patches[0]
        assert vol_patch["path"] == "/spec/volumes"
        assert vol_patch["value"][0]["name"] == "tmp-shared"
        assert "emptyDir" in vol_patch["value"][0]

    def test_volume_appended_if_exists(self):
        """Should append to volumes if it already exists"""
        pod = {
            "spec": {
                "containers": [{"name": "app", "image": "nginx"}],
                "volumes": [{"name": "existing-vol", "emptyDir": {}}]
            }
        }
        patches = make_patch_for_pod(pod)
        
        vol_patches = [p for p in patches if p["path"] == "/spec/volumes/-"]
        assert len(vol_patches) == 1
        assert vol_patches[0]["value"]["name"] == "tmp-shared"

    def test_multiple_containers(self):
        """Should add patches for all containers"""
        pod = {
            "spec": {
                "containers": [
                    {"name": "app1", "image": "nginx"},
                    {"name": "app2", "image": "redis"}
                ]
            }
        }
        patches = make_patch_for_pod(pod)
        
        # Should have env patches for both containers
        env_patches_container_0 = [p for p in patches if "/spec/containers/0/env" in p["path"]]
        env_patches_container_1 = [p for p in patches if "/spec/containers/1/env" in p["path"]]
        
        assert len(env_patches_container_0) > 0
        assert len(env_patches_container_1) > 0

    def test_empty_spec(self):
        """Should handle pod with empty spec gracefully"""
        pod = {"spec": {}}
        patches = make_patch_for_pod(pod)
        
        # Should still have initContainers and volumes patches
        assert any("initContainers" in p["path"] for p in patches)
        assert any("volumes" in p["path"] for p in patches)

    def test_missing_spec(self):
        """Should handle pod without spec gracefully"""
        pod = {}
        patches = make_patch_for_pod(pod)
        
        # Should have patches for initContainers and volumes
        assert any("initContainers" in p["path"] for p in patches)
        assert any("volumes" in p["path"] for p in patches)

    def test_no_containers(self):
        """Should handle pod with no containers"""
        pod = {
            "spec": {
                "containers": []
            }
        }
        patches = make_patch_for_pod(pod)
        
        # Should still have initContainers and volumes, but no container patches
        container_patches = [p for p in patches if "/spec/containers/" in p["path"]]
        assert len(container_patches) == 0

    def test_patch_format_valid_json_patch(self):
        """All patches should be valid JSON Patch format"""
        pod = {
            "spec": {
                "containers": [{"name": "app", "image": "nginx"}]
            }
        }
        patches = make_patch_for_pod(pod)
        
        for patch in patches:
            assert "op" in patch
            assert "path" in patch
            assert "value" in patch
            assert patch["op"] in ["add", "remove", "replace", "move", "copy", "test"]
            assert patch["path"].startswith("/")

