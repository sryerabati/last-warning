#!/usr/bin/env python3
"""Read-only AWS access, GPU quota, availability and live price checks. Creates nothing."""
import argparse
import json
import os
import sys


def get_hourly_price(session, region, instance_type):
    pricing = session.client("pricing", region_name="us-east-1")
    filters = [
        {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
        {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
        {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
        {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
        {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
        {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
    ]
    result = pricing.get_products(ServiceCode="AmazonEC2", Filters=filters, MaxResults=100)
    prices = []
    for product in result["PriceList"]:
        for term in json.loads(product)["terms"].get("OnDemand", {}).values():
            for dimension in term["priceDimensions"].values():
                if dimension["unit"] == "Hrs" and "USD" in dimension["pricePerUnit"]:
                    prices.append(float(dimension["pricePerUnit"]["USD"]))
    if not prices or len(set(prices)) != 1:
        raise ValueError("Could not obtain one unambiguous current Linux On-Demand hourly price")
    return prices[0]


def main():
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-2"))
    parser.add_argument("--instance-type", default="g5.2xlarge")
    parser.add_argument("--max-hours", type=float, default=6)
    parser.add_argument("--project-budget", type=float, default=30)
    args = parser.parse_args()
    if not 0 < args.max_hours <= 12 or not 0 < args.project_budget <= 30:
        parser.error("Use a runtime of 0–12 hours and project budget up to $30")
    session = boto3.Session(region_name=args.region)
    # STS identity failure must abort before any other AWS work.
    identity = session.client("sts").get_caller_identity()
    output = {"account": identity["Account"], "region": args.region, "resource_creation": False,
              "target_project_budget_usd": args.project_budget, "checks": {}}
    checks = output["checks"]
    actions = {
        "instance_type": lambda: session.client("ec2").describe_instance_types(InstanceTypes=[args.instance_type])["InstanceTypes"],
        "availability_zones": lambda: session.client("ec2").describe_instance_type_offerings(
            LocationType="availability-zone", Filters=[{"Name": "instance-type", "Values": [args.instance_type]}])["InstanceTypeOfferings"],
        "gpu_quotas": lambda: [q for page in session.client("service-quotas").get_paginator("list_service_quotas").paginate(ServiceCode="ec2")
                                for q in page["Quotas"] if "G and VT" in q["QuotaName"]],
        "hourly_price_usd": lambda: get_hourly_price(session, args.region, args.instance_type),
    }
    for name, action in actions.items():
        try:
            checks[name] = action()
        except (BotoCoreError, ClientError, ValueError) as error:
            checks[name] = {"error": str(error)}
    price = checks.get("hourly_price_usd")
    if isinstance(price, (float, int)):
        output["compute_estimate_usd"] = round(price * args.max_hours, 2)
        output["remaining_for_storage_transfer_and_other_work_usd"] = round(args.project_budget - price * args.max_hours, 2)
        output["within_compute_allocation"] = price * args.max_hours <= min(20, args.project_budget - 10)
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"AWS preflight failed: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
