import requests
from bs4 import BeautifulSoup
import tweepy
import smtplib
import time
import subprocess
import os
import glob
import random
import shutil
from typing import List

# Twitter API credentials
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

# Email credentials and settings
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENTS = os.getenv("EMAIL_RECIPIENTS").split(",")
EMAIL_SUBJECT = "Mt. Rose Lift Status Update"


# Notification systems
# NOTIFICATION_SYSTEMS = ["twitter", "email", "local_log"]
NOTIFICATION_SYSTEMS = os.getenv("NOTIFICATION_SYSTEMS").split(",")

VPN_SWITCH_INTERVAL = int(os.getenv("VPN_SWITCH_INTERVAL"))

UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL"))
UPDATE_INTERVAL_VARIATION = 0.2 * UPDATE_INTERVAL  # seconds


VPN_CONFIG_DIR = os.getenv("VPN_CONFIG_DIR")
VPN_CREDENTIALS_FILE = os.getenv("VPN_CREDENTIALS_FILE")


def get_random_vpn_config(config_dir: str) -> str:
    configs = [file for file in os.listdir(config_dir) if file.endswith(".ovpn")]
    return os.path.join(config_dir, random.choice(configs))


def connect_to_vpn(config_path: str) -> subprocess.Popen:
    # Check if sudo is available
    sudo_available = shutil.which("sudo") is not None

    if sudo_available:
        command = [
            "sudo",
            "openvpn",
            "--config",
            config_path,
            "--auth-user-pass",
            VPN_CREDENTIALS_FILE,
        ]
    else:
        command = [
            "openvpn",
            "--config",
            config_path,
            "--auth-user-pass",
            VPN_CREDENTIALS_FILE,
        ]
    logging.info(" ".join(command))

    # Start the VPN connection process
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
    )

    # Wait for the VPN connection to be established or fail
    while True:
        output = process.stdout.readline().strip()
        if "Initialization Sequence Completed" in output:
            time.sleep(2)
            logging.info("VPN connection established")
            break
        elif "error" in output.lower():
            process.terminate()
            raise Exception(f"VPN connection failed: {output}")
        elif process.poll() is not None:
            logging.error(output.strip())
            for output in process.stdout.readlines():
                logging.error(output.strip())
            for output in process.stderr.readlines():
                logging.error(output.strip())
            raise Exception(
                "VPN process exited before connection was established: "
                + str(process.poll())
            )

    # Log the current IP address
    ip = requests.get("https://checkip.amazonaws.com").text.strip()
    logging.info(f"VPN connected, current IP address: {ip}")

    return process


def log_vpn_output(output_stream, prefix):
    for output in output_stream:
        message = output.strip()
        logging.info(f"{prefix}{message}")


def authenticate_twitter():
    auth = tweepy.OAuthHandler(API_KEY, API_SECRET_KEY)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    return api


def send_email(subject, body):
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        email_message = f"Subject: {subject}\n\n{body}"
        server.sendmail(EMAIL_USER, EMAIL_RECIPIENTS, email_message)


def log_to_file(message):
    with open("mt_rose_lift_status.log", "a") as log_file:
        log_file.write(f"{time.ctime()} - {message}\n")


def notify(message):
    if "twitter" in NOTIFICATION_SYSTEMS:
        api = authenticate_twitter()
        api.update_status(message)

    if "email" in NOTIFICATION_SYSTEMS:
        send_email(EMAIL_SUBJECT, message)

    if "local_log" in NOTIFICATION_SYSTEMS:
        log_to_file(message)


import random


def get_lift_status():
    url = "https://skirose.com/snow-report/"

    # List of user agents to choose from
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    ]

    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
    }

    page = requests.get(url, headers=headers)
    soup = BeautifulSoup(page.content, "html.parser")
    lift_status_section = soup.find(id="lift-status")
    lift_statuses = {}

    if lift_status_section is not None:
        for row in lift_status_section.find_all(class_="rose-data pad-12 row b-border"):
            lift_name = row.find(class_="rose-name").text.strip()
            lift_status = (
                row.find(class_="column").find_next_sibling("div").text.strip()
            )
            lift_statuses[lift_name] = lift_status
    else:
        print(
            "Error: Unable to find the lift status section. The structure of the webpage might have changed."
        )
        if "local_log" in NOTIFICATION_SYSTEMS:
            log_to_file(
                "Error: Unable to find the lift status section. The structure of the webpage might have changed."
            )

    return lift_statuses


def check_lift_status_changes(current_statuses, last_statuses):
    changes = []
    for lift_name, current_status in current_statuses.items():
        last_status = last_statuses.get(lift_name)
        if last_status and current_status != last_status:
            changes.append((lift_name, current_status))

    return changes


def format_lift_statuses(lift_statuses):
    formatted_statuses = "Current lift statuses:\n"
    for lift_name, status in lift_statuses.items():
        formatted_statuses += f"{lift_name}: {status}\n"
    return formatted_statuses


import logging
import sys


def main():
    # Initialize logging to console
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Check if VPN should be used
    use_vpn = bool(os.getenv("USE_VPN", False))

    # Initialize the VPN connection
    if use_vpn:
        random_config = get_random_vpn_config(VPN_CONFIG_DIR)
        logging.info(f"Connecting to {os.path.basename(random_config)}")
        vpn_process = connect_to_vpn(random_config)
        time.sleep(10)  # Wait for VPN connection to establish

    last_statuses = get_lift_status()
    pretty_statuses = format_lift_statuses(last_statuses)
    logging.info(pretty_statuses)

    next_vpn_switch = time.time() + VPN_SWITCH_INTERVAL

    while True:
        update_interval = UPDATE_INTERVAL + random.randint(
            -UPDATE_INTERVAL_VARIATION, UPDATE_INTERVAL_VARIATION
        )
        time.sleep(update_interval)  # Check with varied intervals

        if use_vpn and time.time() > next_vpn_switch:
            random_config = get_random_vpn_config(VPN_CONFIG_DIR)
            logging.info(f"Connecting to {os.path.basename(random_config)}")
            vpn_process.terminate()
            vpn_process = connect_to_vpn(random_config)
            time.sleep(10)  # Wait for VPN connection to establish
            next_vpn_switch = time.time() + VPN_SWITCH_INTERVAL

        current_statuses = get_lift_status()

        # Log the fetched statuses in a pretty way
        pretty_statuses = format_lift_statuses(current_statuses)
        logging.info(pretty_statuses)
        if "local_log" in NOTIFICATION_SYSTEMS:
            log_to_file(pretty_statuses)

        changes = check_lift_status_changes(current_statuses, last_statuses)
        if changes:
            messages = [
                f"Lift status update: {lift_name} is now {new_status}."
                for lift_name, new_status in changes
            ]
            message = " ".join(messages)
            notify(message)
            logging.info(f"Notification sent: {message}")

        last_statuses = current_statuses


if __name__ == "__main__":
    main()
