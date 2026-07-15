# Functions

# download the file from bucket

# take an input file, scan it for viruses, and output a report

# update the tag from scan output to the file (original)

# Scanned = true, Result = INFECTED/CLEAN/ERROR

# update the notification system with the scan result

# update the db of clamav

import os
import subprocess
import boto3

bucket = "myawsinitialbucket"
key = "clean.txt"
#key = "dirty.txt"
destination = "tmp/clean.txt"
#destination = "tmp/dirty.txt"

# ClamAV 1.5+ requires a certs directory to verify the virus database's
# signature. Keep it inside the project instead of relying on
# /etc/clamav/certs existing (and being writable) on the host.
CERTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "certs")

s3 = boto3.client("s3")


def download_file_from_bucket(bucket, key, destination):
    s3.download_file(bucket, key, destination)


def scan_file(filename):
    os.makedirs(CERTS_DIR, exist_ok=True)

    output = subprocess.run(
        ["clamscan", f"--cvdcertsdir={CERTS_DIR}", filename],
        capture_output=True,
        text=True,
    )

    if output.returncode == 1:
        return "INFECTED: "
    elif output.returncode == 0:
        return "CLEAN: "
    else:
        print(f"clamscan error (exit code {output.returncode}) scanning {filename}")
        print(output.stdout)
        print(output.stderr)
        return "ERROR: "


def tag_file_with_scan_result(bucket, key, tags):
    s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": tags})


download_file_from_bucket(bucket, key, destination)

result = scan_file(destination)

tags = [{"Key": "Scanned", "Value": "True"}, {"Key": "Result", "Value": result}]

tag_file_with_scan_result(bucket, key, tags)