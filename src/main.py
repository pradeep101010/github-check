from utils.logger import Logger
from concurrent.futures import ThreadPoolExecutor
import os
import json
from utils.Input import DEFAULT_REGIONS, AMI_TYPE_SSM_MAP, REPORT_BUCKET_NAME, REPORT_PREFIX
from services.ClusterOperations import ClusterOperations
from services.report import UpgradeReport
from utils.slack import SlackNotifier
from utils.s3_report_uploader import S3ReportUploader

DRY_RUN = False   # Toggle this to enable/disable upgrades
logger = Logger.get_logger("eks-update")

excluded_clusters_env = os.getenv("EXCLUDED_CLUSTERS", "[]")
try:
    EXCLUDED_CLUSTERS = json.loads(excluded_clusters_env)
    if not isinstance(EXCLUDED_CLUSTERS, list):
        EXCLUDED_CLUSTERS = []
except json.JSONDecodeError:
    EXCLUDED_CLUSTERS = []

if EXCLUDED_CLUSTERS:
    logger.info(f"Excluded clusters: {EXCLUDED_CLUSTERS}")

report = UpgradeReport()
slack_notifier = None
s3_report_uploader = S3ReportUploader(REPORT_BUCKET_NAME, REPORT_PREFIX)

slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
if slack_webhook_url:
    slack_notifier = SlackNotifier(slack_webhook_url)
else:
    logger.info("SLACK_WEBHOOK_URL not set. Slack notifications are disabled.")

def should_skip_update(cluster_name: str, node_group: str, ami_type: str) -> tuple[bool, str, str]:
    if ami_type and str(ami_type).upper() == "CUSTOM":
        return True, (
            f"Custom AMI type (created by launch template) is not supported for node group update: "
            f"{cluster_name}/{node_group}"
        ), "warning"

    if cluster_name in EXCLUDED_CLUSTERS:
        return True, f"Cluster {cluster_name} is in exclusion list; skipping update for {cluster_name}/{node_group}", "info"

    if DRY_RUN:
        return True, f"DRY RUN ENABLED: Skipping upgrade for {cluster_name}/{node_group}", "info"

    return False, "", ""

def process_region(region):
    logger.info(f"Processing region {region}")

    ops = ClusterOperations(region)
    account_name = ops.get_account_name()
    clusters_list = ops.list_eks_clusters()

    if not clusters_list:
        logger.info(f"No clusters found in region {region}")
        return

    for cluster in clusters_list:
        cluster_name = cluster.get("cluster")
        cluster_version = ops.get_cluster_version(cluster_name)
        node_groups = ops.get_nodegroups(cluster_name)

        for node_group in node_groups:
            node_group_details = ops.describe_nodegroup(cluster_name, node_group)
            ami_type = ops.get_nodegroup_ami_type(cluster_name, node_group)

            latest_ami = ops.get_latest_eks_ami(
                AMI_TYPE_SSM_MAP,
                ami_type,
                cluster_version
            )

            current_ami = ops.get_current_node_ami(node_group_details)

            report.add_record(
                account_name,
                region,
                cluster_name,
                node_group,
                current_ami,
                latest_ami
            )

            if current_ami != latest_ami:
                logger.info(f"AMI mismatch detected for {cluster_name}/{node_group}")

                skip, msg, level = should_skip_update(cluster_name, node_group, ami_type)
                if skip:
                    if level == "warning":
                        logger.warning(msg)
                    else:
                        logger.info(msg)
                    continue

                update_id = ops.update_managed_nodegroup(cluster_name, node_group, force_update=True)
                if update_id:
                    report.add_triggered_update(
                        account_name,
                        region,
                        cluster_name,
                        node_group,
                        update_id,
                    )


def main(event=None, context=None):
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_region, DEFAULT_REGIONS)

    report.print_report()
    report.print_triggered_updates_report()

    uploaded_key = s3_report_uploader.upload_triggered_updates_report(
        report.triggered_updates
    )
    if uploaded_key:
        logger.info(
            f"Triggered updates CSV report available at s3://{REPORT_BUCKET_NAME}/{uploaded_key}"
        )

    if slack_notifier:
        slack_notifier.send_report(report)

def lambda_handler(event, context):
    main()
    