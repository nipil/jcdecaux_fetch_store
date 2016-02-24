#! /usr/bin/env python
# -*- coding: UTF-8 -*- vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

# The MIT License (MIT)
#
# Copyright (c) 2015-2016 Nicolas Pillot
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the 'Software'),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import sys
import time
import json
import errno
import shutil
import random
import os.path
import sqlite3
import argparse
import requests

# applications specific exception
class JcdException(Exception):

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

# manages access to the application database
class SqliteDB(object):

    def __init__(self, db_filename):
        self._db_path = SqliteDB.getFullPath(db_filename)
        self.connection = None
        self._att_databases = {}

    @staticmethod
    def getFullPath(filename):
        return os.path.normpath(
            "%s/%s" % (App.DataPath, filename))

    def open(self):
        if self.connection is None:
            self.connection = sqlite3.connect(self._db_path)

    def close(self):
        # close main databases
        if self.connection is not None:
            self.connection.close()
        self.connection = None

    def commit(self):
        if self.connection is not None:
            self.connection.commit()

    def __enter__(self):
        # open the connection if it's not already open
        self.open()
        # return self in case a 'as' statement is present
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # close the connection if it's open
        self.close()
        # don't suppress the eventual exception
        return False

    def vacuum(self):
        if self.connection is not None:
            self.connection.execute("vacuum")

    def hasTable(self, name):
        try:
            req = self.connection.execute(
                '''
                SELECT count(*), name
                FROM sqlite_master
                WHERE type = "table" AND name = ?
                ''', (name, ))
            count, name = req.fetchone()
            return count != 0
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error checking if table [%s] exists" % name)

    def attachDatabase(self, file_name, schema_name):
        file_path = SqliteDB.getFullPath(file_name)
        if schema_name in self._att_databases:
            raise JcdException(
                "Database is already attached as schema [%s]" % schema_name)
        try:
            self.connection.execute(
                '''
                ATTACH DATABASE ? AS ?
                ''', (file_path, schema_name))
            # memorize attachement
            self._att_databases[schema_name] = file_name
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error while attaching [%s] as schema [%s]" % (
                    file_name, schema_name))

    def detachDatabase(self,schema_name):
        if schema_name not in self._att_databases:
            raise JcdException(
                "Schema [%s] is not attached" % schema_name)
        try:
            self.connection.execute(
                '''
                DETACH DATABASE ?
                ''', (schema_name, ))
            del self._att_databases[schema_name]
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error while detaching [%s]" % (schema_name, ))

    def _detachAllDatabases(self):
        for schema in self._att_databases.keys():
            self.detachDatabase(schema)

    def getCount(self, target):
        try:
            req = self.connection.execute(
                '''
                SELECT COUNT(*) FROM %s
                ''' % target)
            return req.fetchone()[0]
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error while getting rowcount for [%s]" % (target, ))

# settings table
class SettingsDAO(object):

    TableName = "settings"

    def __init__(self, database):
        self._database = database

    def createTable(self):
        if App.Verbose:
            print "Creating table [%s]" % self.TableName
        try:
            self._database.connection.execute(
                '''
                CREATE TABLE %s (
                    name TEXT PRIMARY KEY NOT NULL,
                    value, -- no type, use affinity
                    last_modification INTEGER NOT NULL)
                ''' % self.TableName)
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error while creating table [%s]" % self.TableName)

    def setParameter(self, name, value):
        try:
            self._database.connection.execute(
                '''
                INSERT OR REPLACE INTO %s (name, value, last_modification)
                VALUES (?, ?, strftime('%%s', 'now'))
                ''' % self.TableName, (name, value))
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error while setting parameter [%s]" % name)

    def getParameter(self, name):
        try:
            results = self._database.connection.execute(
                '''
                SELECT value,
                    datetime(last_modification, 'unixepoch') as modified_stamp
                FROM %s
                WHERE name = ?
                ''' % self.TableName, (name, ))
            result = results.fetchone()
            if result is None:
                return (None, None)
            return result
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error while fetching parameter [%s]" % name)

