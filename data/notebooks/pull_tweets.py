# paste your bearer token from Twitter
bearer_token = '<YOUR TOKEN>'

#Change to the wordle for today
search_term = ['Wordle 237']

# Max results per time bin, 10-100
max_results = 10

#seconds between requests
time_to_sleep = 10

#how long to keep listening in minutes
time_alive = 10

#variable to store tweet of last request, for live tweets.
max_id =int(1487032289452347397)

#twitter imports
from requests_oauthlib import OAuth1Session
import requests
from datetime import datetime

#python imports
import time
import re
import math
import json

#deephaven imports
from deephaven.DateTimeUtils import convertDateTime, plus, convertPeriod, currentTime, hourOfDayNy
from deephaven import DynamicTableWriter
import deephaven.Types as dht
import threading

#twitter function to create header
def create_headers(bearer_token):
        headers = {
            "Authorization": "Bearer {}".format(bearer_token),
            "User-Agent": "v2FullArchiveSearchPython"}
        return headers

# twitter url for recent tweets
search_url = "https://api.twitter.com/2/tweets/search/recent"

#connect to twitter with above header
def connect_to_endpoint(url, headers, params):
    response = requests.request("GET", search_url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(response.status_code, response.text)
    return response.json()

# twitter paramters for tweets from eariler in day
def get_query_params_hist(search_term, start_time, end_time):
    return {'query': search_term,
                    'start_time': start_time,
                    'end_time': end_time,
                    'max_results': max_results,
                    'tweet.fields': 'id,text,author_id,in_reply_to_user_id,geo,conversation_id,created_at,lang,public_metrics,referenced_tweets,reply_settings,source',
                    'user.fields': 'id,name,username,created_at,description,public_metrics,verified',
                    'next_token': {}}

#twitter paramters for live tweets
def get_query_params_live(search_term, max_id):
    return {'query': search_term,
                    'since_id': max_id,
                    'max_results': max_results,
                    'tweet.fields': 'id,text,author_id,in_reply_to_user_id,geo,conversation_id,created_at,lang,public_metrics,referenced_tweets,reply_settings,source',
                    'user.fields': 'id,name,username,created_at,description,public_metrics,verified',
                    'next_token': {}}

# get tweets, if not enough data return null
def get_tweets(query_params):
    headers = create_headers(bearer_token)
    json_response = connect_to_endpoint(search_url, headers, query_params)
    if(len(json_response['data']))>2:
        return(json_response['data'])
    else: return null

# write the twitter data into a deephaven table
def write_data(all_text, tableWriter):
    global max_id
    i = 0
    for t in all_text:
        id = int(t['id'])
        #if there is a newer Id save that as the new max_id, so tweets are only pulled once each
        if max_id < float(t['id']):
            globals()['max_id'] = int(t['id'])
        dateTime = t['created_at'][:-1]+" NY"
        retweet_count = t['public_metrics']['retweet_count']
        reply_count = t['public_metrics']['reply_count']
        like_count = t['public_metrics']['like_count']
        quote_count= t['public_metrics']['quote_count']
        tableWriter.logRow(t['text'],convertDateTime(dateTime), int(retweet_count), int(reply_count), int(like_count), int(quote_count), t['id'])
        i = i + 1
    print("finished writing rows: ", i)
    return max_id

def thread_func(search_term, tableWriter):
    global max_id

    for i in range(1, int(hourOfDayNy(currentTime()))):
        start_time = str(plus(convertDateTime(str(currentTime())[:11]+'00:00:00.000 NY'),convertPeriod("T"+str(int(i-1))+"H")))[:-9]+'Z'
        end_time = str(plus(convertDateTime(str(currentTime())[:11]+'00:00:00.000 NY'),convertPeriod("T"+str(int(i))+"H")))[:-9]+'Z'
        query_params = get_query_params_hist(search_term, start_time, end_time)
        all_text = get_tweets(query_params)
        max_id = write_data(all_text, tableWriter)

    for i in range(time_alive*time_to_sleep):
        query_params = get_query_params_live(search_term, max_id)
        all_text = get_tweets(query_params)
        max_id = write_data(all_text, tableWriter)
        time.sleep(time_to_sleep)

def make_table(term):
    tableWriter = DynamicTableWriter(
        ["Text", "DateTime", "Retweet_count", "Reply_count", "Like_count", "Quote_count", "Id"],
        [dht.string, dht.datetime, dht.int_, dht.int_, dht.int_, dht.int_,dht.string])
    thread = threading.Thread(target=thread_func, args=[term, tableWriter])
    thread.start()
    return tableWriter.getTable()


# Given an answer and a guess, compute the feedback for that guess
def evaluate_guess(answer, guess):
    #print(answer + "," + guess)
    answer = [ch for ch in answer]
    guess = [ch for ch in guess]

    # Y/N/M string for feedback
    result = [ch for ch in ('_' * 5)]
    # Letters missed from exact match
    missed = []
    # First, scan for exact matches
    for i in range(5):
        if (answer[i] == guess[i]):
            result[i] = 'Y'
        else:
            missed.append(answer[i])
    for i in range(5):
        #print(i)
        #print(missed)
        if (result[i] != 'Y'):
            if guess[i] in missed:
                # Found a letter, out of place
                result[i] = 'M'
                missed.remove(guess[i])
            else:
                result[i] = 'N'

    return "".join(str(ch) for ch in result)

#guesses = answers.view('answer = A').join(wordle_words.view("guess = A")) \
#    .where('answer != guess') \
#    .selectDistinct('answer', 'feedback = (String)evaluate_guess(answer, guess)')

tweets_wordle = make_table(search_term)

def wordle_guesses(tweet):
    text = (tweet.replace("Y", "y").replace("\uf7e9", "Y")
                 .replace("M", "m").replace("\uf7e8", "M")
                 .replace("N", "n").replace("\u2b1c", "N").replace("\u2b1b", "N"))
    # pick only 5-letter guesses
    guesses = re.findall("([YMN]{5})", text)
    # skip tweets that never got it
    if ('YYYYY' in guesses):
        # remove success, it adds no value
        guesses.remove('YYYYY')
        # avoid duplicates, they add no value anyway
        return list(set(guesses))
    return []

# convert tweets to table of YNM
wisdom_of_the_masses = tweets_wordle\
    .where('!Text.contains(`Türkçe`)', '!Text.contains(`German`)', '!Text.contains(`t.co`)')\
    .update('Text = ((org.jpy.PyListWrapper)wordle_guesses(Text)).toArray()')\
    .view('TweetId=Id', 'Text', 'Guesses = Text.length')\
    .ungroup("Text")\
    .update("Text=(String)Text")

# match the tweet feedback to the the words they can be
matching_answers = wisdom_of_the_masses.join(feedback, "Text = feedback")

# insure the tweets are all real words, or discard
answer_fits_all_guesses = matching_answers.countBy("Count", "TweetId", "answer", "Guesses").where("Count == Guesses")

# count how many each word appears. Best word at the top.
popular_answers = answer_fits_all_guesses.countBy("Freq", "answer").sortDescending("Freq")

# Ultimate cheat
#print(answers.getColumn("word").getDirect()[237])
