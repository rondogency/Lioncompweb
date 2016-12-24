# Important the necessary methods from tweepy library
from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy import Stream 
#from elasticsearch import Elasticsearch
import requests
import json
import boto3
import nltk


access_token = ""
access_token_secret = ""
consumer_key = ""
consumer_secret = ""


# This is a basic listener that just prints received tweets to stdout
class StdOutListener(StreamListener):

	def on_error(self, status):
		#print status
		pass


	def on_status(self, status):
		try:
			if status.coordinates:
				#print status
				tweet = {}
				tweet['user'] = status.user.screen_name
				tweet['text'] = status.text
				tweet['location'] = status.coordinates['coordinates']
				tweet['time'] = str(status.created_at)

				tokens = nltk.word_tokenize(tweet['text'])

				if len(keywordSet & set(tokens)) > 0:
					response = queue.send_message(MessageBody = tweet['text'], MessageAttributes = {
						'Time': {
							'StringValue': tweet['time'],
							'DataType': 'String'
						},
						'User': {
							'StringValue': tweet['user'],
							'DataType': 'String'
						},
						'Longitude': {
							'StringValue': str(tweet['location'][0]),
							'DataType': 'String'
						},
						'Latitude': {
							'StringValue': str(tweet['location'][1]),
							'DataType': 'String'
						}
					})

				print tweet

		except Exception as e:
			print 'Error! {0}: {1}'.format(type(e), str(e))

if __name__ == '__main__':
	# Create key words
	keywords = ['theft', 'assault', 'arrest', 'arson', 'burglary', 'robbery', 'shooting']
	keywordSet = set(keywords)

	# This handles Twitter authetification and the connection to Twitter Streaming API
	l = StdOutListener()
	auth = OAuthHandler(consumer_key, consumer_secret)
	auth.set_access_token(access_token, access_token_secret)
	stream = Stream(auth, l)

	stream.filter(locations = [-74,40,-73,41])