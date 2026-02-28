#!/usr/bin/env python3

import os
import time
import logging
import importlib.util
from git import Repo
from imap_tools import MailBox, AND
from utils import cfg

print(cfg)

RULES_DIR = cfg['paths']['rules_dir']
EMAIL = cfg['email']['address']
IMAP_SERVER = cfg['email']['imap_server']
PASSWORD = cfg['email']['password']


# set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/handler.log"),
        logging.StreamHandler()
    ]
)

# pull for function updates -- remove if adding GH Action
# might just be easier to make a filter that pulls so you don't have to expose the port
def pull_latest():
    Repo(RULES_DIR).remotes.origin.pull("main")
    logging.info("Pulled latest from main")

def load_rules():

    rule_paths = []

    # index core plugins
    for path in os.listdir("./core_rules"):
        if path.endswith(".py") and not path.startswith("_"):
            rule_paths.append(os.path.join("./core_rules", path))

    # index personal plugins
    for path in os.listdir(RULES_DIR):
        if path.endswith(".py") and not path.startswith("_"):
            rule_paths.append(os.path.join(RULES_DIR, path))

    rules = []

    # import the modules
    for path in rule_paths:
        # find the module's spec (blueprint) via the location
        spec = importlib.util.spec_from_file_location(path[:-3], path)
        if spec:
            # create a place to store the ran code
            module = importlib.util.module_from_spec(spec)
            try:
                # run the code, and place store the objects n the module
                spec.loader.exec_module(module)
                # check that the necessary functions are present
                if hasattr(module, "match") and hasattr(module, "action"):
                    rules.append((path[:-3], module))
                    logging.info(f"Loaded rule: {path}")
            except Exception as e:
                logging.error(f"Failed to load rule {path}: {e}")
    return rules

def handle_email(msg, mailbox):
    logging.info(f"New email — From: {msg.from_} | Subject: {msg.subject}")
    pull_latest()
    for name, rule in load_rules():
        try:
            if rule.match(msg):
                logging.info(f"Rule '{name}' matched")
                rule.action(msg, mailbox)
        except Exception as e:
            logging.error(f"Error in rule '{name}': {e}")

def main():
    logging.info("Starting email handler...")
    while True:
        try:
            with MailBox(IMAP_SERVER).login(EMAIL, PASSWORD) as mailbox:
                logging.info("Connected. Listening for new emails...")
                while True:
                    responses = mailbox.idle.wait(timeout=300)
                    if responses:
                        for msg in mailbox.fetch(AND(seen=False)):
                            handle_email(msg, mailbox)
                            mailbox.flag(msg.uid, ["\\Seen"], True)
        except Exception as e:
            logging.error(f"Connection error: {e}. Reconnecting in 30 seconds...")
            time.sleep(30)

if __name__ == "__main__":
    main()
