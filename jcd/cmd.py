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

import time
import errno
import shutil
import random
import os.path

import jcd.app
import jcd.dao

# initialize application data
class InitCmd(object):

    def __init__(self, args):
        self._args = args

    @staticmethod
    def _remove_data_folder():
        # delete the folder
        try:
            if jcd.app.App.Verbose:
                print "Removing folder [%s] and its content" % jcd.app.App.DataPath
            shutil.rmtree(jcd.app.App.DataPath)
        except OSError as error:
            # silently ignore "absent directory"
            if error.errno == errno.ENOENT:
                return
            # on other errors
            raise jcd.app.JcdException("Could not remove folder : %s" % error)

    @staticmethod
    def _create_data_folder():
        try:
            if jcd.app.App.Verbose:
                print "Creating folder [%s]" % jcd.app.App.DataPath
            os.makedirs(jcd.app.App.DataPath)
        except OSError as exception:
            # folder exists
            if exception.errno == errno.EEXIST:
                raise jcd.app.JcdException(
                    "Folder [%s] already exists. Use --force "
                    "to destroy everything anyway." % jcd.app.App.DataPath)
            # other system error
            raise

    @staticmethod
    def _create_tables():
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            settings = jcd.dao.SettingsDAO(app_db)
            settings.create_table()
            contracts = jcd.dao.ContractsDAO(app_db)
            contracts.create_table()
            full_samples = jcd.dao.FullSamplesDAO(app_db)
            full_samples.create_tables()
            short_samples = jcd.dao.ShortSamplesDAO(app_db)
            short_samples.create_changed_table()

    @staticmethod
    def set_default_parameters():
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            settings = jcd.dao.SettingsDAO(app_db)
            for value in ConfigCmd.Parameters:
                if jcd.app.App.Verbose and value[3] is not None:
                    print "Setting parameter [%s] to default value [%s]" % (
                        value[0], value[3])
                    settings.set_parameter(value[0], value[3])
            # if all went well
            app_db.commit()

    def run(self):
        # remove folder if creation is forced
        if self._args.force:
            self._remove_data_folder()
        self._create_data_folder()
        # create tables in data db
        self._create_tables()
        self.set_default_parameters()

# configure settings:
class ConfigCmd(object):

    Parameters = (
        ('apikey', str, 'JCDecaux API key', None),
        ('contract_ttl', int, 'contracts refresh interval in seconds', 3600),
    )

    def __init__(self, args):
        self._args = args

    @staticmethod
    def display_parameter(param):
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            settings = jcd.dao.SettingsDAO(app_db)
            (value, last_modification) = settings.get_parameter(param)
            # don't check for verbose, display is mandatory
            print "%s = %s (last modified on %s)" % (
                param, value, last_modification)

    @staticmethod
    def update_parameter(param, value):
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            settings = jcd.dao.SettingsDAO(app_db)
            settings.set_parameter(param, value)
            # if all went well
            app_db.commit()
            if jcd.app.App.Verbose:
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
                    self.update_parameter(param, value)
                    has_modified = True
        # if nothing was provided, display all current parameter value
        if not has_modified:
            for value in self.Parameters:
                self.display_parameter(value[0])

# administration
class AdminCmd(object):

    Parameters = (
        ('vacuum', 'defragment and trim sqlite database'),
        ('apitest', 'test JCDecaux API access'),
    )

    def __init__(self, args):
        self._args = args

    @staticmethod
    def vacuum():
        if jcd.app.App.Verbose:
            print "Vacuuming %s" % jcd.app.App.DbName
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            app_db.vacuum()

    @staticmethod
    def apitest():
        if jcd.app.App.Verbose:
            print "Testing JCDecaux API access"
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            # fetch api key
            settings = jcd.dao.SettingsDAO(app_db)
            apikey = settings.get_parameter("apikey")
            if apikey is None:
                raise jcd.app.JcdException(
                    "API key is not set ! "
                    "Please configure using 'config --apikey'")
            # real testing
            api = jcd.app.ApiAccess(apikey)
            # get all available contracts
            if jcd.app.App.Verbose:
                print "Searching contracts ..."
            contracts = api.get_contracts()
            count = len(contracts)
            if jcd.app.App.Verbose:
                print "Found %i contracts." % count
            # get a random contract
            rnd = random.randint(0, count-1)
            contract = contracts[rnd]
            if jcd.app.App.Verbose:
                print "Fetching stations contract [%s] ..." % contract["name"]
            stations = api.get_contract_stations(contract["name"])
            count = len(stations)
            if jcd.app.App.Verbose:
                print "Found %i stations." % count
            # get a random contract
            rnd = random.randint(0, count-1)
            station = stations[rnd]
            if jcd.app.App.Verbose:
                print "Fetching a single station [%i] of contract [%s] ..." % (
                    station["number"], contract["name"])
            station = api.get_contract_station(
                contract["name"], station["number"])
            if jcd.app.App.Verbose:
                print "Station name is [%s]" % station["name"]
            # test OK
            if jcd.app.App.Verbose:
                print "API TEST SUCCESS"

    def run(self):
        args_dict = self._args.__dict__
        for param in AdminCmd.Parameters:
            name = param[0]
            if name in args_dict:
                value = args_dict[name]
                if isinstance(value, bool) and value:
                    function = getattr(self, name)
                    function()

