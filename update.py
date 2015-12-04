#! /usr/bin/env python

import re
import sys
import json
import codecs
import os.path
import requests
import ConfigParser

# save unicode to file
def save_unicode_file(u_string, filename):
	fn = os.path.expanduser(filename)
	with codecs.open(fn,"wt",encoding="utf8") as f:
		f.write(u_string)

# load unicode to file
def load_unicode_file(filename):
	fn = os.path.expanduser(filename)
	with codecs.open(fn,"rt",encoding="utf8") as f:
		return f.read()

# turn station list into tree
def station_list_to_tree(stations):
	r = {}
	for l in stations:
		# create contract if needed
		cn = l["contract_name"]
		if not r.has_key(cn):
			r[cn] = {}
		c = r[cn]
		# create station
		n = l["number"]
		s = {}
		c[n] = s
		# fill station
		s["bikes"] = l["available_bikes"]
		s["empty"] = l["available_bike_stands"]
		if l["status"] == "OPEN":
			s["status"] = 1
		else:
			s["status"] = 0
		s["update"] = int(l["last_update"] / 1000)
	return r

# config
defaults = { "ApiKey": "" }
config = ConfigParser.SafeConfigParser(defaults)
config_file = os.path.expanduser("~/.jcd.ini")
config.read(config_file)
api_key = config.get("DEFAULT","ApiKey")
with open(config_file, "wt") as f:
	config.write(f)

# check
if not re.match("^[0-9a-z]{40}$", api_key):
	print "%s: ApiKey has invalid format" % config_file
	sys.exit(1)

# api
payload = { "contract": "Stockholm", "apiKey": api_key }
url = "https://api.jcdecaux.com/vls/v1/stations"
headers = { "Accept": "application/json" }
r = requests.get(url, params=payload, headers=headers)

# convert to json
current_json = json.loads(r.text)

# check api error
if type(current_json) is dict and current_json.has_key("error"):
	print "API: %s" % current_json["error"]
	sys.exit(1)

# save current
try:
	save_unicode_file(r.text,"~/.jcd.current")
except IOError:
	print "cannot save current file"
	sys.exit(1)

# load previous
previous_text='[]'
try:
	previous_text = load_unicode_file("~/.jcd.previous")
except IOError:
	print "previous file not available"
	pass

# convert to json
previous_json = json.loads(previous_text)

# build tree
current_tree = station_list_to_tree(current_json)
previous_tree = station_list_to_tree(previous_json)

# diff
for contract_key in current_tree:
	if not previous_tree.has_key(contract_key):
		print "contract %s is only in current" % contract_key
		continue
	current_contract = current_tree[contract_key]
	previous_contract = previous_tree[contract_key]
	for current_number in current_contract:
		if not previous_contract.has_key(current_number):
			print "station %s is only in current" % current_number
			continue
		current_station = current_contract[current_number]
		previous_station = previous_contract[current_number]
		if not current_station == previous_station:
			print "current '%s' and previous '%s' differ" % (current_station, previous_station)
