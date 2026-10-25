import io
import json
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

from backend.scripts import aws_gpu_job

FAKE_ACCOUNT = "123456789012"
FAKE_AMI = "ami-00000000000000000"
FAKE_SUBNET = "subnet-00000000000000000"
FAKE_VPC = "vpc-00000000000000000"


class FakeEC2:
    def __init__(self, fail=False, uncertain=False):
        self.fail, self.uncertain = fail, uncertain
        self.calls = []

    def describe_instances(self, **kwargs):
        self.calls.append(("describe", kwargs))
        if "InstanceIds" in kwargs or (self.uncertain and kwargs["Filters"][0]["Name"] == "client-token"):
            return {"Reservations": [{"Instances": [{"InstanceId": "i-test", "State": {"Name": "running"},
                                                     "LaunchTime": datetime.fromisoformat("2026-10-24T12:00:00+00:00")}]}]}
        return {"Reservations": []}

    def describe_images(self, **kwargs):
        self.calls.append(("images", kwargs))
        return {"Images": [{"ImageId": kwargs["ImageIds"][0], "Architecture": "x86_64", "State": "available"}]}

    def describe_subnets(self, **kwargs):
        self.calls.append(("subnets", kwargs))
        return {"Subnets": [{"SubnetId": kwargs["SubnetIds"][0], "VpcId": FAKE_VPC, "State": "available"}]}

    def create_security_group(self, **kwargs):
        self.calls.append(("create_group", kwargs))
        return {"GroupId": "sg-test"}

    def authorize_security_group_ingress(self, **kwargs):
        self.calls.append(("ingress", kwargs))

    def import_key_pair(self, **kwargs):
        self.calls.append(("import_key", kwargs))

    def run_instances(self, **kwargs):
        self.calls.append(("launch", kwargs))
        if self.fail:
            raise RuntimeError("VcpuLimitExceeded")
        if self.uncertain:
            raise TimeoutError("Lost response after instance creation")
        return {"Instances": [{"InstanceId": "i-test", "State": {"Name": "pending"}}]}

    def delete_security_group(self, **kwargs):
        self.calls.append(("delete_group", kwargs))

    def delete_key_pair(self, **kwargs):
        self.calls.append(("delete_key", kwargs))

    def terminate_instances(self, **kwargs):
        self.calls.append(("terminate", kwargs))


def configure(monkeypatch, tmp_path, ec2, args=None, account=FAKE_ACCOUNT):
    key = tmp_path / "worker.pub"
    key.write_text("ssh-ed25519 fake-test-public-key")
    state = tmp_path / "state.json"
    regions = []

    class FakeSession:
        def __init__(self, **kwargs):
            regions.append(kwargs["region_name"])

        def client(self, name):
            return ec2 if name == "ec2" else self

        def get_caller_identity(self):
            return {"Account": account}

    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(Session=FakeSession))
    monkeypatch.setattr(aws_gpu_job.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b"192.0.2.8\n"))
    monkeypatch.setattr(sys, "argv", ["aws_gpu_job.py", "launch", "--state", str(state),
                                     "--public-key", str(key), "--expected-account", FAKE_ACCOUNT,
                                     "--ami-id", FAKE_AMI, "--subnet-id", FAKE_SUBNET, "--vpc-id", FAKE_VPC,
                                     *(args or [])])
    return state, regions


def test_launch_is_single_bounded_encrypted_and_private_ssh(monkeypatch, tmp_path):
    ec2 = FakeEC2()
    state, _ = configure(monkeypatch, tmp_path, ec2)
    aws_gpu_job.main()
    journal = json.loads(state.read_text())
    launch = next(value for name, value in ec2.calls if name == "launch")
    ingress = next(value for name, value in ec2.calls if name == "ingress")
    assert launch["MinCount"] == launch["MaxCount"] == 1
    assert launch["ImageId"] == FAKE_AMI
    assert launch["NetworkInterfaces"][0]["SubnetId"] == FAKE_SUBNET
    assert next(value for name, value in ec2.calls if name == "create_group")["VpcId"] == FAKE_VPC
    assert next(value for name, value in ec2.calls if name == "images")["Owners"] == ["amazon"]
    assert launch["MetadataOptions"]["HttpTokens"] == "required"
    assert launch["InstanceInitiatedShutdownBehavior"] == "terminate"
    assert launch["BlockDeviceMappings"][0]["Ebs"]["Encrypted"] is True
    assert launch["BlockDeviceMappings"][0]["Ebs"]["DeleteOnTermination"] is True
    assert ingress["IpPermissions"][0]["IpRanges"][0]["CidrIp"] == "192.0.2.8/32"
    assert "Persistent=true" in launch["UserData"]
    assert "ExecStart=/sbin/shutdown -h now" in launch["UserData"]
    assert journal["conservative_job_estimate_usd"] < 10
    assert journal["instance_id"] == "i-test"
    assert journal["expected_account"] == FAKE_ACCOUNT


