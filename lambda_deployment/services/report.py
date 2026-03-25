import threading
from tabulate import tabulate
from utils.logger import Logger

class UpgradeReport:

    def __init__(self):
        self.records = []
        self.triggered_updates = []
        self.lock = threading.Lock()
        self.logger = Logger.get_logger("eks-update")


    def add_record(self, account_name, region, cluster, nodegroup, current_ami, latest_ami):

        record = {
            "Account Name": account_name,
            "Region": region,
            "Cluster": cluster,
            "Nodegroup": nodegroup,
            "Current AMI": current_ami,
            "Latest AMI": latest_ami,
            "Needs Update": current_ami != latest_ami
        }

        # Ensure only one thread writes at a time
        with self.lock:
            self.records.append(record)

    def add_triggered_update(self, account_name, region, cluster, nodegroup, update_id=None):

        record = {
            "Account Name": account_name,
            "Region": region,
            "Cluster": cluster,
            "Nodegroup": nodegroup,
            "Update ID": update_id or "N/A"
        }

        with self.lock:
            self.triggered_updates.append(record)

    def print_report(self):

        if not self.records:
            print("No records found")
            return

        print("\n========== EKS NODEGROUP AMI REPORT ==========\n")

        print(tabulate(self.records, headers="keys", tablefmt="grid"))

    def print_triggered_updates_report(self):

        print("\n========== EKS NODEGROUP UPDATE TRIGGER REPORT ==========\n")

        if not self.triggered_updates:
            print("No nodegroups triggered for update")
            return

        print(tabulate(self.triggered_updates, headers="keys", tablefmt="grid"))
        