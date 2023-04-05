import praw
import os
import openai
import time
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
user_agent = os.getenv("user_agent")
username = os.getenv("username")
password = os.getenv('password')

openai.organization = os.getenv("org_id")
openai.api_key = os.getenv("OPENAI_API_KEY")

reddit = praw.Reddit(client_id=client_id,
                     client_secret=client_secret,
                     user_agent=user_agent,
                     username=username,
                     password=password)

with open('API.txt', 'r') as f:
    API_text = f.read()

while True:
    try:  # Praw might throw errors, we want to ignore them
        subreddit = reddit.subreddit('hardwareswap')
        for submission in subreddit.stream.submissions(skip_existing=True,
                                                       pause_after=0):  # REFRESH AND LOOK FOR NEW POSTS AND PROCESS THEM
            if submission is None:
                continue
            try:
                h = submission.title.lower().find('[h]')
                w = submission.title.lower().find('[w]')
                if w > h:
                    want = submission.title.lower().split('[w]')[1]
                else:
                    want = submission.title.lower().split('[h]')[0]
            except:
                continue

            if 'paypal' or 'cash' in want.lower():  # aka if it's a selling post
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an API server."},
                        {"role": "user", "content": API_text},
                        {"role": "assistant", "content": "ready"},
                        {"role": "user", "content": submission.title + "\n" + submission.selftext}
                    ]
                )
                print(response['choices'][0]['message']['content'])
    except Exception as e:
        print(f'Reddit Error: {e}\n Continuing')
        time.sleep(2)