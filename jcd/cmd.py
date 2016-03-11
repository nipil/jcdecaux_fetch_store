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

import csv
import sys
import time
import errno
import shutil
import random
import os.path
import collections

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
            shutil.rmtree(os.path.normpath(os.path.expanduser(
                jcd.app.App.DataPath)))
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
            os.makedirs(os.path.normpath(os.path.expanduser(
                jcd.app.App.DataPath)))
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

    DefaultFile = "jcd.sqlite3"
    DefaultPath = "~/.jcd"

    def __init__(self, args):
        self._args = args
        self._app_db = None
        self._short_dao = None
        self._contracts_dao = None
        self._dao_v1 = None
        self._f_date_str = None
        self._f_contract_id = None
        self._f_station_number = None
        self._f_earliest_timestamp = None
        self._daily_schema_name = None
        self._last_sample = None
        self._kept_samples = None
        self._n_worked = None
        self._n_stored = None
        self._data = dict()

    def _initialize(self):
        # prepare the dao for version 2 archived samples
        self._short_dao = jcd.dao.ShortSamplesDAO(self._app_db)

        # prepare the dao for version 2 contracts
        self._contracts_dao = jcd.dao.ContractsDAO(self._app_db)

        # modify synchronization for main db
        self._app_db.set_synchronous("main", self._args.sync)

        # attach version 1 database
        self._app_db.attach_database(self.DefaultFile,
            jcd.dao.Version1Dao.SchemaName, self._args.source)

        # modify synchronization for version 1 db
        self._app_db.set_synchronous(jcd.dao.Version1Dao.SchemaName, self._args.sync)

        # check for version 1 data
        self._dao_v1 = jcd.dao.Version1Dao(self._app_db)
        if not self._dao_v1.has_sample_table():
            raise jcd.app.JcdException(
                "Version 1 database is missing its sample table")

    def _get_first_sample(self):
        # search for data to import
        samples = self._dao_v1.find_samples_filter(None, None, None, None, 1)
        return next(samples, None)

    def _attach_v2_daily_db(self):
        # create, initialize databases as necessary
        self._daily_schema_name = self._short_dao.get_schema_name(self._f_date_str)
        db_filename = self._short_dao.get_db_file_name(self._daily_schema_name)
        # prepare archive storage if needed
        created = self._short_dao.initialize_archived_table(db_filename)
        if created:
            print "Database", db_filename, "created"
        # WARNING: attaching commits current transaction
        self._app_db.attach_database(db_filename, self._daily_schema_name)
        # modify synchronization for version 1 db
        self._app_db.set_synchronous(self._daily_schema_name, self._args.sync)

    def _detach_v2_daily_db(self):
        # WARNING: detaching commits current transaction
        self._app_db.detach_database(self._daily_schema_name)

    def _find_earliest_target_sample(self):
        # getting earliest available sample from target database
        self._f_earliest_timestamp = self._short_dao.get_earliest_timestamp(
            self._daily_schema_name,
            self._f_contract_id,
            self._f_station_number)

    def _is_sample_changed(self, current_sample):
        return (self._last_sample[3] != current_sample[3] or
            self._last_sample[4] != current_sample[4])

    def _store_kept_samples(self):
        # store samples
        self._short_dao.insert_samples(
            self._kept_samples, self._daily_schema_name)
        # count samples as stored
        self._n_stored += len(self._kept_samples)
        # clear samples buffer
        self._kept_samples.clear()

    def _import_target_samples(self):
        # search for data to import
        samples = self._dao_v1.find_samples_filter(
            self._f_date_str,
            self._f_contract_id,
            self._f_station_number,
            self._f_earliest_timestamp,
            None)

        # check if there is any actual data
        self._last_sample = next(samples, None)
        if self._last_sample is None:
            return 0
        else:
            # count sample as worked
            self._n_worked += 1

        # there is some, do the deduplication
        self._kept_samples = collections.deque()
        self._kept_samples.append(self._last_sample)
        for sample in samples:
            # count sample as worked
            self._n_worked += 1
            # check for change
            if self._is_sample_changed(sample):
                self._kept_samples.append(sample)
                self._last_sample = sample
            # periodically store into target db
            if len(self._kept_samples) > 1000:
                self._store_kept_samples()
        # store remaining samples
        self._store_kept_samples()

    def _remove_imported_source_samples(self):
        contract_name = self._contracts_dao.get_contract_name(self._f_contract_id)
        self._dao_v1.remove_samples(
            self._f_date_str,
            contract_name,
            self._f_station_number)

    def _work(self, target_sample):
        # extract working data
        self._f_date_str = self._app_db.get_date_from_timestamp(target_sample[0])
        self._f_contract_id = target_sample[1]
        self._f_station_number = target_sample[2]
        print "Processing contract %i station %i date %s..." %(
            self._f_contract_id,
            self._f_station_number,
            self._f_date_str),

        # reset stats
        self._n_worked = 0
        self._n_stored = 0

        # attach target database
        self._attach_v2_daily_db()

        # find maximum target timestamp, to limit import
        self._find_earliest_target_sample()

        # actually import samples
        self._import_target_samples()

        # remove imported samples from v1 db
        self._remove_imported_source_samples()

        # display statistics
        print "Committing. Stored", self._n_stored, "and removed", self._n_worked

        # commit transaction
        self._app_db.commit()

        # detach target daily db
        self._detach_v2_daily_db()

    def run_old(self):
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            self._app_db = app_db
            self._initialize()
            while True:
                sample = self._get_first_sample()
                if sample is None:
                    print "No sample found"
                    break
                self._work(sample)

    @staticmethod
    def _get_csv_name(date_str):
        return '%s.csv' % date_str

    @staticmethod
    def _remove_csv_file(date_str):
        filename = Import1Cmd._get_csv_name(date_str)
        try:
            os.remove(filename)
        except OSError as error:
            if error.errno != errno.ENOENT:
                raise

    @staticmethod
    def _flush_samples(date_str, data):
        filename = Import1Cmd._get_csv_name(date_str)
        with open(filename, 'ab') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(data)
            data.clear()

    def _flush_all(self):
        for date_str, date_info in self._data.iteritems():
            self._flush_samples(date_str, date_info["kept"])

    def _work_sample(self, sample_raw):
        # manage dates
        timestamp = sample_raw[0]
        date_str = sample_raw[1]
        contract_id = sample_raw[2]
        station_number = sample_raw[3]
        bikes = sample_raw[4]
        slots = sample_raw[5]
        sample = timestamp, contract_id, station_number, bikes, slots

        # manage structure
        if date_str not in self._data:
            self._data[date_str] = {
                "kept": collections.deque(),
                "created": False,
                "contracts": dict()
            }
        date_info = self._data[date_str]

        # flush samples if required
        kept = date_info["kept"]
        if len(kept) >= 1000:
            if not date_info["created"]:
                self._remove_csv_file(date_str)
                date_info["created"] = True
            self._flush_samples(date_str, kept)

        # manage contracts
        contracts = date_info["contracts"]
        if contract_id not in contracts:
            # will contain all stations by number
            contracts[contract_id] = {
                "stations": dict()
            }
        contract_info = contracts[contract_id]

        # manage stations
        stations = contract_info["stations"]
        if station_number not in stations:
            stations[station_number] = {
                "last": None
            }
        station_info = stations[station_number]

        # manage first sample
        last = station_info["last"]
        if last is None:
            date_info["kept"].append(sample)
            station_info["last"] = sample
            return

        # compare bikes and slots with previous sample
        if last[3] != bikes or last[4] != slots:
            date_info["kept"].append(sample)
            station_info["last"] = sample
            return

        # if same, skip
        return

    def _extract_deduplicate_data(self):
        n = 0
        t = 0
        for sample in self._dao_v1.list_samples():
            n += 1
            t += 1
            self._work_sample(sample)
            if t > 1000:
                t = 0
                sys.stdout.write(".")
                sys.stdout.flush()
        self._flush_all()

    def run(self):
        with jcd.app.SqliteDB(jcd.app.App.DbName) as app_db:
            self._app_db = app_db
            self._initialize()
            self._extract_deduplicate_data()
