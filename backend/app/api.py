# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from collections import defaultdict
from crypt import methods
import os
import pandas as pd

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
import spacy
import srsly
import uvicorn

from app.models import (
    ENT_PROP_MAP,
    RecordsRequest,
    RecordsResponse,
    RecordsEntitiesByTypeResponse,
)
from app.spacy_extractor import SpacyExtractor


load_dotenv(find_dotenv())
prefix = os.getenv("CLUSTER_ROUTE_PREFIX", "").rstrip("/")


app = FastAPI(
    title="backend",
    version="1.0",
    description="Python API that for Custom Cognitive Skills in Azure Search",
    openapi_prefix=prefix,
)

example_request = srsly.read_json("app/data/example_request.json")

nlp = spacy.load("This must be one of spaCy's default languages. See https://spacy.io/usage for a supported list.")
extractor = SpacyExtractor(nlp)


@app.get("/", include_in_schema=False)
def docs_redirect():
    return RedirectResponse(f"{prefix}/docs")

trustpilot_reviews = pd.read_csv('trustpilot_reviews.csv')

review_aspects = pd.read_json('review_aspects.json')

@app.get('/reviews/num', methods=['GET'])
async def get_num_reviews():
    return len(trustpilot_reviews)

@app.get('/reviews/sentiment-distribution', methods=['GET'])
async def get_sentiment_distribution():
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

@app.get('/reviews/aspect-distribution', methods=['GET'])
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

@app.get('tweets/most-liked', methods=['GET'])
async def get_most_liked_tweets():
    # sort by likes
    sorted_tweets = trustpilot_reviews.sort_values(by=['likes'], ascending=False)
    top = sorted_tweets.head(10).to_dict('records')

    return top

@app.get('tweets/top-user-profile', methods=['GET'])
async def get_top_user_profile():
    # based on number of likes
    # get the user from ...

@app.post("/entities", response_model=RecordsResponse, tags=["NER"])
async def extract_entities(body: RecordsRequest = Body(..., example=example_request)):
    """Extract Named Entities from a batch of Records."""

    res = []
    documents = []

    for val in body.values:
        documents.append({"id": val.recordId, "text": val.data.text})

    entities_res = extractor.extract_entities(documents)

    res = [
        {"recordId": er["id"], "data": {"entities": er["entities"]}}
        for er in entities_res
    ]

    return {"values": res}


@app.post(
    "/entities_by_type", response_model=RecordsEntitiesByTypeResponse, tags=["NER"]
)
async def extract_entities_by_type(body: RecordsRequest = Body(..., example=example_request)):
    """Extract Named Entities from a batch of Records separated by entity label.
        This route can be used directly as a Cognitive Skill in Azure Search
        For Documentation on integration with Azure Search, see here:
        https://docs.microsoft.com/en-us/azure/search/cognitive-search-custom-skill-interface"""

    res = []
    documents = []

    for val in body.values:
        documents.append({"id": val.recordId, "text": val.data.text})

    entities_res = extractor.extract_entities(documents)
    res = []

    for er in entities_res:
        groupby = defaultdict(list)
        for ent in er["entities"]:
            ent_prop = ENT_PROP_MAP[ent["label"]]
            groupby[ent_prop].append(ent["name"])
        record = {"recordId": er["id"], "data": groupby}
        res.append(record)

    return {"values": res}
