#Have you tried running the script using the command below? It should execute the main.py script and start the pipeline.
#python ./scripts/main.py

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.upload_to_s3 import upload_file_to_s3
#from scripts.snowflake_load import load_data_into_snowflake



def main():
    print("Starting EDPRP pipeline...")

    upload_file_to_s3()
    #load_data_into_snowflake()

    print("Pipeline completed successfully.")


if __name__ == "__main__":
    main()

