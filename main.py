#!/usr/bin/env python3

import os
import time
import logging
import importlib.util
from git import Repo
from imap_tools import MailBox, AND
from datetime import date, timedelta
from github import Github
from utils import require

print("using config:")

RULES_DIR = "/app/rules"
LOGS_DIR = "/app/logs"

EMAIL = require("address")
IMAP_SERVER = require("imap_server")
PASSWORD = require("password")
GITHUB_TOKEN = require("token")
REPO = require("repo")
LOOKBACK_DAYS = require("lookback_days")


# set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(f"{LOGS_DIR}/handler.log"),
        logging.StreamHandler()
    ]
)

def clone_rules(user):
    repo = user.get_repo(REPO)
    clone_url = repo.clone_url.replace("https://", f"https://{GITHUB_TOKEN}@")
    Repo.clone_from(clone_url, RULES_DIR)

def create_missing_rules_repo(user):
    repo = user.create_repo(
        name=REPO,
        description="Email rules for Demail. The main branch of this repository pulled and ran accross all of your emails",
        private=True,
        auto_init=True,
    )

def repo_exists(user):
    try:
        user.get_repo(REPO)
        return True
    except Exception:
        logging.info("repo not found: ", Exception)
        return False

def setup():
    logging.info("Setting things up...")
    gh = Github(GITHUB_TOKEN)
    user = gh.get_user()

    if repo_exists(user):
        logging.info("Remote exists.") 
        if os.path.exists(RULES_DIR) and len(os.listdir(RULES_DIR)) > 0:
            logging.info("Local rules repo exists. Setup complete.")
        else:
            logging.info("No local copy. cloning...")
            clone_rules(user)

    else:
        if os.path.exists(RULES_DIR) and len(os.listdir(RULES_DIR)) > 0:
            err = "Local rules repo exists without remote. delete local copy or push to remote"
            logging.error(err)
            raise RuntimeError(err)
        else:
            logging.info(f"No remote or local rules repo. Initializing Repository at: {REPO}")
            create_missing_rules_repo(user)
            logging.info(f"Cloning to: {RULES_DIR}")
            clone_rules(user)
            logging.info("Setup Complete.")
    



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
    # pull_latest()
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

                since = date.today() - timedelta(days=int(LOOKBACK_DAYS))

                while True:
                    responses = mailbox.idle.wait(timeout=300)
                    if responses:
                        pull_latest()
                        for msg in mailbox.fetch(AND(seen=False, date_gte=since)):
                            handle_email(msg, mailbox)
                            mailbox.flag(msg.uid, ["\\Seen"], True)
        except Exception as e:
            logging.error(f"Connection error: {e}. Reconnecting in 30 seconds...")
            time.sleep(30)

if __name__ == "__main__":
    setup()
    main()
