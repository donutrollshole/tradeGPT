import praw
import os
import openai
import time
from GeoSpatial import GeoSpatial
import json
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit


def main(socketio: SocketIO = None):
    load_dotenv()

    client_id = os.getenv("client_id")
    client_secret = os.getenv("client_secret")
    user_agent = os.getenv("user_agent")
    username = os.getenv("username")
    password = os.getenv('password')
    paypal_email = os.getenv("paypal_email")
    zipcode = os.getenv("zipcode")

    openai.organization = os.getenv("org_id")
    openai.api_key = os.getenv("OPENAI_API_KEY")

    my_local_zip = int(os.getenv("my_local_zip", 10001))
    max_allowed_local_distance = float(os.getenv("max_allowed_local_distance", -1)) * 1.609344

    my_location = GeoSpatial(my_local_zip)

    reddit = praw.Reddit(client_id=client_id,
                         client_secret=client_secret,
                         user_agent=user_agent,
                         username=username,
                         password=password)

    with open('API.txt', 'r') as f:
        API_text = f.read()

    def GPT_API(submission):
        for i in range(5):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an API server."},
                        {"role": "user", "content": API_text},
                        {"role": "assistant", "content": "ready"},
                        {"role": "user", "content": submission.title + "\n" + submission.selftext}
                    ]
                )
                try:
                    return json.loads(response['choices'][0]['message']['content'])
                except json.decoder.JSONDecodeError:
                    print("Bad JSON, asking again")
                    print(f"Retry {i} / 5")
            except Exception as e:
                print(f"OpenAI or other errors: {e}")
                print(f"Retry {i} / 5")

    def send_pm(recipient, item_name, item_price, paypal_email, zipcode):  # recipient's username WITHOUT "u/"
        reddit.redditor(f"{recipient}").message(subject=f"{item_name}", 
                                                message=f"""Hey! I'd like to purchase the {item_name} for ${item_price}.
                                                        If you're good with shipping to {zipcode}, please send a PayPal invoice to {paypal_email}. Thanks!""")


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
                    response = GPT_API(submission)
                    print(response)
                    if socketio:
                        socketio.emit('new_data', response)
                    if response['US_postal_code']:
                        print(my_location - GeoSpatial(response['US_postal_code']) <= max_allowed_local_distance)


        except Exception as e:
            print(f'Reddit Error: {e}\n Continuing')
            time.sleep(2)


if __name__ == '__main__':
    main()
