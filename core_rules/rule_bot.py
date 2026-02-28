"""
Watches for emails from the owner with subject 'new rule',
generates a rule with AI, opens a GitHub PR, and replies with the link.
"""

import os
import re
import logging
from datetime import datetime

import anthropic
from github import Github
from git import Repo

from utils import cfg

MODERATOR_ADDRESS = cfg['email']['moderator_address']
ANTHROPIC_API_KEY = cfg['anthropic']['api_key']
MODEL = cfg['anthropic']['model']
GITHUB_TOKEN = cfg['github']['token']
GITHUB_REPO = cfg['github']['repo']
RULES_DIR = cfg['paths']['rules_dir']
SMTP_SERVER = cfg['email']['smtp_server']
EMAIL = cfg['email']['address']

def match(msg):
    return (
        msg.from_.lower().strip() == MODERATOR_ADDRESS.lower()
        and msg.subject.strip().lower() == "new rule"
    )

def action(msg, mailbox):
    instruction = msg.text.strip()
    logging.info(f"New rule instruction: {instruction}")

    try:
        code = _generate_rule_code(instruction)
        slug = re.sub(r"[^a-z0-9_]", "", "_".join(instruction.lower().split()[:5]))
        filename = f"{slug}.py"
        pr_url = _push_and_open_pr(filename, code, instruction)

        _send_reply(
            to=msg.from_,
            subject="Re: new rule — PR ready for review",
            body=f"Your new rule is ready for review:\n\n{pr_url}\n\n"
                 f"Once merged it will be active on the next incoming email."
        )

    except Exception as e:
        logging.error(f"Failed to create rule: {e}")
        _send_reply(
            to=msg.from_,
            subject="Re: new rule — something went wrong",
            body=f"Failed to generate rule:\n\n{e}"
        )

def _generate_rule_code(instruction):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=MODEL
        max_tokens=1024,
        messages=[{"role": "user", "content": f"""
You are a Python code generator for an email automation system.

Generate a Python module with exactly two functions:

1. `match(msg) -> bool` — returns True if this rule applies to the email
2. `action(msg, mailbox)` — performs the desired action. action should True if other actions can also run on top of this email. Rules should return False if taking a permanent action, such as deleting the received email.

The `msg` object (imap_tools) has:
- msg.from_       sender address string
- msg.to          list of recipient addresses
- msg.subject     subject string
- msg.text        plain text body
- msg.date        datetime object
- msg.uid         unique message id

The `mailbox` object is a live imap_tools MailBox. Useful methods:
- mailbox.delete([msg.uid])
- mailbox.flag(msg.uid, ['\\\\Seen'], True)
- mailbox.move(msg.uid, 'FolderName')

SMTP details if you need to send a reply:
- Server: {SMTP_SERVER}, Port: 587, Login: {EMAIL} / use env var EMAIL_PASSWORD

Rules:
- Output only valid Python, no markdown, no explanation
- Add a module docstring describing what the rule does
- Keep it simple and focused

Instruction: {instruction}
"""}]
    )
    return response.content[0].text.strip()

def _push_and_open_pr(filename, code, instruction):
    repo = Repo(RULES_DIR)
    origin = repo.remotes.origin
    origin.pull("main")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-z0-9_]", "", "_".join(instruction.lower().split()[:4]))
    branch_name = f"rule/{slug}-{timestamp}"

    new_branch = repo.create_head(branch_name, "main")
    new_branch.checkout()

    filepath = os.path.join(RULES_DIR, filename)
    with open(filepath, "w") as f:
        f.write(code)

    repo.index.add([filepath])
    repo.index.commit(f"Add rule: {instruction[:60]}")
    origin.push(branch_name)

    gh = Github(GITHUB_TOKEN)
    pr = gh.get_repo(GITHUB_REPO).create_pull(
        title=f"New rule: {instruction[:60]}",
        body=f"**Instruction:**\n\n> {instruction}\n\nReview before merging.",
        head=branch_name,
        base="main"
    )

    repo.heads.main.checkout()
    return pr.html_url

def _send_reply(to, subject, body):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart()
    msg["From"] = EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_SERVER, 587) as server:
        server.starttls()
        server.login(EMAIL, os.environ["EMAIL_PASSWORD"])
        server.send_message(msg)
