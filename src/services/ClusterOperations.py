from botocore.exceptions import ClientError, BotoCoreError
import boto3
import logging
import re
from utils.logger import Logger

class ClusterOperations:

    def __init__(self, region):
        self.region = region
        self.logger = Logger.get_logger("eks-update")
        self.logger.info(f"Initializing ClusterOperations for region: {region}")

        self.eks_client = boto3.client("eks", region_name=region)
        self.ec2_client = boto3.client("ec2", region_name=region)
        self.ssm_client = boto3.client("ssm", region_name=region)
        self.autoscaling_client = boto3.client("autoscaling", region_name=region)
        self.sts_client = boto3.client("sts", region_name=region)
        self.organizations_client = boto3.client("organizations")
        self._account_name = None

    def get_account_name(self):
        if self._account_name:
            return self._account_name

        try:
            account_id = self.sts_client.get_caller_identity().get("Account")
        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"Error retrieving account id: {str(e)}")
            self._account_name = "unknown-account"
            return self._account_name

        try:
            response = self.organizations_client.describe_account(AccountId=account_id)
            self._account_name = response["Account"]["Name"]
            self.logger.info(f"Resolved account name: {self._account_name}")
        except (ClientError, BotoCoreError) as e:
            self.logger.warning(
                f"Could not resolve account name from Organizations, using account id {account_id}: {str(e)}"
            )
            self._account_name = account_id

        return self._account_name

    def list_eks_clusters(self):
        clusters = []
        self.logger.info(f"Listing EKS clusters in region {self.region}")
        try:
            paginator = self.eks_client.get_paginator("list_clusters")
            for page in paginator.paginate():
                for cluster in page["clusters"]:
                    self.logger.info(f"Found cluster: {cluster}")
                    clusters.append({
                        "region": self.region,
                        "cluster": cluster
                    })
        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"Error accessing region {self.region}: {str(e)}")
        return clusters

    def get_cluster_version(self, cluster_name):
        self.logger.info(f"Retrieving cluster version for {cluster_name}")
        try:
            response = self.eks_client.describe_cluster(name=cluster_name)
            version = response["cluster"]["version"]
            self.logger.info(f"Cluster {cluster_name} version: {version}")
            return version
        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"Error retrieving cluster version: {str(e)}")
            return None

    def get_nodegroups(self, cluster_name):
        self.logger.info(f"Listing nodegroups for cluster {cluster_name}")
        try:
            response = self.eks_client.list_nodegroups(clusterName=cluster_name)
            nodegroups = response["nodegroups"]
            self.logger.info(f"Nodegroups found: {nodegroups}")
            return nodegroups
        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"Error retrieving nodegroups: {str(e)}")
            return []

    def describe_nodegroup(self, cluster_name, nodegroup_name):
        self.logger.info(f"Describing nodegroup {nodegroup_name} in cluster {cluster_name}")
        try:
            response = self.eks_client.describe_nodegroup(
                clusterName=cluster_name,
                nodegroupName=nodegroup_name
            )
            return response["nodegroup"]
        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"Error describing nodegroup: {str(e)}")
            return {}

    def get_launch_template(self, nodegroup):
        self.logger.info("Retrieving launch template details from nodegroup")
        launch_template = nodegroup.get("launchTemplate", {})

        return {
            "launch_template_name": launch_template.get("name"),
            "launch_template_id": launch_template.get("id"),
            "launch_template_version": launch_template.get("version")
        }

    def get_nodegroup_ami_type(self, cluster_name, nodegroup_name):
        self.logger.info(f"Retrieving AMI type for nodegroup {nodegroup_name}")
        try:
            response = self.eks_client.describe_nodegroup(
                clusterName=cluster_name,
                nodegroupName=nodegroup_name
            )
            ami_type = response["nodegroup"]["amiType"]
            self.logger.info(f"AMI Type for {nodegroup_name}: {ami_type}")
            return ami_type
        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"Error retrieving AMI type: {str(e)}")
            return None

    def get_latest_eks_ami(self, ssm_map, ami_type, cluster_version):
        self.logger.info(f"Fetching latest EKS AMI for type {ami_type} and version {cluster_version}")
        try:
            if ami_type not in ssm_map:
                self.logger.warning(f"Unsupported AMI type: {ami_type}")
                return None

            parameter_path = ssm_map[ami_type].format(version=cluster_version)
            self.logger.info(f"Fetching SSM parameter: {parameter_path}")

            response = self.ssm_client.get_parameter(
                Name=parameter_path
            )
            ami = response["Parameter"]["Value"]

            self.logger.info(f"Latest AMI from SSM: {ami}")
            return ami

        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"Error retrieving AMI from SSM: {str(e)}")
            return None

    def get_ami_from_launch_template(self, launch_template_id, version):
        self.logger.info(f"Retrieving AMI from Launch Template {launch_template_id}, version {version}")
        try:
            response = self.ec2_client.describe_launch_template_versions(
                LaunchTemplateId=launch_template_id,
                Versions=[str(version)]
            )
            launch_template_data = response["LaunchTemplateVersions"][0]["LaunchTemplateData"]
            ami = launch_template_data.get("ImageId")

            self.logger.info(f"AMI in Launch Template: {ami}")
            return ami

        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"Error retrieving AMI from Launch Template: {str(e)}")
            return None

    def get_current_node_ami(self, nodegroup_details):
        self.logger.info("Retrieving current node AMI from running instances")
        try:
            asg_name = nodegroup_details["resources"]["autoScalingGroups"][0]["name"]
            self.logger.info(f"Auto Scaling Group: {asg_name}")

            asg = self.autoscaling_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )

            instance_ids = [
                instance["InstanceId"]
                for instance in asg["AutoScalingGroups"][0]["Instances"]
            ]

            if not instance_ids:
                self.logger.warning(f"No instances found in ASG {asg_name}")
                return None

            self.logger.info(f"Instances found: {instance_ids}")

            instance = self.ec2_client.describe_instances(
                InstanceIds=[instance_ids[0]]
            )

            ami_id = instance["Reservations"][0]["Instances"][0]["ImageId"]

            self.logger.info(f"Current node AMI: {ami_id}")

            return ami_id

        except (ClientError, BotoCoreError, KeyError, IndexError) as e:
            self.logger.error(f"Error retrieving current node AMI: {str(e)}")
            return None

    def update_managed_nodegroup(self, cluster_name, nodegroup_name, force_update=False):
        self.logger.info(
            f"Starting rolling update for nodegroup {nodegroup_name} in cluster {cluster_name} "
            f"(force={force_update})"
        )
        try:
            response = self.eks_client.update_nodegroup_version(
                clusterName=cluster_name,
                nodegroupName=nodegroup_name,
                force=force_update
            )
            update_id = response["update"]["id"]
            self.logger.info(f"Rolling update started with ID: {update_id}")
            return update_id

        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"Error updating nodegroup: {str(e)}")
            return None

    def describe_image(self, image_id, region):

        self.logger.info("Describing AMI %s in region %s", image_id, region)

        try:
            response = self.ec2_client.describe_images(
                ImageIds=[image_id]
            )

            images = response.get("Images", [])

            if not images:
                self.logger.warning("No image found for AMI %s in region %s", image_id, region)
                return None

            image = images[0]

            self.logger.debug("AMI details retrieved: %s", image)

            return {
                "ImageId": image.get("ImageId"),
                "Name": image.get("Name"),
                "Description": image.get("Description"),
                "State": image.get("State"),
                "OwnerId": image.get("OwnerId"),
                "CreationDate": image.get("CreationDate"),
                "Architecture": image.get("Architecture"),
                "PlatformDetails": image.get("PlatformDetails")
            }

        except ClientError as e:
            self.logger.error("Error describing AMI %s in region %s: %s", image_id, region, str(e))
            return None


    def get_ami_variant(self,ami_name: str) -> str:
        self.logger.info(f"Processing AMI name: {ami_name}")
        pattern = r"amazon-eks-node-([a-z0-9_]+-[a-z0-9_]+-[a-z0-9_]+)-\d+\.\d+-v\d+"
        match = re.search(pattern, ami_name)
        if match:
            variant = match.group(1).replace("-", "_").upper()
            self.logger.info(f"Extracted AMI variant: {variant}")
            return variant
        self.logger.warning(f"AMI name did not match expected pattern: {ami_name}")
        return None
    