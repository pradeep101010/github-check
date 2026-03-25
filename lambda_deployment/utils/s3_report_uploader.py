import csv
import io
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

import boto3

from utils.logger import Logger
from utils.Input import REPORT_BUCKET_NAME, REPORT_PREFIX

class S3ReportUploader:
    def __init__(self, bucket_name: str = None, prefix: str = None):
        if not bucket_name:
            bucket_name = REPORT_BUCKET_NAME
        if not prefix:
            prefix = REPORT_PREFIX

        self.bucket_name = bucket_name
        self.prefix = prefix.strip("/")
        self.s3_client = boto3.client("s3")
        self.logger = Logger.get_logger("eks-update")

    def _build_unique_key(self) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        unique_id = uuid4().hex[:8]
        return f"{self.prefix}/mng_update_report_{timestamp}_{unique_id}.csv"

    def _build_csv_content(self, triggered_updates: List[Dict]) -> str:
        headers = ["Account Name", "Region", "Cluster", "Nodegroup", "Update ID"]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=headers)
        writer.writeheader()

        for item in triggered_updates:
            writer.writerow(
                {
                    "Account Name": item.get("Account Name", ""),
                    "Region": item.get("Region", ""),
                    "Cluster": item.get("Cluster", ""),
                    "Nodegroup": item.get("Nodegroup", ""),
                    "Update ID": item.get("Update ID", ""),
                }
            )

        return buffer.getvalue()

    def upload_triggered_updates_report(self, triggered_updates: List[Dict]) -> Optional[str]:
        key = self._build_unique_key()
        csv_content = self._build_csv_content(triggered_updates)

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=csv_content.encode("utf-8"),
                ContentType="text/csv",
            )
            self.logger.info(
                f"Triggered updates report uploaded to s3://{self.bucket_name}/{key}"
            )
            return key
        except Exception as exc:
            self.logger.error(f"Failed to upload triggered updates report to S3: {exc}")
            return None
