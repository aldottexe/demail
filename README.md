# demail
Bend your inbox to your will. Demail is an intelligent, infinitely customizable mailbox manager and companion. Above all else, it is private and locally hosted.
# About
Demail is not a mail server. it is a compaion server that monitors an email inbox. Create rules in the form of python scripts to in response to a received email. 
## Rules
Rules are small python script that run in response to an email being received. The behavior is infinitely customizable. 
A rule can look like:
- Delete emails from "scammer@gmail.com"
- for the next 2 weeks, respond with "sorry I'm out of office"
Rules are stored in a designated Github repo for accessibility. 
# Rule Creation Bot
Demail comes prepackaged with a rule creation bot. Email yourself a prompt for a rule, and the prompt will be offloaded to an LLM. The bot then creates a pull request with the generated script.