# contract table
class ContractsDAO(object):

    TableName = "contracts"

    def __init__(self, database):
        self._database = database

    def createTable(self):
        if App.Verbose:
            print "Creating table [%s]" % self.TableName
        try:
            self._database.connection.execute(
                '''
                CREATE TABLE %s (
                    contract_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    contract_name TEXT UNIQUE NOT NULL,
                    commercial_name TEXT NOT NULL,
                    country_code TEXT NOT NULL,
                    cities TEXT NOT NULL)
                ''' % self.TableName)
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error while creating table [%s]" % self.TableName)

    def storeContracts(self, json, timestamp):
        # merge cities together
        for contract in json:
            contract["timestamp"] = timestamp
            contract["cities"] = "/".join(contract["cities"])
        try:
            # update any existing contracts
            self._database.connection.executemany(
                '''
                UPDATE OR IGNORE %s
                SET timestamp = :timestamp,
                    commercial_name = :commercial_name,
                    country_code = :country_code,
                    cities = :cities
                WHERE contract_name = :name
                ''' % self.TableName, json)
            # add possible new contracts
            req = self._database.connection.executemany(
                '''
                INSERT OR IGNORE INTO %s (
                    contract_id,
                    timestamp,
                    contract_name,
                    commercial_name,
                    country_code,
                    cities)
                VALUES (
                    NULL,
                    :timestamp,
                    :name,
                    :commercial_name,
                    :country_code,
                    :cities)
                ''' % self.TableName, json)
            # return number of inserted records
            return req.rowcount
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException("Database error while inserting contracts")

# settings table
class FullSamplesDAO(object):

    TableNameNew = "new_samples"
    TableNameOld = "old_samples"

    def __init__(self, database):
        self._database = database

    def createTables(self):
        self._createTable(self.TableNameNew)
        self._createTable(self.TableNameOld)

    def _createTable(self, tableName):
        if App.Verbose:
            print "Creating table [%s]" % tableName
        try:
            self._database.connection.execute(
                '''
                CREATE TABLE %s (
                    timestamp INTEGER NOT NULL,
                    contract_id INTEGER NOT NULL,
                    station_number INTEGR NOT NULL,
                    available_bikes INTEGER NOT NULL,
                    available_bike_stands INTEGER NOT NULL,
                    status INTEGER NOT NULL,
                    bike_stands INTEGER NOT NULL,
                    bonus INTEGER NOT NULL,
                    banking INTEGER NOT NULL,
                    position TEXT NOT NULL,
                    address TEXT NOT NULL,
                    station_name TEXT NOT NULL,
                    last_update INTEGER,
                    PRIMARY KEY (contract_id, station_number))
                ''' % tableName)
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error while creating table [%s]" % tableName)

    def storeNewSamples(self, json, timestamp):
        # adapt json to database schema
        for station in json:
            station["timestamp"] = timestamp
            station["status"] = 1 if station["status"] == "OPEN" else 0
            station["bonus"] = 1 if station["bonus"] == True else 0
            station["banking"] = 1 if station["banking"] == True else 0
            station["position"] = "/".join(
                str(v) for v in station["position"].values())
        try:
            # insert station data
            req = self._database.connection.executemany(
                '''
                INSERT OR REPLACE INTO %s (
                    timestamp,
                    contract_id,
                    station_number,
                    available_bikes,
                    available_bike_stands,
                    status,
                    bike_stands,
                    bonus,
                    banking,
                    position,
                    address,
                    station_name,
                    last_update)
                VALUES (
                    :timestamp,
                    (SELECT contract_id FROM %s
                        WHERE contract_name = :contract_name),
                    :number,
                    :available_bikes,
                    :available_bike_stands,
                    :status,
                    :bike_stands,
                    :bonus,
                    :banking,
                    :position,
                    :address,
                    :name,
                    :last_update)
                ''' % (self.TableNameNew, ContractsDAO.TableName), json)
            # return number of inserted records
            return req.rowcount
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException("Database error while inserting state")

    def moveNewSamplesIntoOld(self, date):
        try:
            req = self._database.connection.execute(
                '''
                INSERT OR REPLACE INTO %s
                SELECT * FROM %s
                WHERE date(timestamp,'unixepoch') = ?
                ''' % (self.TableNameOld, self.TableNameNew),
                (date, ))
            inserted = req.rowcount
            req = self._database.connection.execute(
                '''
                DELETE FROM %s
                WHERE date(timestamp,'unixepoch') = ?
                ''' % self.TableNameNew,
                (date, ))
            deleted = req.rowcount
            # verify coherence
            if deleted != inserted:
                raise JcdException(
                "Ageing operation failed (%i inserted, %i deleted)" % (
                    inserted, deleted))
            # return aged number of records
            return inserted
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException("Database error ageing new samples into old")

    def getNewCount(self):
        return self._database.getCount(self.TableNameNew)

    def getOldCount(self):
        return self._database.getCount(self.TableNameOld)

