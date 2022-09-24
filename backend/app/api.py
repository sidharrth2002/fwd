# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import ast
import base64
from collections import defaultdict
from crypt import methods
import os
from tkinter import font
import pandas as pd

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
import spacy
import srsly
import uvicorn
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import plotly.express as px
from textblob import TextBlob
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt
from nltk.corpus import stopwords
import json
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(find_dotenv())
prefix = os.getenv("CLUSTER_ROUTE_PREFIX", "").rstrip("/")


app = FastAPI(
    title="backend",
    version="1.0",
    description="Python API that for Custom Cognitive Skills in Azure Search",
    openapi_prefix=prefix,
)

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

example_request = srsly.read_json("app/data/example_request.json")

@app.get("/", include_in_schema=False)
def docs_redirect():
    return RedirectResponse(f"{prefix}/docs")

def to_dict(x):
    try:
        y = ast.literal_eval(x)
        if type(y) == dict:
            return y
    except:
        return None

# load data
trustpilot_reviews = pd.read_csv('app/assets/trustpilot_reviews.csv')
review_aspects = json.load(open('app/assets/review_aspects.json', 'r'))
users = pd.read_csv('app/assets/insurance_tweets_100.csv', converters = {'age': to_dict})
tweets = pd.read_csv('app/assets/insurance_tweets_100.csv', converters = {'age': to_dict})
# read json column age in users
# convert column to json
# users['age'] = users['age'].apply(lambda x: "\"" + json.dumps(x).replace('\'', '\"') + "\"")
# print(json.dumps(users['age'].iloc[0]))

users['age_num'] = users['age'].apply(lambda x: x['faces'][0]['age'] if ('faces' in x) and (len(x['faces']) > 0) and ('age' in x['faces'][0]) else 18)
users['age_group'] = users['age'].apply(lambda x: x['faces'][0]['class'] if ('faces' in x) and (len(x['faces']) > 0) and ('age' in x['faces'][0]) else 18)

tweets['age_num'] = tweets['age'].apply(lambda x: x['faces'][0]['age'] if ('faces' in x) and (len(x['faces']) > 0) and ('age' in x['faces'][0]) else 18)
tweets['age_group'] = tweets['age'].apply(lambda x: x['faces'][0]['class'] if ('faces' in x) and (len(x['faces']) > 0) and ('age' in x['faces'][0]) else 18)

@app.get('/reviews/num')
async def get_num_reviews():
    return len(trustpilot_reviews)

def getAnalysis(score):
    if score < 0:
        return "Negative"
    elif score == 0:
        return "Neutral"
    else:
        return "Positive"

@app.get('/reviews/sentiment-distribution')
async def get_sentiment_distribution():
    trustpilot_reviews['sentiment'] = trustpilot_reviews['review'].apply(lambda x: getAnalysis(TextBlob(str(x)).sentiment.polarity))
    dist = trustpilot_reviews['sentiment'].value_counts()
    return dist.to_dict()

# @app.get('/reviews/wordcloud', methods=['GET'])
# async def get_wordcloud():
#     wr = trustpilot_reviews['review']
#     # find most common aspects
#     from collections import Counter

#     aspects = set()
#     for review in review_aspects:
#         aspects.update([aspect for aspect in review['aspect']])

@app.get('/reviews/aspect-distribution')
async def get_aspect_distribution():
    # find most common aspects
    from collections import Counter

    aspects = set()
    for review in review_aspects:
        aspects.update([aspect for aspect in review['aspect']])

    aspect_sentiments = {}

    for review in review_aspects:
        aspects_list = review['aspect']
        for i in range(len(review['aspect'])):
            aspect = aspects_list[i].lower()
            if aspect not in aspect_sentiments:
                aspect_sentiments[aspect] = [review['sentiment'][i]]
            else:
                aspect_sentiments[aspect].append(review['sentiment'][i])

    sentiment_ratios = {}

    for aspect in aspect_sentiments:
        pos = aspect_sentiments[aspect].count('Positive')
        neg = aspect_sentiments[aspect].count('Negative')
        neu = aspect_sentiments[aspect].count('Neutral')
        sentiment_ratios[aspect] = {
            'Positive': pos,
            'Negative': neg,
            'Neutral': neu,
        }

        restructured_dist = {
            'Positive': {},
            'Negative': {},
            'Neutral': {},
        }
    for key in sentiment_ratios:
        for sentiment in sentiment_ratios[key]:
            restructured_dist[sentiment][key] = sentiment_ratios[key][sentiment]

    return restructured_dist

