import json
import praw
import random

with open("reddit_credentials.json", "r") as f:
    reddit_credentials = json.load(f)

def get_reddit_instance(account):
    return praw.Reddit(
        client_id=reddit_credentials[account]["client_id"],
        client_secret=reddit_credentials[account]["client_secret"],
        user_agent=reddit_credentials[account]["user_agent"],
        username=reddit_credentials[account]["username"],
        password=reddit_credentials[account]["password"]
    )

def send_pm(sender, recipient, subject, message):
    reddit = get_reddit_instance(sender)
    reddit.redditor(recipient).message(subject=subject, message=message)
    print(f"Message sent to u/{recipient} from {sender}!")
# example usage: send_pm(sender="account1", recipient="gpjoe278",
#                        subject="TEST1", message="hi from u/pcbeest! this is a test.")

def random_send_pm(recipient, subject, message):
     senders = list(reddit_credentials.keys())
     sender = senders[random.randint(0, len(senders)-1)]  # choose a random sender from the list senders

     reddit = get_reddit_instance(sender)
     reddit.redditor(recipient).message(subject=subject, message=message)
     print(f"Message sent to u/{recipient} from {sender}!")



# this function is currently unused.
def generate_pm_message(item_name, item_price, paypal_email, zipcode):
        message = f"""Hey! I'm interested in the {item_name} you listed for {item_price}.
        If you're OK with shipping to {zipcode}, send me a Paypal invoice to {paypal_email}! Thanks!"""

        return message