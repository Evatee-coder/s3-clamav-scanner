# Functions

# download the file from bucket

# take an input file, scan it for viruses, and output a report

# update the tag from scan output to the file (original)

# Scanned = true, Result = INFECTED/CLEAN/ERROR

# update the notification system with the scan result

# update the db of clamav


#### Below code is better implementation of automation of clamav ####

import subprocess
import boto3
import os
import json
import sys
import argparse


# ClamAV 1.5+ requires a certs directory to verify the virus database's
# signature. Keep it inside the project instead of relying on
# /etc/clamav/certs existing (and being writable) on the host.
CERTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")

# Account-specific config is pulled from the environment instead of being
# hardcoded, so this file can be committed/pushed without leaking bucket
# names or account details. Set these before running (see .env.example).
LANDING_BUCKET = os.environ.get("LANDING_BUCKET")
CLEAN_BUCKET = os.environ.get("CLEAN_BUCKET")
NOTIFICATION_QUEUE = os.environ.get("NOTIFICATION_QUEUE", "scan-notification-queue")

#key = "clean.txt"
key = "dirty.txt"
#destination = "tmp/clean.txt"
destination = "tmp/dirty.txt"

s3 = boto3.client("s3")
sqs = boto3.client("sqs")


def download_file_from_bucket(bucket, key, destination):
    try:
        s3.download_file(bucket, key, destination)
        print(f"File {key} downloaded: {destination}")
    except Exception as e:
        print(f"Error downloading file: {e}")



def scan_file(filename):
    os.makedirs(CERTS_DIR, exist_ok=True)

    output = subprocess.run(
        ["clamscan", f"--cvdcertsdir={CERTS_DIR}", filename],
        capture_output=True,
        text=True,
    )
    print(f"File {filename} scanned")

    if output.returncode == 1:
        return "INFECTED"
    elif output.returncode == 0:
        return "CLEAN"
    else:
        print(f"clamscan error (exit code {output.returncode}) scanning {filename}")
        print(output.stdout)
        print(output.stderr)
        return "ERROR"



def tag_file_with_scan_result(bucket, key, tags):
    s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": tags})
    print(f"tagged {key} ")



def upload_to_s3(local_file, bucket, key):
    # upload file to bucket
    try:
        response = s3.upload_file(local_file, bucket, key)
        print(f"File {key} uploaded to {bucket}")
    except Exception as e:
        print(e)
    else:
        print("File uploaded successfully")



def notify_queue_if_infected(queue_name, filename):
    queue_url = sqs.get_queue_url(QueueName=queue_name)["QueueUrl"]
    pay_load = {"file": filename, "status": "INFECTED"}
    response = sqs.send_message(QueueUrl=queue_url, MessageBody=str(pay_load))
    print(f"Notified the queue: {queue_url}")
    return response.get("MessageId")



def require_config():
    missing = [
        name
        for name, value in [("LANDING_BUCKET", LANDING_BUCKET), ("CLEAN_BUCKET", CLEAN_BUCKET)]
        if not value
    ]
    if missing:
        sys.exit(f"Missing required environment variable(s): {', '.join(missing)}")


def scan():
    require_config()

    download_file_from_bucket(LANDING_BUCKET, key, destination)

    result = scan_file(destination)

    if result == "CLEAN":
        upload_to_s3(destination, CLEAN_BUCKET, key)

    if result == "INFECTED":
        notify_queue_if_infected(NOTIFICATION_QUEUE, destination)

    tags = [
        {"Key": "Scanned", "Value": "True"},
        {"Key": "Result", "Value": result},
        ]

    tag_file_with_scan_result(LANDING_BUCKET, key, tags)



def update_db():
    output = subprocess.run(["freshclam"], capture_output=True, text=True)

    if output.returncode == 1:
        sys.exit
    elif output.returncode == 0:
        print("Database is up to date")



def parse_args():
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description="ClamAV Automation Script")
    # Add arguments
    parser.add_argument("job", nargs='?', type=str, choices=["scan", "update"])
    return parser.parse_args()



def run():
    try:
        args = parse_args()
    except Exception as e:
        print(f"Argument parsing error: {e}")
    if args.job == "scan":
        scan()
    elif args.job == "update":
        update_db()
    else:
        print("Invalid job type. Use 'scan' or 'update'.")
   

if __name__ == "__main__":
    run()



