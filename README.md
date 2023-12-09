# wordle-solving

This repository integrates [Deephaven](http://deephaven.io/) with [Twitter](https://twitter.com/) to solve [WORDLE](https://wordle.at/) in one guess, without knowing any possible letters.

 Running `./wordle-solver.sh` will create all the needed tables in Deephaven.

 Open Deephaven on [http://localhost:10000/ide](http://localhost:10000/ide) to edit and run the scripts.
 
Note: Free access to the Twitter API is no longer available. However, the code and concepts in this blog are still valid for users with a paid developer account.

## Overview

The team at Deephaven loves to play Wordle. We think of the game and the phenomenom it's created as fascinating in two ways. First, it is a simple game that gained viral popularity. We love that people of all ages seem to be playing it. But, equally important is that EVERYONE PLAYS THE SAME GAME EVERY DAY. You play Worlde by yourself, but it feels social. People talk about it in the real world and of course share results on social media.

There are a number of computer science strategies that optimize how to play the game by yourself: some use entropy and information theory math. That's good stuff, but I am much more interested in the social part of the game. That's a big part of the fun. Recently, [Ben Hamner](https://www.kaggle.com/benhamner/wordle-1-6) posted an article that uses the tweets of people's past Worlde solutions to solve the current Wordle. We wanted to try a similar strategy, but instead of looking at historical data, pull in the anonymized solutions as they come in on Twitter to determine the likeliest answer for the Worlde of the day. 

Last month, we built a simple toy solver starting with a CSV upload of high-frequency words and creating a table with custom columns that we could filter to narrow down our guesses. Now, we are going to show you how solving Worlde can essentially be crowd-sourced in real-time. The real-time part is exciting. We'll demonstrate how listening to the real-time Twitter feed for today's Worlde posts for just a couple of minutes and simply understanding the information provided by the colored squares in those Twitter posts can provide the today's winning solution. No one will tell you a single letter and you can guess the answer on the first try.

### Components

* `Dockerfile` - The Dockerfile for the application. This extends the default Deephaven images to add dependencies. See our guide, [How to install Python packages](https://deephaven.io/core/docs/how-to-guides/install-python-packages/#add-packages-to-a-custom-docker-image), for more information.
* `docker-compose.yml` - The Docker Compose file for the application. This is mostly the same as the [Deephaven docker-compose file](https://raw.githubusercontent.com/deephaven/deephaven-core/main/containers/python-examples/docker-compose.yml) with modifications to run [Twitter V2 API](https://twitter.com/) and custom dependencies.
* `wordle-solver.sh` - A simple helper script to launch the application.
* `requirements.txt` - Python dependencies for the application.
* `data/feedback.csv` - The cross join of the WORDLE answers with WORDLE guesses in `YNM` format.  
* `data/notebooks/pull_tweets.py` - A query to pull tweets, clean and get the WORDLE
* `data/layout/layout.json` - A Deephaven layout to show needed tables and query.
* `app.d/start.app` - A Deephaven file to load execute app mode.
* `app.d/tables.py` - A Deephaven sample query to load CSV and WORDLE words into a table.

## Details

If you look at the main JavaScript program behind WORDLE, you can see the word bank. This is available to anyone who right clicks and saves the Worlde and then views the html via any text editor (not browser).

The WORDLE source is backed by a list of 2,315 possible answers that are all common English words, as well as a list of 10,657 other words that are valid guesses but are less-common English words that will never be answers. In the WORDLE JavaScript, these are `Ta` and `La`.


Next, we want to know what the feedback will be for each guess given each answer.

For example, if the answer is "light" and we guess "alter", then the feedback should return as NMMNN, while a guess of fight should return NYYYY. The function to find these values is our `evaluate_guess` function below. This will show all the possible feedback that will happen for each word guessed. As you can imagine, this is a long list since each word can have many permutations for various answers.

When you run this script, you will see these loaded into Deephaven as `answers` and `all_words`.

To speed up our computation, we want to be smart about the source for our words so we use `answers` and `all_words` but combine them into a words array for feedback.  This operation takes about 8 minutes to run, so we load the results into the `feedback` table. If you want to execute this for any reason, comment out the query:

```python
guesses = answers.view('answer = A').join(wordle_words.view("guess = A")) \
    .where('answer != guess') \
    .selectDistinct('answer', 'feedback = (String)evaluate_guess(answer, guess)')
```

Why are we using this list and not the larger list from last time? We are pulling in real-time anonymous tweet data and using the word list from our last post showed there are a lot obscure words that have weird patterns. Since the anonymous tweet data relies on patterns, we quickly get the correct word with the limited list.


### Twitter

Each day there is a new WORDLE. Generally, when searching Twitter for WORDLE posts, we want to make sure the data is robust. With more data comes the chances of bad data; also, the frequency of data changes throughout the day since real people are posting their WORDLE adventure on their own schedule. Some of my friends like to solve it right when it comes out, while others wait until later in the day.

[Twitter](https://developer.twitter.com/en/docs/twitter-api) provides an API to make it easy to pull public tweets. In order to use this code as-is, you need to also have a Twitter Developer account and copy your Bearer Token.

The code below will pull in the tweets. Make sure you change your variables to fine-tune your settings. The end result will be a table of tweets that concern a particular numbered WORDLE. For example, as of this writing, the WORDLE is 228.

This is designed so that the tweets are pulled starting at midnight and then are continued to pull in real-time every 10 seconds. Edit the parameters so that you can fine tune how much old/new tweets you want.


## Clean the tweets

With any data project, we need to clean the data. Twitter uses beautiful emojis for the boxes. As those do not render very well in our dataset, we replace them with Yes, No, and Maybe in a similar fashion as Ben Hamner. We also do not get any new information from tweets that are all Y or all N; these add no value but slow the operation.


We also want to separate the guesses in each tweet so that each set of five will be a new value to count. Running these lines will create a new table that contains each user's guess in `YMN` format. Notice some tweet IDs are included five times because that user took five guesses before they got the right answer, while some are just included once because they only needed one guess to solve the puzzle.

Another interesting problem that came up is that other languages, aside from English, use the same WORDLE numbering system, so we remove those tweets and any tweet that links to the external WORDLE sites from these other platforms.


## Process the Tweets

Now we have a table of all the feedback that people received for the day. We want to look up what words each feedback can correspond to. Each tweet gives us a set of words that can be the possible answer. A single tweet doesn't reduce the word list by much, but as more and more come in, we can start to see the patterns that emerge.

Our code now joins the streaming tweets-feedback table with all the possible answers so that each tweet ID will now appear up to twelve-thousand times.

Since some data inside a tweet is not unique, we can reduce this list by just showing those with distinct values inside each tweet.

For example, if we see a tweet that has feedback `NMMNN`, then the word `alter` will increase in count by 1 as that is the feedback when the answer is `light`. `NMMNN` is not a unique value so all matches to this value will increase in count such as `silky` and `mitoc`. As each user's feedback comes in, the count will increase and the right word will come to the top of the table.

Finally, we want to count how many times each word appears in the results column. The more tweets one pulls, the better the data.

This really shows the power of large, dynamic data sets. Even though this data is anonymous and we do not know the letters or words of each tweet, it's impressive to see the right answer emerge at the top of our results table.

What other anonymous dataset can this be applied to? Let us know by joining our [Slack community](https://deephaven.io/slack).

## Correct word

You can always check the word by just pulling it from the array where you want to change the numbered value to the current Worlde. Or, impress your friends and put in the number for tomorrow!

print(answers.getColumn("word").getDirect()[234])

## Dependencies

* The [Deephaven-core dependencies](https://github.com/deephaven/deephaven-core#required-dependencies) are required to build and run this project.

## Launch

To launch the latest release, you can clone the repository via:

```shell
git clone https://github.com/deephaven-examples/wordle-solving.git
cd wordle-solving
```

A start script will install the needed python modules. It will also start the Deephaven IDE.

To run it, execute:

```shell
./wordle-solver.sh
```

Running this script will start several Docker containers that work together to launch Deephaven with the needed dependancies. To view the data navigate to [http://localhost:10000/ide](http://localhost:10000/ide).  To view the data you need to edit the `pull_tweets.py` file with your information.

## Close

To stop running in your terminal execute `docker-compose down -v`

## Related documentation

- [WORDLE, Python, and crowd-sourcing in real-time](https://deephaven.io/blog/2022/02/11/wordle-2/)
- [Solve WORDLE on the first guess with real-time data](https://www.youtube.com/watch?v=hEib74gdyWc&t=14s)

## Note

The code in this repository is built for Deephaven Community Core v0.12.0. No guarantee of forwards or backwards compatibility is given.