# stored sample DAO
class ShortSamplesDAO(object):

    TableNameChanged = "changed_samples"
    TableNameArchive = "archived_samples"

    def __init__(self, database):
        self._database = database

    def _createTable(self, database, tableName):
        try:
            database.connection.execute(
                '''
                CREATE TABLE %s (
                    timestamp INTEGER NOT NULL,
                    contract_id INTEGER NOT NULL,
                    station_number INTEGR NOT NULL,
                    available_bikes INTEGER NOT NULL,
                    available_bike_stands INTEGER NOT NULL,
                    PRIMARY KEY (timestamp, contract_id, station_number))
                ''' % tableName)
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error while creating table [%s]" % tableName)

    def createTableChanged(self):
        if App.Verbose:
            print "Creating table [%s]" % self.TableNameChanged
        self._createTable(self._database, self.TableNameChanged)

    def buildChangedSamples(self):
        try:
            self._database.connection.execute(
                '''
                DELETE FROM %s
                ''' % self.TableNameChanged)
            req = self._database.connection.execute(
                '''
                INSERT INTO %s
                SELECT new.timestamp,
                    new.contract_id,
                    new.station_number,
                    new.available_bikes,
                    new.available_bike_stands
                FROM %s AS new LEFT OUTER JOIN %s AS old
                ON new.contract_id=old.contract_id AND
                    new.station_number = old.station_number
                WHERE new.available_bikes != old.available_bikes OR
                    new.available_bike_stands != old.available_bike_stands OR
                    old.station_number IS NULL
                ORDER BY new.timestamp, new.contract_id, new.station_number
                ''' % (self.TableNameChanged,
                    FullSamplesDAO.TableNameNew,
                    FullSamplesDAO.TableNameOld))
            # return number of inserted records
            return req.rowcount
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException("Database error building changed samples")

    def getChangedStatistics(self):
        try:
            req = self._database.connection.execute(
                '''
                SELECT
                    DATE(timestamp, 'unixepoch') AS day,
                    COUNT(timestamp) AS num_changed_samples
                FROM %s
                GROUP BY day
                ORDER BY day ASC
                ''' % self.TableNameChanged)
            return req.fetchall()
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException("Database error getting changed date list")

    def getSchemaName(self, date):
        return "samples_%s" % date.replace("-", "_")

    def getDbFileName(self, schema_name):
        return "%s.db" % schema_name

    def initializeDateDb(self, dbfilename):
        with SqliteDB(dbfilename) as storage_db:
            if not storage_db.hasTable(self.TableNameArchive):
                self._createTable(storage_db, self.TableNameArchive)
                return True
        return False

    def archiveChangedSamples(self, date, target_schema):
        try:
            req = self._database.connection.execute(
                '''
                INSERT INTO %s.%s
                SELECT * FROM %s
                WHERE date(timestamp,'unixepoch') = ?
                ''' % (target_schema,
                    self.TableNameArchive,
                    self.TableNameChanged),
                (date, ))
            inserted = req.rowcount
            req = self._database.connection.execute(
                '''
                DELETE FROM %s
                WHERE date(timestamp,'unixepoch') = ?
                ''' % self.TableNameChanged,
                (date, ))
            deleted = req.rowcount
            # verify coherence
            if deleted != inserted:
                raise JcdException(
                "Archive operation failed (%i inserted, %i deleted)" % (
                    inserted, deleted))
            # return number of archived records
            return inserted
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error achiving changed samples to %s" % target_schema)

    def getChangedCount(self):
        return self._database.getCount(self.TableNameChanged)

