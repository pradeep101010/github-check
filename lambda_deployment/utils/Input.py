# Regions in Scope
DEFAULT_REGIONS = ["us-east-1", "us-east-2", "eu-central-1", "us-west-2", "ap-south-1"]

# AMI in Parameter Store
AMI_TYPE_SSM_MAP: dict[str, str] = {
    "AL2_x86_64": "/aws/service/eks/optimized-ami/{version}/amazon-linux-2/recommended/image_id",
    "AL2_x86_64_GPU": "/aws/service/eks/optimized-ami/{version}/amazon-linux-2-gpu/recommended/image_id",
    "AL2_ARM_64": "/aws/service/eks/optimized-ami/{version}/amazon-linux-2-arm64/recommended/image_id",
    "AL2023_x86_64_STANDARD": "/aws/service/eks/optimized-ami/{version}/amazon-linux-2023/x86_64/standard/recommended/image_id",
    "AL2023_ARM_64_STANDARD": "/aws/service/eks/optimized-ami/{version}/amazon-linux-2023/arm64/standard/recommended/image_id",
    "BOTTLEROCKET_x86_64": "/aws/service/bottlerocket/aws-k8s-{version}/x86_64/latest/image_id",
    "BOTTLEROCKET_ARM_64": "/aws/service/bottlerocket/aws-k8s-{version}/arm64/latest/image_id"
}

# S3 Report Constants
REPORT_BUCKET_NAME = "reports-upload-24"
REPORT_PREFIX = "test"
