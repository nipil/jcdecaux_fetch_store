#! /usr/bin/env python

import sys
import json
import glob
import codecs
import sqlite3
import os.path
import logging

storage = {}

class JcdImportException(Exception):
	def __init__(self,*args,**kwargs):
		Exception.__init__(self,*args,**kwargs)

# load unicode to file
def load_unicode_file(filename):
	try:
		fn = os.path.expanduser(filename)
		with codecs.open(fn,"rt",encoding="utf8") as f:
			return f.read()
	except IOError as e:
		logging.error(e)
		raise JcdImportException("Failed to load unicode file %s" % filename)

# load json from content
def convert_to_json(content):
	try:
		return json.loads(content)
	except (TypeError,OverflowError,ValueError,TypeError) as e:
		logging.error(e)
		raise JcdImportException("Failed to convert content to json")

# list available files to import
def list_files(path, ext):
	full_path = os.path.expanduser(path)
	file_list = glob.glob("%s/*.%s" % (full_path, ext))
	return sorted(file_list)

# open sqlite3 database
def open_database(contract_name, station_number):
	# open or create db file
	db_path = "~/.jcd/databases/%s_%s.sqlite3" % (contract_name, station_number)
	full_db_path = os.path.expanduser(db_path)
	try:
		return sqlite3.connect(full_db_path)
	except sqlite3.OperationalError as e:
		logging.error(e)
		raise JcdImportException("Failed to open database %s" % full_db_path)

# import contract into database
def import_contract_station(contract_name, station_number, station):
	# open/create/init database
	db = open_database(contract_name, station_number)
	# create table if necessary
	pass
	# import updated stations
	print "contract %s number %i station %s" % (contract_name, station_number, station)
	# commit changes
	pass

# import update file into databases
def import_update(filename):
	# loading text content
	content = load_unicode_file(filename)
	# load json from text
	json = convert_to_json(content)
	# import a contract's updates
	for contract_name in json:
		contract = json[contract_name]
		for station_key in contract:
			station = contract[station_key]
			station_number = int(station_key)
			import_contract_station(contract_name,station_number,station)

# work
def work():
	files = list_files("~/.jcd/updates", "json")
	for f in files:
		try:
			import_update(f)
		except JcdImportException as e:
			logging.error(e)
			logging.warning("Skipping file %s" % f)
		return

# main
def main():
	# setup logging
	logging.basicConfig(format="%(levelname)s:%(asctime)s %(message)s")
	# do work
	work()

main()
