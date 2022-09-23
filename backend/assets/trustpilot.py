from operator import countOf
from traceback import print_tb
from bs4 import BeautifulSoup
import requests
import pandas as pd
import datetime as dt
import csv
import time

# Initialize lists
review_titles = []
review_dates_original = []
review_dates = []
review_ratings = []
review_texts = []
reviewers = []
page_number = []

# Set Trustpilot page numbers to scrape here
from_page = 463
to_page = 976

datafile = 'trustpilot_reviews.csv'

with open(datafile, 'a', newline='', encoding='utf8') as csvfile:

    # Tab delimited to allow for special characters
    datawriter = csv.writer(csvfile, delimiter='\t')
    for i in range(from_page, to_page + 1):
        # print("Scraping page " + str(i) + " of " + str(to_page))
        response = requests.get(f"https://www.trustpilot.com/review/www.fwd.com.sg?page={i}")
        web_page = response.text
        soup = BeautifulSoup(web_page, "html.parser")

        count_on_page = 0
        for review in soup.find_all(class_ = "paper_paper__1PY90 paper_square__lJX8a card_card__lQWDv card_noPadding__D8PcU styles_cardWrapper__LcCPA styles_show__HUXRb styles_reviewCard__9HxJJ"):
            # Review titles
            review_title = review.find(class_ = "typography_typography__QgicV typography_h4__E971J typography_color-black__5LYEn typography_weight-regular__TWEnf typography_fontstyle-normal__kHyN3 styles_reviewTitle__04VGJ")
            review_titles.append(review_title.getText())

            # Review dates
            review_date_original = review.select_one(selector="time")
            review_dates_original.append(review_date_original.getText())

            # Convert review date texts into Python datetime objects
            review_date = review.select_one(selector="time").getText().replace("Updated ", "")
            if "hours ago" in review_date.lower() or "hour ago" in review_date.lower():
                review_date = dt.datetime.now().date()
            elif "a day ago" in review_date.lower():
                review_date = dt.datetime.now().date() - dt.timedelta(days=1)
            elif "days ago" in review_date.lower():
                review_date = dt.datetime.now().date() - dt.timedelta(days=int(review_date[0]))
            else:
                review_date = dt.datetime.strptime(review_date, "%b %d, %Y").date()
            review_dates.append(review_date)

            # Review ratings
            review_rating = review.find(class_ = "star-rating_starRating__4rrcf star-rating_medium__iN6Ty").findChild()
            review_ratings.append(review_rating["alt"])

            # When there is no review text, append "" instead of skipping so that data remains in sequence with other review data e.g. review_title
            review_text = review.find(class_ = "typography_typography__QgicV typography_body__9UBeQ typography_color-black__5LYEn typography_weight-regular__TWEnf typography_fontstyle-normal__kHyN3")
            txt = None
            if review_text == None:
                review_texts.append("")
                txt = ""
            else:
                review_texts.append(review_text.getText())
                txt = review_text.getText()

            reviewer = review.find(class_ = "link_internal__7XN06 link_wrapper__5ZJEx styles_consumerDetails__ZFieb").get("href")
            reviewers.append(reviewer.split('/')[-1])

            # Trustpilot page number
            page_number.append(i)

            datawriter.writerow([review_title.getText(), review_date_original.getText(), review_date, review_rating["alt"], txt, reviewer.split('/')[-1], i])

            count_on_page += 1

        print(f"Fetched {count_on_page} on page {i}")

        if (count_on_page == 0):
            print("Sleeping for 20 seconds after page {i}")
            time.sleep(20)
        elif (i % 10 == 0):
            print(f"Sleeping for 5 seconds after page {i}")
            time.sleep(5)

# Create final dataframe from lists
# df_reviews = pd.DataFrame(list(zip(review_titles, review_dates_original, review_dates, review_ratings, review_texts, reviewers, page_number)),
#                 columns =['review_title', 'review_date_original', 'review_date', 'review_rating', 'review_text', 'reviewer', 'page_number'])

# df_reviews.to_csv("trustpilot_reviews.csv", index=False)