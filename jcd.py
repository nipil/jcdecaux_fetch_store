#! /usr/bin/env python
# -*- coding: UTF-8 -*- vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

# The MIT License (MIT)
#
# Copyright (c) 2015 Nicolas Pillot
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

    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

# manages access to the application database
class SqliteDB:

    def __init__(self, db_filename):
        self._db_filename = db_filename
        self._db_path = os.path.normpath("%s/%s" % (App.DataPath,self._db_filename))
        self.connection = None

    def open(self):
        if self.connection is None:
            self.connection = sqlite3.connect(self._db_path)

    def close(self):
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

    def hasTable(self,name):
        try:
            req = self.connection.execute(
                '''SELECT count(*),name
                FROM sqlite_master
                WHERE type = 'table' AND
                name = ?
                ''', (name,))
            count, name = req.fetchone();
            return count != 0
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error checking if table [%s] exists" % name)

# settings table
class SettingsDAO:

    TableName = "settings"

    def __init__(self, database):
        self._database = database

    def createTable(self):
        print "Creating table [%s]" % self.TableName
        try:
            self._database.connection.execute(
                '''CREATE TABLE %s(
                    name TEXT PRIMARY KEY NOT NULL,
                    value, -- no type, use affinity
                    last_modification INTEGER NOT NULL
                )''' % self.TableName)
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while creating table [%s]" % self.TableName)

    def setParameter(self, name, value):
        try:
            self._database.connection.execute(
                '''INSERT OR REPLACE INTO
                    %s(name,value,last_modification)
                    VALUES(?,?, strftime('%%s', 'now'))
                ''' % self.TableName, (name,value))
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while setting parameter [%s]" % name)

    def getParameter(self, name):
        try:
            results = self._database.connection.execute(
                '''SELECT value, datetime(last_modification,'unixepoch')
                    FROM %s
                    WHERE name = ?
                ''' % self.TableName, (name,))
            r = results.fetchone()
            if r is None:
                return (None, None)
            return r
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while fetching parameter [%s]" % name)

# contract table
class ContractsDAO:

    TableName = "contracts"

    def __init__(self, database):
        self._database = database

    def createTable(self):
        print "Creating table [%s]" % self.TableName
        try:
            self._database.connection.execute(
                '''CREATE TABLE %s(
                contract_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                contract_name TEXT UNIQUE NOT NULL,
                commercial_name TEXT NOT NULL,
                country_code TEXT NOT NULL,
                cities TEXT NOT NULL
                )''' % self.TableName)
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while creating table [%s]" % self.TableName)

    def storeContracts(self, json):
        # merge cities together
        for contract in json:
            contract["cities"] = "/".join(contract["cities"])
        try:
            # update any existing contracts
            self._database.connection.executemany(
                '''UPDATE OR IGNORE %s SET
                    commercial_name = :commercial_name,
                    country_code = :country_code,
                    cities = :cities
                    WHERE contract_name = :name
                ''' % self.TableName, json)
            # add possible new contracts
            req = self._database.connection.executemany(
                '''INSERT OR IGNORE INTO
                    %s(contract_id,contract_name,commercial_name,country_code,cities)
                    VALUES(NULL,:name,:commercial_name,:country_code,:cities)
                ''' % self.TableName, json)
            # return number of inserted records
            return req.rowcount
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while inserting contracts")

# settings table
class FullSamplesDAO:

    TableNameNew = "new_samples"
    TableNameOld = "old_samples"

    def __init__(self, database):
        self._database = database

    def createTables(self):
        self._createTable(self.TableNameNew)
        self._createTable(self.TableNameOld)

    def _createTable(self, tableName):
        print "Creating table [%s]" % tableName
        try:
            self._database.connection.execute(
                '''CREATE TABLE %s(
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
                PRIMARY KEY (contract_id, station_number)
                )''' % tableName)
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while creating table [%s]" % tableName)

    def storeNewSamples(self, json):
        # get current time in UTC
        timestamp = int(time.time())
        # adapt json to database schema
        for station in json:
            station["timestamp"] = timestamp
            station["status"] = 1 if station["status"] == "OPEN" else 0
            station["bonus"] = 1 if station["bonus"] == True else 0
            station["banking"] = 1 if station["banking"] == True else 0
            station["position"] = "/".join(map(str,station["position"].values()))
        try:
            # insert station data
            req = self._database.connection.executemany(
                '''INSERT OR REPLACE INTO %s(timestamp,
                    contract_id, station_number, available_bikes,
                    available_bike_stands, status, bike_stands,
                    bonus, banking, position, address,
                    station_name, last_update)
                    VALUES(:timestamp, (SELECT contract_id FROM %s
                        WHERE contract_name = :contract_name),
                    :number, :available_bikes,
                    :available_bike_stands, :status, :bike_stands,
                    :bonus, :banking, :position, :address,
                    :name, :last_update)
                ''' % (self.TableNameNew, ContractsDAO.TableName), json)
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while inserting state")

    def moveNewSamplesIntoOld(self):
        try:
            self._database.connection.execute(
                '''INSERT OR REPLACE INTO %s
                    SELECT * FROM %s
                ''' % (self.TableNameOld, self.TableNameNew))
            self._database.connection.execute(
                '''DELETE FROM %s
                ''' % self.TableNameNew)
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error moving new samples into old")