# access jcdecaux web api
class ApiAccess(object):

    BaseUrl = "https://api.jcdecaux.com/vls/v1"

    def __init__(self, apikey):
        self._apikey = apikey

    def _parseReply(self, reply_text):
        reply_json = json.loads(reply_text)
        if type(reply_json) is dict and reply_json.has_key("error"):
            error = reply_json["error"]
            # Test for invalid API key
            if error == "Unauthorized":
                # TODO: disable fetch
                pass
            raise JcdException(
                "JCDecaux API exception: %s" % reply_json["error"])
        return reply_json

    def _get(self, sub_url, payload=None):
        if payload is None:
            payload = {}
        # add the api key to the call
        payload["apiKey"] = self._apikey
        url = "%s/%s" % (self.BaseUrl, sub_url)
        headers = {"Accept": "application/json"}
        try:
            request = requests.get(url, params=payload, headers=headers)
            # avoid ultra-slow character set auto-detection
            # see https://github.com/kennethreitz/requests/issues/2359
            request.encoding = "utf-8"
            # check for api error
            return self._parseReply(request.text)
        except requests.exceptions.RequestException as exception:
            raise JcdException(
                "JCDecaux Requests exception: (%s) %s" % (
                    type(exception).__name__, exception))

    def getStations(self):
        return self._get("stations")

    def getContractStation(self, contract_name, station_id):
        return self._get("stations/%i" % station_id,
            {"contract": contract_name})

    def getContractStations(self, contract_name):
        return self._get("stations",
            {"contract": contract_name})

    def getContracts(self):
        return self._get("contracts")

# initialize application data
class InitCmd(object):

    def __init__(self, args):
        self._args = args

    def _removeFolder(self):
        # delete the folder
        try:
            if App.Verbose:
                print "Removing folder [%s] and its content" % App.DataPath
            shutil.rmtree(App.DataPath)
        except OSError as error:
            # silently ignore "absent directory"
            if error.errno == errno.ENOENT:
                return
            # on other errors
            raise JcdException("Could not remove folder : %s" % error)

    def _createFolder(self):
        try:
            if App.Verbose:
                print "Creating folder [%s]" % App.DataPath
            os.makedirs(App.DataPath)
        except OSError as exception:
            # folder exists
            if exception.errno == errno.EEXIST:
                raise JcdException(
                    "Folder [%s] already exists. Use --force "
                    "to destroy everything anyway." % App.DataPath)
            # other system error
            raise

    def _createTables(self):
        with SqliteDB(App.DbName) as app_db:
            settings = SettingsDAO(app_db)
            settings.createTable()
            contracts = ContractsDAO(app_db)
            contracts.createTable()
            full_samples = FullSamplesDAO(app_db)
            full_samples.createTables()
            short_samples = ShortSamplesDAO(app_db)
            short_samples.createTableChanged()

    # set default parameters
    def setDefaultParameters(self):
        with SqliteDB(App.DbName) as app_db:
            settings = SettingsDAO(app_db)
            for value in ConfigCmd.Parameters:
                if App.Verbose and value[3] is not None:
                    print "Setting parameter [%s] to default value [%s]" % (
                        value[0], value[3])
                    settings.setParameter(value[0], value[3])
            # if all went well
            app_db.commit()

    def run(self):
        # remove folder if creation is forced
        if self._args.force:
            self._removeFolder()
        self._createFolder()
        # create tables in data db
        self._createTables()
        self.setDefaultParameters()

# configure settings:
class ConfigCmd(object):

    Parameters = (
        ('apikey', str, 'JCDecaux API key', None),
        ('fetch', int, 'Enable/disable fetch operation', 0),
        ('import', int, 'Enable/disable import operation', 0),
    )

    def __init__(self, args):
        self._args = args

    def displayParam(self, param):
        with SqliteDB(App.DbName) as app_db:
            settings = SettingsDAO(app_db)
            (value, last_modification) = settings.getParameter(param)
            # don't check for verbose, display is mandatory
            print "%s = %s (last modified on %s)" % (
                param, value, last_modification)

    def updateParam(self, param, value):
        with SqliteDB(App.DbName) as app_db:
            settings = SettingsDAO(app_db)
            settings.setParameter(param, value)
            # if all went well
            app_db.commit()
            if App.Verbose:
                print "Setting %s = %s" % (param, value)

    def run(self):
        # modify each fully provided parameter
        has_modified = False
        args_dict = self._args.__dict__
        for value in ConfigCmd.Parameters:
            param = value[0]
            if param in args_dict:
                value = args_dict[param]
                if value is not None:
                    self.updateParam(param, value)
                    has_modified = True
        # if nothing was provided, display all current parameter value
        if not has_modified:
            for value in self.Parameters:
                self.displayParam(value[0])

