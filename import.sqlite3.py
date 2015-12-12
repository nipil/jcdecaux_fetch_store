#! /usr/bin/env python

import sys
import json
import glob
import time
import codecs
import shutil
import sqlite3
import os.path
import logging

storage = {}

class JcdImportException(Exception):
	def __init__(self,*args,**kwargs):
		Exception.__init__(self,*args,**kwargs)

def move_file(src,dst):
	sn = os.path.expanduser(src)
	dn = os.path.expanduser(dst)
	shutil.move(sn,dn)

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
def open_database():
	# open or create db file
	db_path = "~/.jcd/databases/jcd.sqlite3"
	full_db_path = os.path.expanduser(db_path)
	connection = sqlite3.connect(full_db_path)
	return connection

# create table if necessary
def create_storage_table(connection):
	connection.execute(
		'''CREATE TABLE IF NOT EXISTS samples (
		contract_name STRING,
		station_number INT,
		timestamp INTEGER,
		last_update INTEGER,
		bike INTEGER,
		empty INTEGER,
		status INTEGER,
		PRIMARY KEY (contract_name, station_number, timestamp))''')

def import_station_dynamic_data(connection,contract_name,station_number,timestamp,station):
	connection.execute(
		'''INSERT INTO
		samples (contract_name,station_number,timestamp,last_update,bike,empty,status)
		VALUES(?,?,?,?,?,?,?)''',
		(contract_name,
		station_number,
		timestamp,
		station["update"],
		station["bikes"],
		station["empty"],
		station["status"]))

# import json into database
def import_updates(connection, json, timestamp):
	n = 0
	# create single table
	create_storage_table(connection)
	# import a contract's updates
	for contract_name in json:
		contract = json[contract_name]
		for station_key in contract:
			station = contract[station_key]
			station_number = int(station_key)
			# import updated stations
			import_station_dynamic_data(connection, contract_name, station_number, timestamp, station)
			n += 1
	return n

# extract timestamp from file name
def get_timestamp(filename):
	b = os.path.basename(filename)
	s = os.path.splitext(b)
	return s[0]

# import update file into databases
def import_update(filename):
	timestamp = get_timestamp(filename)
	# loading text content
	content = load_unicode_file(filename)
	# load json from text
	json = convert_to_json(content)
	n = 0
	try:
		# open or create db file
		connection = open_database()
		# due to context, commit on success, auto-rollback on except
		with connection:
			n = import_updates(connection, json, timestamp)
			move_file(filename,"~/.jcd/archives/")
		connection.close()
	except IOError as e:
		logging.error(e)
		raise JcdImportException("Failed to archive %s" % filename)
	except (sqlite3.OperationalError,sqlite3.IntegrityError,sqlite3.Error) as e:
		logging.error(e)
		raise JcdImportException("Failed to import %s" % filename)
	return n

# work
def work():
	files = list_files("~/.jcd/updates", "json")
	for f in files:
		try:
			n = import_update(f)
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
