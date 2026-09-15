import boto3
import os


# ==============================
# Configuration
# ==============================

BUCKET_NAME = "amz-s3-data-snow"
LOCAL_FILE = r"C:\Users\user\Desktop\DE\Projects\EnterpriseDataProcessing&ReportingPlatform_EDPRP\data\raw\customers\customer_master_150926_0947.csv"
S3_KEY = "raw/customers/customer_master_150926_0947.csv"


# ==============================
# Create S3 Client
# ==============================

s3 = boto3.client("s3")


# ==============================
# Check Local File
# ==============================

if not os.path.exists(LOCAL_FILE):
    print(f"File not found: {LOCAL_FILE}")
    exit()


# ==============================
# Upload File
# ==============================

try:

    s3.upload_file(
        LOCAL_FILE,
        BUCKET_NAME,
        S3_KEY
    )

    print("CSV file uploaded successfully!")
    print(f"Bucket : {BUCKET_NAME}")
    print(f"S3 Key : {S3_KEY}")

except Exception as e:

    print("Error while uploading file:")
    print(e)