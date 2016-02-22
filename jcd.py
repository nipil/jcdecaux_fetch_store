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
class AppDB:

    FileName = "app.db"

    def __init__(self):
        self._db_path = os.path.normpath("%s/%s" % (App.DataPath,self.FileName))
        self.connection = None

    def open(self):
        if self.connection is None:
            self.connection = sqlite3.connect(self._db_path)

    def close(self):
        if self.connection is not None:
            self.connection.close()
        self.connection = None

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
                    name TEXT PRIMARY KEY,
                    value, -- no type, use affinity
                    last_modification INTEGER
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
            self._database.connection.commit()
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
                id INTEGER,
                name TEXT UNIQUE,
                commercial_name TEXT,
                country_code TEXT,
                cities TEXT,
                PRIMARY KEY (id)
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
                    WHERE name = :name
                ''' % self.TableName, json)
            # add possible new contracts
            req = self._database.connection.executemany(
                '''INSERT OR IGNORE INTO
                    %s(id,name,commercial_name,country_code,cities)
                    VALUES(NULL,:name,:commercial_name,:country_code,:cities)
                ''' % self.TableName, json)
            # notify if new contracts were added
            if req.rowcount > 0:
                print "New contracts added: %i" % req.rowcount
            # if everything went fine
            self._database.connection.commit()
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while inserting contract [%s]" % contract)

# settings table
class NewSamplesDAO:

    TableName = "new_samples"

    def __init__(self, database):
        self._database = database

    def createTable(self):
        print "Creating table [%s]" % self.TableName
        try:
            self._database.connection.execute(
                '''CREATE TABLE %s(
                contract_name STRING,
                station_number INT,
                age INTEGER,
                timestamp INTEGER,
                last_update INTEGER,
                bike INTEGER,
                empty INTEGER,
                status INTEGER,
                PRIMARY KEY (contract_name, station_number, age)
                )''' % self.TableName)
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while creating table [%s]" % self.TableName)

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
        with AppDB() as db:
            settings = SettingsDAO(db)
            settings.createTable()
            contracts = ContractsDAO(db)
            contracts.createTable()
            newSamples = NewSamplesDAO(db)
            newSamples.createTable()

    # set default parameters
    def setDefaultParameters(self):
        with AppDB() as db:
            settings = SettingsDAO(db)
            for value in ConfigCmd.Parameters:
                if value[3] is not None:
                    print "Setting parameter [%s] to default value [%s]" % (value[0],value[3])
                    settings.setParameter(value[0], value[3])

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
        with AppDB() as db:
            settings = SettingsDAO(db)
            (value, last_modification) = settings.getParameter(param)
            print "%s = %s (last modified on %s)" % (param, value, last_modification)

    def updateParam(self,param,value):
        with AppDB() as db:
            settings = SettingsDAO(db)
            settings.setParameter(param,value)
            print "Setting %s = %s" % (param,value)

    def run(self):
        # modify each fully provided parameter
        has_modified = False
        for param, value in self._args.__dict__.iteritems():
            if value is not None:
                self.updateParam(param,value)
                has_modified = True
        # if nothing was provided, display all current parameter value
        if not has_modified:
            for value in self.Parameters:
                self.displayParam(value[0])

# administration
class AdminCmd:

    def __init__(self, args):
        self._args = args

    def vacuum(self):
        print "Vacuuming AppDB"
        with AppDB() as db:
            db.vacuum()

    def apitest(self):
        print "Testing JCDecaux API access"
        with AppDB() as db:
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
        for param, value in self._args.__dict__.iteritems():
            f = getattr(self, param)
            if not value:
                continue
            if type(value) == bool:
                f()
            else:
                f(value)

# fetch information from api:
class FetchCmd:

    def __init__(self, args):
        self._args = args

    def _fetchContracts(self):
        with AppDB() as db:
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
            dao.storeContracts(json)

    def _fetchState(self):
        print "fetchState"

    def run(self):
        if self._args.contracts:
            self._fetchContracts()
        if self._args.state:
            self._fetchState()

# main app
class App:

    DataPath = None

    def __init__(self, default_data_path):
        # store data path
        self._default_data_path = default_data_path
        # top parser
        self._parser = argparse.ArgumentParser(description = 'Fetch and store JCDecaux API results')
        # top level argument for data destination
        self._parser.add_argument(
            '--datadir',
            help = 'choose data folder (default: %s)' % default_data_path,
            default = default_data_path
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
        admin.add_argument(
            '--vacuum',
            action = 'store_true',
            help = 'defragment and trim sqlite database',
        )
        admin.add_argument(
            '--apitest',
            action = 'store_true',
            help = 'test JCDecaux API access'
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

    def run(self):
        try:
            # parse arguments
            args = self._parser.parse_args()
            # consume data-path argument
            App.DataPath = os.path.expanduser(args.datadir)
            del args.datadir
            # consume command
            command = getattr(self, args.command)
            del args.command
            # run requested command
            command(args)
        except JcdException as e:
            print e

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

# main
if __name__ == '__main__':
    app = App("~/.jcd")
    try:
        app.run()
    except KeyboardInterrupt:
        pass
