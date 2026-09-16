import boto3
import os
import shutil


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

        print(f"Source folder not found: {SOURCE_FOLDER}")
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

            print(f"Skipped: {file_name}")
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

            print(f"Skipped (not a file): {file_name}")
            continue


        # --------------------------------------------------------
        # S3 Key
        # --------------------------------------------------------

        s3_key = S3_FOLDER + file_name


        print("\n---------------------------------------------")
        print(f"Processing file: {file_name}")
        print(f"S3 Location: s3://{BUCKET_NAME}/{s3_key}")


        # ========================================================
        # Upload File To S3
        # ========================================================

        try:

            s3.upload_file(
                local_file,
                BUCKET_NAME,
                s3_key
            )

            print("S3 upload successful!")


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

            print("File moved to processed folder.")
            print(f"Processed: {processed_file}")


        except Exception as e:

            print("S3 upload failed!")
            print(f"Error: {e}")


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

                print("File moved to rejected folder.")
                print(f"Rejected: {rejected_file}")


            except Exception as move_error:

                print("Could not move file to rejected folder.")
                print(f"Move Error: {move_error}")


    # ============================================================
    # Process Completed
    # ============================================================

    print("\n=============================================")
    print("Customer file processing completed.")
    print("=============================================")


if __name__ == "__main__":
    upload_file_to_s3()