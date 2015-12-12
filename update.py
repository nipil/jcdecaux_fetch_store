#! /usr/bin/env python

import re
import sys
import json
import stat
import time
import errno
import codecs
import os.path
import logging
import requests
import ConfigParser

storage = {}

# create folder
def create_folder(path):
	try:
		full_path = os.path.expanduser(path)
		os.makedirs(full_path)
	except OSError as exception:
		if exception.errno != errno.EEXIST:
			print "could not create folder %s" % full_path
			raise exception

# create working folders
def make_sure_program_folders_exist():
	try:
		create_folder("~/.jcd/")
		create_folder("~/.jcd/cache/")
		create_folder("~/.jcd/updates/")
		create_folder("~/.jcd/archives/")
		create_folder("~/.jcd/databases/")
	except OSError:
		sys.exit(1)

# save unicode to file
def save_unicode_file(u_string, filename):
	try:
		fn = os.path.expanduser(filename)
		with codecs.open(fn,"wt",encoding="utf8") as f:
			f.write(u_string)
	except IOError:
		print "cannot save %s file" % filename
		sys.exit(1)

# load unicode to file
def load_unicode_file(filename):
	try:
		fn = os.path.expanduser(filename)
		with codecs.open(fn,"rt",encoding="utf8") as f:
			return f.read()
	except IOError:
		pass
	return None

# move file
def move_file(old_file, new_file):
	nf = os.path.expanduser(new_file)
	of = os.path.expanduser(old_file)
	try:
		os.rename(of,nf)
	except OSError as e:
		print "cannot rename %s to %s" % (of,nf)

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

# save config file
def save_config_file(filename, configuration):
	# save default and reformat existing
	with open(filename, "wt") as f:
		configuration.write(f)
	# restrict access to protect api key
	os.chmod(filename, stat.S_IRUSR | stat.S_IWUSR)

# config
def load_api_key():
	defaults = { "ApiKey": "" }
	config = ConfigParser.SafeConfigParser(defaults)
	# load
	config_file = os.path.expanduser("~/.jcd/config.ini")
	config.read(config_file)
	api_key = config.get("DEFAULT","ApiKey")
	# flush config to file to create or reformat it
	save_config_file(config_file, config)
	# check api key for integrity
	if not re.match("^[0-9a-z]{40}$", api_key):
		print "%s: ApiKey has invalid format" % config_file
		sys.exit(1)
	return api_key

# api
def api_get_stations(api_key, contract = None):
	payload = { "apiKey": api_key }
	if contract is not None:
		payload["contract"] = contract
	url = "https://api.jcdecaux.com/vls/v1/stations"
	headers = { "Accept": "application/json" }
	r = requests.get(url, params=payload, headers=headers)
	# avoid ultra-slow auto-detect
	# see https://github.com/kennethreitz/requests/issues/2359
	r.encoding = "utf-8"
	return r.text

# check api error
def check_api_error(json):
	if type(json) is dict and t0_json.has_key("error"):
		print "API: %s" % t0_json["error"]
		sys.exit(1)

# check input stream
def check_and_fix_input_for_bugs(json):
	for station in json:
		# api sometime provides 'null', so we consider the update was "now" instead
		if station["last_update"] is None:
			station["last_update"] = int(time.time())
			logging.warning("Station %s_%s had null 'last_update', overrided using time.time()=%s",
				station["contract_name"], station["number"],station["last_update"])

# deduplicate using t0, t1 and t2
def deduplicate_store(t0_tree, t1_tree, t2_tree):
	# browse t0 and 
	for t0_contract_name in t0_tree:
		# extract t0 contract stations
		t0_stations = t0_tree[t0_contract_name]
		# check for t1
		if t1_tree is None:
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
			if t2_tree is None:
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

#########################################
# work
# t0 = current, t1 = previous, t2 = oldest
#########################################
def work():
	# create program folders
	make_sure_program_folders_exist()
	# load api key from config file
	api_key = load_api_key()
	# fetch data from api
	text = api_get_stations(api_key)
	# parse json
	t0_json = json.loads(text)
	# check that api returnd valid data
	check_api_error(t0_json)
	# check input for bugs
	check_and_fix_input_for_bugs(t0_json)
	# re-convert so fixes are flushed to cache
	text = json.dumps(t0_json)
	# save t0 data to disk
	save_unicode_file(text,"~/.jcd/cache/t0")
	# load cache
	t1_text = load_unicode_file("~/.jcd/cache/t1")
	t2_text = load_unicode_file("~/.jcd/cache/t2")
	# build trees
	t0_tree = station_list_to_tree(t0_json)
	t1_json = None
	t2_json = None
	t1_tree = None
	t2_tree = None
	if t1_text is not None:
		t1_json = json.loads(t1_text)
		t1_tree = station_list_to_tree(t1_json)
	if t2_text is not None:
		t2_json = json.loads(t2_text)
		t2_tree = station_list_to_tree(t2_json)
	# deduplicate and store
	deduplicate_store(t0_tree,t1_tree,t2_tree)
	# don't output if empty set
	if not storage:
		return
	# output stored data
	output_text = json.dumps(storage)
	time_stamp = time.time()
	save_unicode_file(output_text,"~/.jcd/updates/%i.json" % time_stamp)
	# age cache files
	move_file("~/.jcd/cache/t1","~/.jcd/cache/t2")
	move_file("~/.jcd/cache/t0","~/.jcd/cache/t1")


# main
def main():
	# setup logging
	logging.basicConfig(format="%(levelname)s:%(asctime)s %(message)s")
	# do work
	work()

main()