# administration
class AdminCmd(object):

    Parameters = (
        ('vacuum', 'defragment and trim sqlite database'),
        ('apitest', 'test JCDecaux API access'),
    )

    def __init__(self, args):
        self._args = args

    def vacuum(self):
        if App.Verbose:
            print "Vacuuming SqliteDB"
        with SqliteDB(App.DbName) as app_db:
            app_db.vacuum()

    def apitest(self):
        if App.Verbose:
            print "Testing JCDecaux API access"
        with SqliteDB(App.DbName) as app_db:
            # fetch api key
            settings = SettingsDAO(app_db)
            apikey = settings.getParameter("apikey")
            if apikey is None:
                raise JcdException(
                    "API key is not set ! "
                    "Please configure using 'config --apikey'")
            # real testing
            api = ApiAccess(apikey)
            # get all available contracts
            if App.Verbose:
                print "Searching contracts ..."
            contracts = api.getContracts()
            count = len(contracts)
            if App.Verbose:
                print "Found %i contracts." % count
            # get a random contract
            rnd = random.randint(0, count-1)
            contract = contracts[rnd]
            if App.Verbose:
                print "Fetching stations contract [%s] ..." % contract["name"]
            stations = api.getContractStations(contract["name"])
            count = len(stations)
            if App.Verbose:
                print "Found %i stations." % count
            # get a random contract
            rnd = random.randint(0, count-1)
            station = stations[rnd]
            if App.Verbose:
                print "Fetching a single station [%i] of contract [%s] ..." % (
                station["number"], contract["name"])
            station = api.getContractStation(
                contract["name"], station["number"])
            if App.Verbose:
                print "Station name is [%s]" % station["name"]
            # test OK
            if App.Verbose:
                print "API TEST SUCCESS"

    def run(self):
        args_dict = self._args.__dict__
        for param in AdminCmd.Parameters:
            name = param[0]
            if name in args_dict:
                value = args_dict[name]
                if type(value) == bool and value:
                    function = getattr(self, name)
                    function()

# fetch information from api:
class FetchCmd(object):

    def __init__(self, args):
        self._args = args
        self._timestamp = int(time.time())

    def fetchContracts(self):
        with SqliteDB(App.DbName) as app_db:
            # fetch api key
            settings = SettingsDAO(app_db)
            apikey = settings.getParameter("apikey")
            if apikey is None:
                raise JcdException(
                    "API key is not set ! "
                    "Please configure using 'config --apikey'")
            # get all available contracts
            api = ApiAccess(apikey)
            json_contracts = api.getContracts()
            dao = ContractsDAO(app_db)
            new_contracts_count = dao.storeContracts(
                json_contracts, self._timestamp)
            # if everything went fine
            app_db.commit()
            if App.Verbose:
                print "New contracts added: %i" % new_contracts_count

    def fetchState(self):
        with SqliteDB(App.DbName) as app_db:
            settings = SettingsDAO(app_db)
            full_dao = FullSamplesDAO(app_db)
            short_dao = ShortSamplesDAO(app_db)
            # fetch api key
            apikey = settings.getParameter("apikey")
            if apikey is None:
                raise JcdException(
                    "API key is not set ! "
                    "Please configure using 'config --apikey'")
            # get all station states
            api = ApiAccess(apikey)
            json_stations = api.getStations()
            num_new = full_dao.storeNewSamples(json_stations, self._timestamp)
            if App.Verbose:
                print "New samples acquired: %i" % num_new
            # analyse changes
            num_changed = short_dao.buildChangedSamples()
            if App.Verbose:
                print "Changed samples available for archive: %i" % num_changed
            # if everything went fine
            app_db.commit()

    def run(self):
        if self._args.contracts:
            self.fetchContracts()
        if self._args.state:
            self.fetchState()

