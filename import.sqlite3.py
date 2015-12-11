#! /usr/bin/env python

import sys
import json
import glob
import time
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
	connection = sqlite3.connect(full_db_path)
	return connection

# create table if necessary
def create_storage_table(connection):
	connection.execute(
		'''CREATE TABLE IF NOT EXISTS samples (
		timestamp INTEGER PRIMARY KEY,
		bike INTEGER,
		empty INTEGER,
		status INTEGER)''')

def import_station_dynamic_data(connection,station):
	connection.execute(
		'''INSERT INTO
		samples (timestamp,bike,empty,status)
		VALUES(?,?,?,?)''',
		(station["update"],
		station["bikes"],
		station["empty"],
		station["status"]))

# import contract into database
def import_contract_station(contract_name, station_number, station):
	try:
		# open or create db file
		connection = open_database(contract_name, station_number)
		# due to context, commit on success, auto-rollback on except
		with connection:
			# create table if necessary
			create_storage_table(connection)
			# import updated stations
			import_station_dynamic_data(connection, station)
	except (sqlite3.OperationalError,sqlite3.IntegrityError,sqlite3.Error) as e:
		logging.error(e)
		raise JcdImportException("Failed to import station %s" % station)

# import update file into databases
def import_update(filename):
	n = 0
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
			n += 1
	return n

# work
def work():
	files = list_files("~/.jcd/updates", "json")
	for f in files:
		try:
			t0 = time.time()
			n = import_update(f)
			dt = time.time() - t0
			rate = None
			if dt != 0:
				rate = n / dt
			logging.info("File %s imported (%s samples in %s seconds, rate %s)" % (f,n,dt,rate))
		except JcdImportException as e:
			logging.error(e)
			logging.warning("Skipping file %s" % f)

# main
def main():
	# setup logging
	logging.basicConfig(format="%(levelname)s:%(asctime)s %(message)s")
	# do work
	work()

main()
