import re
import praw
import os
import openai
import time
import json
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit

from thread_signal import Signal


def main(socketio: SocketIO = None) -> None:
    print("Thread started")
    load_dotenv()

    client_id = os.getenv("client_id")
    client_secret = os.getenv("client_secret")
    user_agent = os.getenv("user_agent")
    username = os.getenv("reddit_username")
    password = os.getenv('password')

    openai.organization = os.getenv("org_id")
    openai.api_key = os.getenv("OPENAI_API_KEY")

    #       search for keywords, but not nxn (RAM)
    regex = r'(bought for |sold for |asking( for)? |selling for |shipped |for |\$(\s)?)?(?<!\dx)'
    regex += r'\d{1,4}(\.\d{0,2})?\$?'  # search for numbers and decimal places, and dollar sign after the number.
    regex += r'(?!\+ bronze|\+ gold|\+ silver|\+ certified|\+ platinum|ghz|\+ trade)'  # don't match 80+ ratings and trades
    regex += r'( \$| shipped| local| plus|(\s)?\+|(\s)?obo| or| sold| for|(\s)?USD)*'  # match these keywords

    reddit = praw.Reddit(client_id=client_id,
                         client_secret=client_secret,
                         user_agent=user_agent,
                         username=username,
                         password=password)

    with open('API.txt', 'r') as f:
        API_text = f.read()

    def identifyprice(price_string):
        price_string = price_string.lower().strip()
        try:  # If the string only has numbers, it's an irrelevant random number
            price_string = float(price_string)
            return False
        except ValueError:  # There are words or a dollar sign, indicating it's not a random model number
            if 'bought' in price_string or 'sold' in price_string:
                return False
            else:
                return True

    def highlight(match):
        if identifyprice(match.group()):
            return f'<span style="background-color: yellow;">{match.group()}</span>'
        return match.group()

    def GPT_API(submission):
        for i in range(3):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an API server."},
                        {"role": "user", "content": API_text},
                        {"role": "assistant", "content": "ready"},
                        {"role": "user", "content": submission.title + "\n" + submission.selftext}
                    ],
                    temperature=0.2
                )
                try:
                    return json.loads(response['choices'][0]['message']['content'])
                except json.decoder.JSONDecodeError:
                    print("Bad JSON, asking again")
                    print(f"Retry {i} / 3")
            except Exception as e:
                print(f"OpenAI or other errors: {e}")
                print(f"Retry {i} / 3")
        return {'US_postal_code': 0, 'item': [
            {'name': 'GPT error', 'price': -1, 'shipping_cost': -1, 'is_local_only': False, 'condition': 3,
             'buyer_caution': ''}], }

    while Signal.should_run:
        try:  # Praw might throw errors, we want to ignore them
            subreddit = reddit.subreddit('hardwareswap')
            for submission in subreddit.stream.submissions(skip_existing=True,
                                                           pause_after=0):  # REFRESH AND LOOK FOR NEW POSTS AND PROCESS THEM
                if not Signal.should_run:
                    print("Thread exiting")
                    return
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

                if 'paypal' in want.lower() or 'cash' in want.lower():  # aka if it's a selling post
                    response = GPT_API(submission)
                    response['selftext'] = re.sub(regex, highlight, submission.selftext, flags=re.IGNORECASE)
                    response['title'] = submission.title
                    response['author'] = submission.author.name
                    response['trades'] = submission.author_flair_text
                    if not response['trades']:
                        response['trades'] = "Trades: 0"
                    response['url'] = submission.url.strip()
                    response['id'] = submission.id
                    response['created'] = submission.created_utc  # Unix timestamp
                    print(response)
                    if socketio:
                        socketio.emit('new_data', response)


        except Exception as e:
            print(f'Reddit Error: {e}\n Continuing')
            time.sleep(2)
    print("Thread exiting")


if __name__ == '__main__':
    Signal.should_run = True
    main()