# stored sample DAO
class ShortSamplesDAO:

    TableNameChanged = "changed_samples"
    TableNameArchive = "archived_samples"

    def __init__(self, database):
        self._database = database

    def _createTable(self, db, tableName):
        try:
            db.connection.execute(
                '''CREATE TABLE %s(
                timestamp INTEGER NOT NULL,
                contract_id INTEGER NOT NULL,
                station_number INTEGR NOT NULL,
                available_bikes INTEGER NOT NULL,
                available_bike_stands INTEGER NOT NULL,
                PRIMARY KEY (contract_id, station_number)
                )''' % tableName)
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while creating table [%s]" % tableName)

    def createTableChanged(self):
        print "Creating table [%s]" % self.TableNameChanged
        self._createTable(self._database,self.TableNameChanged)

    def buildChangedSamples(self):
        try:
            self._database.connection.execute(
                '''DELETE FROM %s
                ''' % self.TableNameChanged)
            req = self._database.connection.execute(
                '''INSERT INTO %s
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
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error building changed samples")

    def getChangedStatistics(self):
        try:
            req = self._database.connection.execute(
                '''SELECT DATE(timestamp,'unixepoch') AS day,
                    COUNT(timestamp) as num_changed_samples
                    FROM %s
                    GROUP BY day
                    ORDER BY day ASC
                ''' % self.TableNameChanged)
            return req.fetchall()
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error getting changed date list")

    def getDateDbName(self, date):
        return "samples-%s.db" % date

    def initializeDateDb(self, date):
        dbname = self.getDateDbName(date)
        with SqliteDB(dbname) as storage_db:
            if not storage_db.hasTable(self.TableNameArchive):
                self._createTable(storage_db,self.TableNameArchive)
                return True
        return False

# access jcdecaux web api
class ApiAccess:

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
            raise JcdException("JCDecaux API exception: %s" % reply_json["error"])
        return reply_json

    def _get(self, sub_url, payload = {}):
        # add the api key to the call
        payload["apiKey"] = self._apikey
        url = "%s/%s" % (self.BaseUrl, sub_url)
        headers = { "Accept": "application/json" }
        try:
            r = requests.get(url, params=payload, headers=headers)
            # avoid ultra-slow character set auto-detection
            # see https://github.com/kennethreitz/requests/issues/2359
            r.encoding = "utf-8"
            # check for api error
            return self._parseReply(r.text)
        except requests.exceptions.RequestException as e:
            raise JcdException("JCDecaux Requests exception: (%s) %s" % (type(e).__name__, e))

    def getStations(self):
        return self._get("stations")

    def getContractStation(self,contract_name,station_id):
        return self._get("stations/%i" % station_id, {"contract": contract_name})

    def getContractStations(self,contract_name):
        return self._get("stations", {"contract": contract_name})

    def getContracts(self):
        return self._get("contracts")

# initialize application data
class InitCmd:

    def __init__(self, args):
        self._args = args

    def _removeFolder(self):
        # delete the folder
        try:
            print "Removing folder [%s] and its content" % App.DataPath
            shutil.rmtree(App.DataPath)
        except OSError as e:
            # silently ignore "absent directory"
            if e.errno == errno.ENOENT:
                return
            # on other errors
            raise JcdException("Could not remove folder : %s" % e)

    def _createFolder(self):
        try:
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
        with SqliteDB(App.DbName) as db:
            settings = SettingsDAO(db)
            settings.createTable()
            contracts = ContractsDAO(db)
            contracts.createTable()
            full_samples = FullSamplesDAO(db)
            full_samples.createTables()
            short_samples = ShortSamplesDAO(db)
            short_samples.createTableChanged()

    # set default parameters
    def setDefaultParameters(self):
        with SqliteDB(App.DbName) as db:
            settings = SettingsDAO(db)
            for value in ConfigCmd.Parameters:
                if value[3] is not None:
                    print "Setting parameter [%s] to default value [%s]" % (value[0],value[3])
                    settings.setParameter(value[0], value[3])
            # if all went well
            db.commit()

    def run(self):
        # remove folder if creation is forced
        if self._args.force:
            self._removeFolder()
        self._createFolder()
        # create tables in data db
        self._createTables()
        self.setDefaultParameters()

# configure settings:
class ConfigCmd:

    Parameters = (
        ('apikey', str, 'JCDecaux API key', None),
        ('fetch', int, 'Enable/disable fetch operation', 0),
        ('import', int, 'Enable/disable import operation', 0),
    )

    def __init__(self, args):
        self._args = args

    def displayParam(self,param):
        with SqliteDB(App.DbName) as db:
            settings = SettingsDAO(db)
            (value, last_modification) = settings.getParameter(param)
            print "%s = %s (last modified on %s)" % (param, value, last_modification)

    def updateParam(self,param,value):
        with SqliteDB(App.DbName) as db:
            settings = SettingsDAO(db)
            settings.setParameter(param,value)
            # if all went well
            db.commit()
            print "Setting %s = %s" % (param,value)

    def run(self):
        # modify each fully provided parameter
        has_modified = False
        args_dict = self._args.__dict__
        for value in ConfigCmd.Parameters:
            param = value[0]
            if param in args_dict:
                value = args_dict[param]
                if value is not None:
                    self.updateParam(param,value)
                    has_modified = True
        # if nothing was provided, display all current parameter value
        if not has_modified:
            for value in self.Parameters:
                self.displayParam(value[0])

# administration
class AdminCmd:

    Parameters = (
        ('vacuum', 'defragment and trim sqlite database'),
        ('apitest', 'test JCDecaux API access'),
    )

    def __init__(self, args):
        self._args = args

    def vacuum(self):
        print "Vacuuming SqliteDB"
        with SqliteDB(App.DbName) as db:
            db.vacuum()

    def apitest(self):
        print "Testing JCDecaux API access"
        with SqliteDB(App.DbName) as db:
            # fetch api key
            settings = SettingsDAO(db)
            apikey, last_modified = settings.getParameter("apikey")
            if apikey is None:
                raise JcdException(
                    "API key is not set ! "
                    "Please configure using 'config --apikey'")
            # real testing
            api = ApiAccess(apikey)
            # get all available contracts
            print "Searching contracts ..."
            contracts = api.getContracts()
            c = len(contracts)
            print "Found %i contracts." % c
            # get a random contract
            r = random.randint(0,c-1)
            contract = contracts[r]
            cn = contract["name"]
            print "Fetching stations contract [%s] ..." % cn
            stations = api.getContractStations(cn)
            c = len(stations)
            print "Found %i stations." % c
            # get a random contract
            r = random.randint(0,c-1)
            station = stations[r]
            sn = station["number"]
            print "Fetching a single station [%i] of contract [%s] ..." % (sn,cn)
            station = api.getContractStation(cn,sn)
            print "Station name is [%s]" % station["name"]
            # test OK
            print "API TEST SUCCESS"

    def run(self):
        args_dict = self._args.__dict__
        for param in AdminCmd.Parameters:
            name = param[0]
            if name in args_dict:
                value = args_dict[name]
                if type(value) == bool and value:
                    f = getattr(self, name)
                    f()

# fetch information from api:
class FetchCmd:

    def __init__(self, args):
        self._args = args

    def _fetchContracts(self):
        with SqliteDB(App.DbName) as db:
            # fetch api key
            settings = SettingsDAO(db)
            apikey, last_modified = settings.getParameter("apikey")
            if apikey is None:
                raise JcdException(
                    "API key is not set ! "
                    "Please configure using 'config --apikey'")
            # get all available contracts
            api = ApiAccess(apikey)
            json = api.getContracts()
            dao = ContractsDAO(db)
            new_contracts_count = dao.storeContracts(json)
            # if everything went fine
            db.commit()
            if new_contracts_count > 0 and self._args.verbose:
                print "New contracts added: %i" % new_contracts_count

    def _fetchState(self):
        with SqliteDB(App.DbName) as db:
            # fetch api key
            settings = SettingsDAO(db)
            apikey, last_modified = settings.getParameter("apikey")
            if apikey is None:
                raise JcdException(
                    "API key is not set ! "
                    "Please configure using 'config --apikey'")
            # get all station states
            api = ApiAccess(apikey)
            json = api.getStations()
            dao = FullSamplesDAO(db)
            dao.storeNewSamples(json)
            # if everything went fine
            db.commit()

    def run(self):
        if self._args.contracts:
            self._fetchContracts()
        if self._args.state:
            self._fetchState()

# store state into database:
class StoreCmd:

    def __init__(self, args):
        self._args = args

    def run(self):
        with SqliteDB(App.DbName) as db:
            # analyse changes
            short_dao = ShortSamplesDAO(db)
            num_changed_samples = short_dao.buildChangedSamples()
            # prepare archive storage if needed
            stats = short_dao.getChangedStatistics()
            for date, count in stats:
                created = short_dao.initializeDateDb(date)
                if created and self._args.verbose:
                    print "Creating archive database for date [%s]" % date
            # TODO: attach date databases to main databases
            # TODO: move samples around
            # cleanup and do age samples
            full_dao = FullSamplesDAO(db)
            full_dao.moveNewSamplesIntoOld()
            # if everything went fine
            db.commit()
            if num_changed_samples > 0 and self._args.verbose:
                print "Changed samples: %i" % num_changed_samples

# main app
class App:

    DataPath = None
    DbName = None

    def __init__(self, default_data_path, default_app_dbname):
        # store data path
        self._default_data_path = default_data_path
        # store main dbname
        self._default_app_dbname = default_app_dbname
        # top parser
        self._parser = argparse.ArgumentParser(description = 'Fetch and store JCDecaux API results')
        # top level argument for data destination
        self._parser.add_argument(
            '--datadir',
            help = 'choose data folder (default: %s)' % default_data_path,
            default = default_data_path
        )
        self._parser.add_argument(
            '--dbname',
            help = 'choose db filename (default: %s)' % default_app_dbname,
            default = default_app_dbname
        )
        self._parser.add_argument(
            '--verbose', '-v',
            action = 'store_true',
            help = 'display operationnal informations'
        )
        # top level commands
        top_command = self._parser.add_subparsers(dest='command')
        # init command
        init = top_command.add_parser(
            'init',
            help = 'create application files',
            description = 'Initialize application'
        )
        init.add_argument(
            '--force', '-f',
            action = 'store_true',
            help = 'overwrite existing files'
        )
        # config command
        config = top_command.add_parser(
            'config',
            help = 'config application parameters',
            description = 'Configure application'
        )
        for value in ConfigCmd.Parameters:
            config.add_argument(
                '--%s' % value[0],
                type = value[1],
                help = value[2],
            )
        # admin command
        admin = top_command.add_parser(
            'admin',
            help = 'administrate application database',
            description = 'Manage database'
        )
        for value in AdminCmd.Parameters:
            admin.add_argument(
                '--%s' % value[0],
                action = 'store_true',
                help = value[1],
            )
        # fetch command
        fetch = top_command.add_parser(
            'fetch',
            help = 'get information from the API',
            description = 'Get from API'
        )
        fetch.add_argument(
            '--contracts', '-c',
            action = 'store_true',
            help = 'get contracts'
        )
        fetch.add_argument(
            '--state', '-s',
            action = 'store_true',
            help = 'get current state'
        )
        # store command
        store = top_command.add_parser(
            'store',
            help = 'store fetched state into database',
            description = 'Store state in database'
        )

    def run(self):
        try:
            # parse arguments
            args = self._parser.parse_args()
            # consume data-path argument
            App.DataPath = os.path.expanduser(args.datadir)
            # consume db name argument
            App.DbName = os.path.expanduser(args.dbname)
            del args.dbname
            # consume command
            command = getattr(self, args.command)
            del args.command
            # run requested command
            command(args)
        except JcdException as e:
            print e
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
    app = App("~/.jcd","app.db")
    try:
        app.run()
    except KeyboardInterrupt:
        pass