# store state into database:
class StoreCmd(object):

    def __init__(self, args):
        self._args = args

    def run(self):
        with SqliteDB(App.DbName) as app_db:
            full_dao = FullSamplesDAO(app_db)
            short_dao = ShortSamplesDAO(app_db)
            # daily databases are used
            stats = short_dao.getChangedStatistics()
            for date, count in stats:
                # create, initialize databases as necessary
                schemas_name = short_dao.getSchemaName(date)
                db_filename = short_dao.getDbFileName(schemas_name)
                # prepare archive storage if needed
                created = short_dao.initializeDateDb(db_filename)
                if App.Verbose and created:
                    print "Database [%s] created" % db_filename
                # WARNING: attaching commits current transaction
                app_db.attachDatabase(db_filename, schemas_name)
                # moving changed samples to attached db
                if App.Verbose:
                    print "Archiving %i changed samples into %s" % (
                        count, schemas_name)
                # archive changed samples from date
                num_stored = short_dao.archiveChangedSamples(date, schemas_name)
                if num_stored != count:
                    raise JcdException(
                        "Not all changed samples could be archived")
                # age new samples into old
                num_aged = full_dao.moveNewSamplesIntoOld(date)
                if App.Verbose:
                    print "Aged %i samples for %s" % (num_aged, date)
                # if everything went fine for this date
                app_db.commit()
                # WARNING: detaching commits current transaction
                app_db.detachDatabase(schemas_name)
                # verify that nothing new or changed remains after processing
            remain_new = full_dao.getNewCount()
            remain_changed = short_dao.getChangedCount()
            if remain_new > 0 or remain_changed > 0:
                raise JcdException((
                    "Unprocessed samples will be lost: "
                    "%i changed linked to %i new") % (
                        remain_changed, remain_new))

# main app
class App(object):

    DataPath = None
    DbName = None
    Verbose = None

    def __init__(self, default_data_path, default_app_dbname):
        # store data path
        self._default_data_path = default_data_path
        # store main dbname
        self._default_app_dbname = default_app_dbname
        # top parser
        self._parser = argparse.ArgumentParser(
            description='Fetch and store JCDecaux API results')
        # top level argument for data destination
        self._parser.add_argument(
            '--datadir',
            help='choose data folder (default: %s)' % default_data_path,
            default=default_data_path
        )
        self._parser.add_argument(
            '--dbname',
            help='choose db filename (default: %s)' % default_app_dbname,
            default=default_app_dbname
        )
        self._parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='display operationnal informations'
        )
        # top level commands
        top_command = self._parser.add_subparsers(dest='command')
        # init command
        init = top_command.add_parser(
            'init',
            help='create application files',
            description='Initialize application'
        )
        init.add_argument(
            '--force', '-f',
            action='store_true',
            help='overwrite existing files'
        )
        # config command
        config = top_command.add_parser(
            'config',
            help='config application parameters',
            description='Configure application'
        )
        for value in ConfigCmd.Parameters:
            config.add_argument(
                '--%s' % value[0],
                type=value[1],
                help=value[2],
            )
        # admin command
        admin = top_command.add_parser(
            'admin',
            help='administrate application database',
            description='Manage database'
        )
        for value in AdminCmd.Parameters:
            admin.add_argument(
                '--%s' % value[0],
                action='store_true',
                help=value[1],
            )
        # fetch command
        fetch = top_command.add_parser(
            'fetch',
            help='get information from the API',
            description='Get from API'
        )
        fetch.add_argument(
            '--contracts', '-c',
            action='store_true',
            help='get contracts'
        )
        fetch.add_argument(
            '--state', '-s',
            action='store_true',
            help='get current state'
        )
        # store command
        top_command.add_parser(
            'store',
            help='store fetched state into database',
            description='Store state in database'
        )

    def run(self):
        try:
            # parse arguments
            args = self._parser.parse_args()
            # consume data-path argument
            App.DataPath = os.path.expanduser(args.datadir)
            del args.datadir
            # consume db name argument
            App.DbName = os.path.expanduser(args.dbname)
            del args.dbname
            # consume verbose
            App.Verbose = args.verbose
            del args.verbose
            # consume command
            command = getattr(self, args.command)
            del args.command
            # run requested command
            command(args)
        except JcdException as exception:
            print "JcdException: %s" % exception
            sys.exit(1)

    def init(self, args):
        init = InitCmd(args)
        init.run()

    def config(self, args):
        config = ConfigCmd(args)
        config.run()

    def admin(self, args):
        admin = AdminCmd(args)
        admin.run()

    def fetch(self, args):
        fetch = FetchCmd(args)
        fetch.run()

    def store(self, args):
        store = StoreCmd(args)
        store.run()
# main
if __name__ == '__main__':
    app = App("~/.jcd", "app.db")
    try:
        app.run()
    except KeyboardInterrupt:
        pass