# fetch information from api:
class FetchCmd(object):

    def __init__(self, args, check_contracts_ttl=False):
        self._args = args
        self._check_contracts_ttl = check_contracts_ttl
        self._timestamp = int(time.time())

    def fetch_contracts(self):
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            settings = jcd.dao.SettingsDAO(app_db)
            dao = jcd.dao.ContractsDAO(app_db)
            # in case of cron, check for refresh necessity
            if self._check_contracts_ttl and not dao.is_refresh_needed():
                return
            # fetch api key
            apikey = settings.get_parameter("apikey")
            if apikey is None:
                raise jcd.app.JcdException(
                    "API key is not set ! "
                    "Please configure using 'config --apikey'")
            # get all available contracts
            api = jcd.app.ApiAccess(apikey)
            json_contracts = api.get_contracts()
            new_contracts_count = dao.store_contracts(
                json_contracts, self._timestamp)
            # if everything went fine
            app_db.commit()
            if jcd.app.App.Verbose:
                print "New contracts added: %i" % new_contracts_count

    def fetch_state(self):
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            settings = jcd.dao.SettingsDAO(app_db)
            full_dao = jcd.dao.FullSamplesDAO(app_db)
            short_dao = jcd.dao.ShortSamplesDAO(app_db)
            # fetch api key
            apikey = settings.get_parameter("apikey")
            if apikey is None:
                raise jcd.app.JcdException(
                    "API key is not set ! "
                    "Please configure using 'config --apikey'")
            # get all station states
            api = jcd.app.ApiAccess(apikey)
            json_stations = api.get_all_stations()
            num_new = full_dao.store_new_samples(json_stations, self._timestamp)
            if jcd.app.App.Verbose:
                print "New samples acquired: %i" % num_new
            # analyse changes
            num_changed = short_dao.find_changed_samples()
            if jcd.app.App.Verbose:
                print "Changed samples available for archive: %i" % num_changed
            # if everything went fine
            app_db.commit()

    def run(self):
        if self._args.contracts:
            self.fetch_contracts()
        if self._args.state:
            self.fetch_state()

# store state into database:
class StoreCmd(object):

    def __init__(self, args):
        self._args = args

    @staticmethod
    def run():
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            full_dao = jcd.dao.FullSamplesDAO(app_db)
            short_dao = jcd.dao.ShortSamplesDAO(app_db)
            # daily databases are used
            stats = short_dao.get_changed_samples_stats()
            for date, count in stats:
                # create, initialize databases as necessary
                schema_name = short_dao.get_schema_name(date)
                db_filename = short_dao.get_db_file_name(schema_name)
                # prepare archive storage if needed
                created = short_dao.initialize_archived_table(db_filename)
                if jcd.app.App.Verbose and created:
                    print "Database [%s] created" % db_filename
                # WARNING: attaching commits current transaction
                app_db.attach_database(db_filename, schema_name)
                # moving changed samples to attached db
                if jcd.app.App.Verbose:
                    print "Archiving %i changed samples into %s" % (
                        count, schema_name)
                # archive changed samples from date
                num_stored = short_dao.archive_changed_samples(
                    date, schema_name)
                if num_stored != count:
                    raise jcd.app.JcdException(
                        "Not all changed samples could be archived")
                # age new samples into old
                num_aged = full_dao.age_samples(date)
                if jcd.app.App.Verbose:
                    print "Aged %i samples for %s" % (num_aged, date)
                # if everything went fine for this date
                app_db.commit()
                # WARNING: detaching commits current transaction
                app_db.detach_database(schema_name)
            # verify nothing changed remains after processing
            # unchanged new are not aged, old holds last change
            remain_changed = short_dao.get_changed_count()
            if remain_changed > 0:
                raise jcd.app.JcdException(
                    "Unprocessed changes: %i" % remain_changed)

# store state into database:
class CronCmd(object):

    def __init__(self, args):
        self._args = args

    @staticmethod
    def run():
        from argparse import Namespace
        params = Namespace(state=True, contracts=True)
        fetch = FetchCmd(params, check_contracts_ttl=True)
        fetch.run()
        params = Namespace()
        store = StoreCmd(params)
        store.run()

# import data from version 1
class Import1Cmd(object):

    Parameters = (
        ('source', str, 'directory of version 1 data to import', "~/.jcd"),
    )

    def __init__(self, args):
        self._args = args

    def run(self):
        print self._args.source
