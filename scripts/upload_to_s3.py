import boto3
import os
import shutil

try:
    from scripts.logging_config import setup_logging, get_logger
except ImportError:
    from logging_config import setup_logging, get_logger


# ============================================================
# Configuration
# ============================================================

#BUCKET_NAME = "amz-s3-data-snow"
#BUCKET_NAME = "amz-s3-data-snow-ap-singapore"
BUCKET_NAME = "amz-s3-data-snow-ap-thailand"

SOURCE_FOLDER = r"C:\Users\user\Desktop\DE\Projects\EnterpriseDataProcessing&ReportingPlatform_EDPRP\data\raw\customers"

PROCESSED_FOLDER = r"C:\Users\user\Desktop\DE\Projects\EnterpriseDataProcessing&ReportingPlatform_EDPRP\data\processed\customers"

REJECTED_FOLDER = r"C:\Users\user\Desktop\DE\Projects\EnterpriseDataProcessing&ReportingPlatform_EDPRP\data\rejected\customers"

S3_FOLDER = "raw/customers/"

logger = get_logger()


def upload_file_to_s3():
    # ============================================================
    # Create S3 Client
    # ============================================================

    s3 = boto3.client("s3")


    # ============================================================
    # Create Archive Folders If They Don't Exist
    # ============================================================

    os.makedirs(PROCESSED_FOLDER, exist_ok=True)
    os.makedirs(REJECTED_FOLDER, exist_ok=True)


    # ============================================================
    # Check Source Folder
    # ============================================================

    if not os.path.exists(SOURCE_FOLDER):

        logger.error("Source folder not found: %s", SOURCE_FOLDER)
        exit()


    # ============================================================
    # Get All Files From Source Folder
    # ============================================================

    files = os.listdir(SOURCE_FOLDER)


    # ============================================================
    # Process Files
    # ============================================================

    for file_name in files:

        # --------------------------------------------------------
        # Only process files starting with customer_
        # --------------------------------------------------------

        if not file_name.startswith("customer_"):

            logger.info("Skipped: %s", file_name)
            continue


        # --------------------------------------------------------
        # Create complete local file path
        # --------------------------------------------------------

        local_file = os.path.join(
            SOURCE_FOLDER,
            file_name
        )


        # --------------------------------------------------------
        # Make sure it is actually a file
        # --------------------------------------------------------

        if not os.path.isfile(local_file):

            logger.info("Skipped (not a file): %s", file_name)
            continue


        # --------------------------------------------------------
        # S3 Key
        # --------------------------------------------------------

        s3_key = S3_FOLDER + file_name


        print("\n---------------------------------------------")
        logger.info("Processing file: %s", file_name)
        logger.info("S3 Location: s3://%s/%s", BUCKET_NAME, s3_key)


        # ========================================================
        # Upload File To S3
        # ========================================================

        try:

            s3.upload_file(
                local_file,
                BUCKET_NAME,
                s3_key
            )

            logger.info("S3 upload successful!")


            # ====================================================
            # Move File To Processed Folder
            # ====================================================

            processed_file = os.path.join(
                PROCESSED_FOLDER,
                file_name
            )

            shutil.move(
                local_file,
                processed_file
            )

            logger.info("File moved to processed folder.")
            logger.info("Processed: %s", processed_file)


        except Exception as e:

            logger.error("S3 upload failed!")
            logger.error("Error: %s", e)


            # ====================================================
            # Move File To Rejected Folder
            # ====================================================

            try:

                rejected_file = os.path.join(
                    REJECTED_FOLDER,
                    file_name
                )

                shutil.move(
                    local_file,
                    rejected_file
                )

                logger.info("File moved to rejected folder.")
                logger.info("Rejected: %s", rejected_file)


            except Exception as move_error:

                logger.error("Could not move file to rejected folder.")
                logger.error("Move Error: %s", move_error)


    # ============================================================
    # Process Completed
    # ============================================================

    print("\n=============================================")
    logger.info("Customer file processing completed.")
    print("=============================================")


if __name__ == "__main__":
    setup_logging()
    upload_file_to_s3()