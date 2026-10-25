#!/usr/bin/env python3
"""Launch/status/terminate one bounded TRIBE worker. Credentials stay in memory.

The launch writes a resource journal to ignored data/gpu-job so cleanup can be
resumed after interruption. It creates no IAM roles, buckets, endpoints or NATs.
"""
import argparse
import getpass
import ipaddress
import json
import re
import sys
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

REGIONS = ("us-east-2", "us-east-1")


def timestamp():
    return datetime.now(UTC).isoformat()


def bootstrap_deadline(expires_at):
    calendar = datetime.fromisoformat(expires_at).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""#!/bin/bash
set -euo pipefail
cat > /etc/systemd/system/last-warning-budget.service <<'SERVICE'
[Unit]
Description=Terminate Last Warning GPU at its budget deadline
[Service]
Type=oneshot
ExecStart=/sbin/shutdown -h now
SERVICE
cat > /etc/systemd/system/last-warning-budget.timer <<'TIMER'
[Unit]
Description=Absolute Last Warning GPU budget deadline
[Timer]
OnCalendar={calendar}
Persistent=true
Unit=last-warning-budget.service
[Install]
WantedBy=timers.target
TIMER
systemctl daemon-reload
systemctl enable --now last-warning-budget.timer
date -u > /var/tmp/last-warning-budget-installed
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["launch", "status", "terminate", "cleanup"])
    parser.add_argument("--state", type=Path, default=Path("data/gpu-job/aws-job.json"))
    parser.add_argument("--credential-parts", type=int, default=0)
    parser.add_argument("--instance-type", default="g5.4xlarge")
    parser.add_argument("--hourly-price", type=float, default=1.624)
    parser.add_argument("--max-hours", type=float, default=3)
    parser.add_argument("--region", choices=list(REGIONS), default="us-east-2")
    parser.add_argument("--expected-account", help="Required for launch: AWS account ID verified against STS")
    parser.add_argument("--subnet-id", help="Required for launch: existing public subnet in the selected region")
    parser.add_argument("--vpc-id", help="Required for launch: VPC containing the supplied subnet")
    parser.add_argument("--ami-id", help="Required for launch: Amazon-owned x86_64 DLAMI in the selected region")
    parser.add_argument("--spot", action="store_true", help="One-time Spot with the supplied hourly price as a ceiling")
    parser.add_argument("--public-key", type=Path, default=Path("data/gpu-job/worker-key.pub"))
    args = parser.parse_args()
    if not 0 < args.max_hours <= 3 or not 0 < args.hourly_price <= 3:
        parser.error("Maximum three-hour job and $3/hour verified instance price")
    if args.instance_type not in {"g5.2xlarge", "g5.4xlarge", "g6.2xlarge"}:
        parser.error("Use one of the evaluated single-GPU instance types")
    if args.action == "launch":
        if not re.fullmatch(r"[0-9]{12}", args.expected_account or ""):
            parser.error("Launch requires --expected-account with a 12-digit AWS account ID")
        for option, value, prefix in (("--subnet-id", args.subnet_id, "subnet"),
                                      ("--vpc-id", args.vpc_id, "vpc"),
                                      ("--ami-id", args.ami_id, "ami")):
            if not re.fullmatch(rf"{prefix}-(?:[0-9a-f]{{8}}|[0-9a-f]{{17}})", value or ""):
                parser.error(f"Launch requires an explicit valid {option}")
    import boto3

    state = json.loads(args.state.read_text()) if args.state.exists() else {}
    selected_region = args.region if args.action == "launch" else state.get("region", args.region)
    if args.credential_parts:
        credentials = json.loads("".join(getpass.getpass("Credential part (hidden): ")
                                          for _ in range(args.credential_parts)))
        session = boto3.Session(**credentials, region_name=selected_region)
    else:
        session = boto3.Session(region_name=selected_region)
    ec2 = session.client("ec2")

    def save():
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(json.dumps(state, indent=2, default=str) + "\n")

    def cleanup():
        errors = []
        if state.get("security_group_id"):
            try:
                ec2.delete_security_group(GroupId=state["security_group_id"])
                state.pop("security_group_id")
                save()
            except Exception as error:
                errors.append(str(error))
        if state.get("key_name"):
            try:
                ec2.delete_key_pair(KeyName=state["key_name"])
                state.pop("key_name")
                save()
            except Exception as error:
                errors.append(str(error))
        state["cleanup_errors"] = errors
        save()
        return errors

    if args.action in {"status", "terminate", "cleanup"}:
        if state.get("instance_id"):
            if args.action == "terminate":
                ec2.terminate_instances(InstanceIds=[state["instance_id"]])
                state["termination_requested_at"] = timestamp()
                save()
            value = ec2.describe_instances(InstanceIds=[state["instance_id"]])["Reservations"][0]["Instances"][0]
            state.update(instance_state=value["State"]["Name"], public_ip=value.get("PublicIpAddress"),
                         launch_time=value["LaunchTime"].isoformat(), last_checked_at=timestamp())
            save()
            if args.action == "cleanup" and state["instance_state"] != "terminated":
                raise RuntimeError("Terminate the worker and wait for terminated state before cleanup")
        if args.action == "cleanup":
            errors = cleanup()
            if errors:
                raise RuntimeError("; ".join(errors))
        print(json.dumps(state, indent=2))
        return

    if state.get("instance_id") or state.get("security_group_id") or state.get("key_name"):
        raise RuntimeError("Existing journal contains resources; inspect and clean it before another launch")
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != args.expected_account:
        raise RuntimeError("Refusing to launch in an unexpected AWS account")
    with urllib.request.urlopen("https://checkip.amazonaws.com", timeout=20) as response:
        address = ipaddress.ip_address(response.read().decode().strip())
    if address.version != 4:
        raise RuntimeError("This public subnet requires a specific IPv4 SSH source")
    active = ec2.describe_instances(Filters=[
        {"Name": "tag:Project", "Values": ["LastWarning"]},
        {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
    ])["Reservations"]
    if active:
        raise RuntimeError("A Last Warning instance already exists; inspect it instead of duplicating compute")
    subnets = ec2.describe_subnets(SubnetIds=[args.subnet_id])["Subnets"]
    if len(subnets) != 1 or subnets[0].get("VpcId") != args.vpc_id or subnets[0].get("State") != "available":
        raise RuntimeError("Expected an available subnet in the explicitly supplied VPC")
    images = ec2.describe_images(ImageIds=[args.ami_id], Owners=["amazon"])["Images"]
    if (len(images) != 1 or images[0].get("ProductCodes")
            or images[0].get("Architecture") != "x86_64" or images[0].get("State") != "available"):
        raise RuntimeError("Expected an available Amazon-owned x86_64 DLAMI without additional marketplace charges")
    estimate = args.hourly_price * args.max_hours + 100 * .08 / 720 * args.max_hours + .005 * args.max_hours + 1
    if estimate >= 10:
        raise RuntimeError("Job estimate exceeds the $10 sub-allocation; total project ceiling is $30")
    token = "last-warning-" + uuid.uuid4().hex[:12]
    expires = (datetime.now(UTC) + timedelta(hours=args.max_hours)).isoformat()
    state.update(job_id=token, region=args.region, instance_type=args.instance_type,
                 expected_account=args.expected_account, subnet_id=args.subnet_id, vpc_id=args.vpc_id, ami_id=args.ami_id,
                 hourly_compute_usd=args.hourly_price, maximum_hours=args.max_hours,
                 conservative_job_estimate_usd=round(estimate, 3), expires_at=expires,
                 root_disk_gib=100, root_disk_delete_on_termination=True,
                 shutdown_behavior="terminate", started_at=timestamp(), ssh_cidr=f"{address}/32")
    state["market"] = "spot" if args.spot else "on-demand"
    save()
    tags = [{"Key": "Project", "Value": "LastWarning"}, {"Key": "Name", "Value": token},
            {"Key": "ExpiresAt", "Value": expires}, {"Key": "Purpose", "Value": "TRIBE-inference"}]
    launch_requested = False
    try:
        group = ec2.create_security_group(GroupName=token, Description="Temporary TRIBE SSH from operator IP only",
                                          VpcId=args.vpc_id, TagSpecifications=[{"ResourceType": "security-group", "Tags": tags}])
        state["security_group_id"] = group["GroupId"]
        save()
        ec2.authorize_security_group_ingress(GroupId=group["GroupId"], IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
            "IpRanges": [{"CidrIp": f"{address}/32", "Description": "Temporary operator SSH"}],
        }])
        ec2.import_key_pair(KeyName=token, PublicKeyMaterial=args.public_key.read_bytes(),
                            TagSpecifications=[{"ResourceType": "key-pair", "Tags": tags}])
        state["key_name"] = token
        save()
        market = {"InstanceMarketOptions": {"MarketType": "spot", "SpotOptions": {
            "MaxPrice": str(args.hourly_price), "SpotInstanceType": "one-time",
            "InstanceInterruptionBehavior": "terminate",
        }}} if args.spot else {}
        launch_requested = True
        result = ec2.run_instances(
            ClientToken=token, ImageId=args.ami_id, InstanceType=args.instance_type, MinCount=1, MaxCount=1,
            KeyName=token, NetworkInterfaces=[{"DeviceIndex": 0, "SubnetId": args.subnet_id,
                                              "Groups": [group["GroupId"]], "AssociatePublicIpAddress": True,
                                              "DeleteOnTermination": True}],
            InstanceInitiatedShutdownBehavior="terminate", MetadataOptions={"HttpTokens": "required"},
            BlockDeviceMappings=[{"DeviceName": "/dev/sda1", "Ebs": {
                "VolumeSize": 100, "VolumeType": "gp3", "Encrypted": True, "DeleteOnTermination": True,
            }}], UserData=bootstrap_deadline(expires),
            TagSpecifications=[{"ResourceType": "instance", "Tags": tags}, {"ResourceType": "volume", "Tags": tags}],
            **market,
        )
        state["instance_id"] = result["Instances"][0]["InstanceId"]
        state["instance_state"] = result["Instances"][0]["State"]["Name"]
        save()
        print(json.dumps(state, indent=2))
    except Exception as error:
        state["launch_error"] = f"{type(error).__name__}: {error}"
        save()
        # A lost launch response can still correspond to a real billed instance.
        # Reconcile the idempotency token and stop it before considering cleanup.
        if launch_requested and not state.get("instance_id"):
            reservations = ec2.describe_instances(Filters=[{"Name": "client-token", "Values": [token]}])["Reservations"]
            discovered = [i for r in reservations for i in r["Instances"]]
            if discovered:
                state["instance_id"] = discovered[0]["InstanceId"]
                state["instance_state"] = discovered[0]["State"]["Name"]
                save()
                ec2.terminate_instances(InstanceIds=[state["instance_id"]])
                state["termination_requested_at"] = timestamp()
                save()
        if not state.get("instance_id"):
            cleanup()
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"AWS GPU job failed: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