@app.get('/tweets/most-liked')
async def get_most_liked_tweets():
    # sort by likes
    # print(tweets['favorite_count'])
    cleaned_tweets = tweets.dropna(subset=['favorite_count'])
    sorted_tweets = cleaned_tweets.sort_values(by=['favorite_count'], ascending=False)
    # only get tweet text
    final_tweets = []
    for tweet in sorted_tweets.iterrows():
        print(tweet[1].keys())
        final_tweets.append({
            'text': tweet[1]['full_text'],
            'name': tweet[1]['name'],
            'age': tweet[1]['age_num'],
            'sentiment': getAnalysis(TextBlob(str(tweet[1]['full_text'])).sentiment.polarity)
        })

    return final_tweets

# @app.get('/tweets/most-retweeted')
# async def get_most_retweeted_tweets():
#     tw = trustpilot_reviews.sort_values(by=['retweets'], ascending=False)
#     return tw.head(10).to_dict('records')

@app.get('/perception-by-age')
async def get_perception_by_age():
    sent_by_age = users.groupby('age_group')['sentiment'].mean()
    return sent_by_age.to_dict()

@app.get('/tweet_wordcloud/{age_group}')
async def get_tweet_wordcloud(age_group):
    options = ['Adult', '18', 'Young Adult', 'Senior Adult', 'Kid', 'Toddler', 'Mature Adult', 'Token']
    if age_group not in options:
        raise Exception('Invalid age group. Please choose from: ' + ', '.join(options))
    else:
        if age_group != '18':
            age_group = 'Age - ' + age_group

    stops = stopwords.words('english')

    def black_color_func(word, font_size, position,orientation,random_state=None, **kwargs):
        return("hsl(0,100%, 1%)")

    # for each age group, get the most common keywords

    # plot word cloud
    cloud = WordCloud(font_path = '/Library/Fonts/Arial Unicode.ttf', background_color="white", width=2000, height=1000, max_words=500, stopwords=stops + ['insurance']).generate(" ".join(users[users['age_group'] == age_group]['clean_text']))
    cloud.recolor(color_func=black_color_func)

    # save word cloud
    cloud.to_file('cloud.png')

    # return image as base64
    return {
        'cloud': base64.b64encode(open('cloud.png', 'rb').read()).decode('utf-8')
    }

@app.get('/pain-points')
async def get_pain_points():
    sentiment_ratios = {}

    aspect_sentiments = {}

    for review in review_aspects:
        aspects_list = review['aspect']
        for i in range(len(review['aspect'])):
            aspect = aspects_list[i].lower()
            if aspect not in aspect_sentiments:
                aspect_sentiments[aspect] = [review['sentiment'][i]]
            else:
                aspect_sentiments[aspect].append(review['sentiment'][i])

    for aspect in aspect_sentiments:
        pos = aspect_sentiments[aspect].count('Positive')
        neg = aspect_sentiments[aspect].count('Negative')
        neu = aspect_sentiments[aspect].count('Neutral')
        sentiment_ratios[aspect] = {
            'Positive': pos,
            'Negative': neg,
            'Neutral': neu,
        }

    # only keep first 30 aspects
    sentiment_ratios = dict(sorted(sentiment_ratios.items(), key=lambda item: item[1]['Negative'], reverse=True)[:30])

    restructured_dist = {
        'Positive': {},
        'Negative': {},
        'Neutral': {},
    }

    for key in sentiment_ratios:
        for sentiment in sentiment_ratios[key]:
            restructured_dist[sentiment][key] = sentiment_ratios[key][sentiment]

    # only show first 20 bars
    bar_plot = px.bar(restructured_dist, barmode='stack')

    # save bar plot with high definition
    bar_plot.write_image('bar_plot.png', width=2000, height=1000)

    return {
        'bar_plot': base64.b64encode(open('bar_plot.png', 'rb').read()).decode('utf-8')
    }

# @app.get('/most-active-age-groups')
# async def get_most_active_age_groups():
#     # which age groups are most active on twitter?
