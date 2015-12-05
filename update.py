#! /usr/bin/env python

import re
import sys
import csv
import json
import codecs
import os.path
import requests
import ConfigParser

storage = {}

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

# age file
def age_file(new_file, old_file):
	nf = os.path.expanduser(new_file)
	of = os.path.expanduser(old_file)
	try:
		os.rename(nf,of)
	except OSError:
		pass

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

# store station sample
def store_station(station, station_number, contract_name, timestamp):
	if not storage.has_key(contract_name):
		storage[contract_name] = {}
	stations = storage[contract_name]
	stations[station_number] = station
	station["update"] = timestamp

# store contract stations
def store_stations(stations, contract_name):
	for number in stations:
		station = stations[number]
		timestamp = station.pop("update",None)
		store_station(station, number, contract_name, timestamp)

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
payload = { "apiKey": api_key }
url = "https://api.jcdecaux.com/vls/v1/stations"
headers = { "Accept": "application/json" }
r = requests.get(url, params=payload, headers=headers)

# convert to json
t0_json = json.loads(r.text)

# check api error
if type(t0_json) is dict and t0_json.has_key("error"):
	print "API: %s" % t0_json["error"]
	sys.exit(1)

# save t0
try:
	save_unicode_file(r.text,"~/.jcd.cache.t0")
except IOError:
	print "cannot save t0 file"
	sys.exit(1)

# load t1
t1_text = None
try:
	t1_text = load_unicode_file("~/.jcd.cache.t1")
except IOError:
	pass

# load t2
t2_text = None
try:
	t2_text = load_unicode_file("~/.jcd.cache.t2")
except IOError:
	pass

# build tree
t0_tree = station_list_to_tree(t0_json)
if t1_text is not None:
	t1_tree = station_list_to_tree(json.loads(t1_text))
if t2_text is not None:
	t2_tree = station_list_to_tree(json.loads(t2_text))

# t0 = current, t1 = previous, t2 = oldest

# browse t0 and deduplicates as needed
for t0_contract_name in t0_tree:
	# extract t0 contract stations
	t0_stations = t0_tree[t0_contract_name]
	# check for t1
	if t1_text is None:
		# if absent save all t0 contract
		store_stations(t0_stations, t0_contract_name)
		continue
	# check for t1 contract
	if not t1_tree.has_key(t0_contract_name):
		# if absent save all t0 contract
		store_stations(t0_stations, t0_contract_name)
		continue
	# extract t1 contract stations
	t1_stations = t1_tree[t0_contract_name]
	# compare station by station
	for t0_station_number in t0_stations:
		# extract t0 station
		t0_station = t0_stations[t0_station_number]
		# remove t0 timestamp
		t0_update = t0_station.pop("update",None)
		# check for t1 station
		if not t1_stations.has_key(t0_station_number):
			# if absent save t0 station
			store_station(t0_station, t0_station_number, t0_contract_name, t0_update)
			continue
		# extract t1 station
		t1_station = t1_stations[t0_station_number]
		# remove t1 timestamp
		t1_update = t1_station.pop("update",None)
		# check t0 station for change since t1 station
		if t0_station == t1_station:
			continue
		# store t0 when as it changed
		store_station(t0_station, t0_station_number, t0_contract_name, t0_update)
		################################################
		# now we will check it t1=t2, then store t1 too
		# we'll get cleaner graphs with minimal samples
		# example : '.     .'  '.
		################################################
		# check for t2
		if t2_text is None:
			continue
		# check for t2 contract
		if not t2_tree.has_key(t0_contract_name):
			continue
		# extract t2 contract stations
		t2_stations = t2_tree[t0_contract_name]
		# check t2 for station
		if not t2_stations.has_key(t0_station_number):
			continue
		# extract t2 station
		t2_station = t2_stations[t0_station_number]
		# remove t2 timestamp
		t2_update = t2_station.pop("update",None)
		# check t1 station for change since t2 station
		if t1_station == t2_station:
			# no change, store latest unchanged (t1)
			store_station(t1_station, t0_station_number, t0_contract_name, t1_update)
			continue

# output stored data
print json.dumps(storage)

# age cache files
age_file("~/.jcd.cache.t1","~/.jcd.cache.t2")
age_file("~/.jcd.cache.t0","~/.jcd.cache.t1")