@pytest.mark.parametrize("option", ["--expected-account", "--ami-id", "--subnet-id", "--vpc-id"])
def test_launch_requires_explicit_configuration_before_auth(monkeypatch, tmp_path, option):
    ec2 = FakeEC2()
    _, regions = configure(monkeypatch, tmp_path, ec2)
    argv = list(sys.argv)
    index = argv.index(option)
    del argv[index:index+2]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit):
        aws_gpu_job.main()
    assert regions == []
    assert ec2.calls == []


def test_wrong_account_fails_before_network_lookup_or_resource_access(monkeypatch, tmp_path):
    ec2 = FakeEC2()
    state, _ = configure(monkeypatch, tmp_path, ec2, account="999999999999")
    monkeypatch.setattr(aws_gpu_job.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("IP lookup precedes account guard"))
    with pytest.raises(RuntimeError, match="unexpected AWS account"):
        aws_gpu_job.main()
    assert not state.exists()
    assert ec2.calls == []


def test_mismatched_subnet_vpc_fails_before_resource_creation(monkeypatch, tmp_path):
    ec2 = FakeEC2()
    state, _ = configure(monkeypatch, tmp_path, ec2, ["--vpc-id", "vpc-11111111111111111"])
    with pytest.raises(RuntimeError, match="explicitly supplied VPC"):
        aws_gpu_job.main()
    assert not state.exists()
    assert {name for name, _ in ec2.calls} == {"describe", "subnets"}


@pytest.mark.parametrize("changes", [{"Architecture": "arm64"}, {"State": "pending"}, {"ProductCodes": ["paid-product"]}])
def test_unsuitable_ami_fails_before_resource_creation(monkeypatch, tmp_path, changes):
    ec2 = FakeEC2()
    state, _ = configure(monkeypatch, tmp_path, ec2)
    monkeypatch.setattr(ec2, "describe_images", lambda **kwargs: {"Images": [{"Architecture": "x86_64", "State": "available", **changes}]})
    with pytest.raises(RuntimeError, match="available Amazon-owned x86_64"):
        aws_gpu_job.main()
    assert not state.exists()
    assert not any(name in {"create_group", "import_key", "launch"} for name, _ in ec2.calls)


def test_quota_failure_cleans_created_resources(monkeypatch, tmp_path):
    ec2 = FakeEC2(fail=True)
    state, _ = configure(monkeypatch, tmp_path, ec2)
    with pytest.raises(RuntimeError, match="VcpuLimitExceeded"):
        aws_gpu_job.main()
    journal = json.loads(state.read_text())
    assert "instance_id" not in journal
    assert "security_group_id" not in journal
    assert "key_name" not in journal
    assert journal["cleanup_errors"] == []
    assert {"delete_group", "delete_key"} <= {name for name, _ in ec2.calls}


def test_lost_response_reconciles_and_terminates_real_instance(monkeypatch, tmp_path):
    ec2 = FakeEC2(uncertain=True)
    state, _ = configure(monkeypatch, tmp_path, ec2)
    with pytest.raises(TimeoutError):
        aws_gpu_job.main()
    journal = json.loads(state.read_text())
    assert journal["instance_id"] == "i-test"
    assert journal["termination_requested_at"]
    assert ("terminate", {"InstanceIds": ["i-test"]}) in ec2.calls
    assert "delete_group" not in {name for name, _ in ec2.calls}


def test_status_uses_journal_region(monkeypatch, tmp_path):
    ec2 = FakeEC2()
    state, regions = configure(monkeypatch, tmp_path, ec2)
    state.write_text(json.dumps({"instance_id": "i-test", "region": "us-east-1"}))
    monkeypatch.setattr(sys, "argv", ["aws_gpu_job.py", "status", "--state", str(state)])
    aws_gpu_job.main()
    assert regions == ["us-east-1"]


@pytest.mark.parametrize("hours", ["0", "-1", "4", "nan", "inf"])
def test_excess_runtime_is_rejected_before_auth(monkeypatch, tmp_path, hours):
    ec2 = FakeEC2()
    configure(monkeypatch, tmp_path, ec2, ["--max-hours", hours])
    with pytest.raises(SystemExit):
        aws_gpu_job.main()
    assert ec2.calls == []
