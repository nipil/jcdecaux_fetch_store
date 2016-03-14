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

import sqlite3

import jcd.common
import jcd.app
import jcd.cmd

# settings table
class SettingsDAO(object):

    TableName = "settings"

    def __init__(self, database):
        self._database = database

    def create_table(self):
        if jcd.app.App.Verbose:
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
            raise jcd.common.JcdException(
                "Database error while creating table [%s]" % self.TableName)

    def set_parameter(self, name, value):
        try:
            self._database.connection.execute(
                '''
                INSERT OR REPLACE INTO %s (name, value, last_modification)
                VALUES (?, ?, strftime('%%s', 'now'))
                ''' % self.TableName, (name, value))
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException(
                "Database error while setting parameter [%s]" % name)

    def get_parameter(self, name):
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
            raise jcd.common.JcdException(
                "Database error while fetching parameter [%s]" % name)

# contract table
class ContractsDAO(object):

    TableName = "contracts"

    def __init__(self, database):
        self._database = database

    def create_table(self):
        if jcd.app.App.Verbose:
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
            raise jcd.common.JcdException(
                "Database error while creating table [%s]" % self.TableName)

    def store_contracts(self, json_content, timestamp):
        # merge cities together
        for contract in json_content:
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
                ''' % self.TableName, json_content)
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
                ''' % self.TableName, json_content)
            # return number of inserted records
            return req.rowcount
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException("Database error while inserting contracts")

    def is_refresh_needed(self):
        try:
            req = self._database.connection.execute(
                '''
                SELECT STRFTIME('%s','now') - MAX(timestamp) > value
                FROM contracts, settings
                WHERE name = ?
                ''', (jcd.cmd.ConfigCmd.Parameters[1][0],))
            result = req.fetchone()
            # if no contract, None
            # if latest refresh is too old, 1
            return result[0] is None or result[0] == 1
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException("Database error while checking contracts refresh")

# settings table
class FullSamplesDAO(object):

    TableNameNew = "new_samples"
    TableNameOld = "old_samples"

    def __init__(self, database):
        self._database = database

    def create_tables(self):
        self._create_table(self.TableNameNew)
        self._create_table(self.TableNameOld)

    def _create_table(self, table_name):
        if jcd.app.App.Verbose:
            print "Creating table [%s]" % table_name
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
                ''' % table_name)
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException(
                "Database error while creating table [%s]" % table_name)

    def store_new_samples(self, json_content, timestamp):
        # adapt json_content to database schema
        for station in json_content:
            station["timestamp"] = timestamp
            station["status"] = 1 if station["status"] == "OPEN" else 0
            station["bonus"] = 1 if station["bonus"] else 0
            station["banking"] = 1 if station["banking"] else 0
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
                ''' % (self.TableNameNew, ContractsDAO.TableName), json_content)
            # return number of inserted records
            return req.rowcount
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException("Database error while inserting state")

    def age_samples(self, date):
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
                raise jcd.common.JcdException(
                    "Ageing operation failed (%i inserted, %i deleted)" % (
                        inserted, deleted))
            # return aged number of records
            return inserted
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException("Database error ageing new samples into old")

# stored sample DAO
class ShortSamplesDAO(object):

    TableNameChanged = "changed_samples"
    TableNameArchive = "archived_samples"

    def __init__(self, database):
        self._database = database

    @staticmethod
    def _create_table(database, table_name):
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
                ''' % table_name)
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException(
                "Database error while creating table [%s]" % table_name)

    def create_changed_table(self):
        if jcd.app.App.Verbose:
            print "Creating table [%s]" % self.TableNameChanged
        self._create_table(self._database, self.TableNameChanged)

    def find_changed_samples(self):
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
            raise jcd.common.JcdException("Database error building changed samples")

    def get_changed_samples_stats(self):
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
            raise jcd.common.JcdException("Database error getting changed date list")

    @staticmethod
    def get_schema_name(date):
        return "samples_%s" % date.replace("-", "_")

    @staticmethod
    def get_db_file_name(schema_name):
        return "%s.db" % schema_name

    def initialize_archived_table(self, dbfilename):
        with jcd.common.SqliteDB(dbfilename, jcd.app.App.DataPath) as storage_db:
            if not storage_db.has_table(self.TableNameArchive):
                self._create_table(storage_db, self.TableNameArchive)
                return True
        return False

    def archive_changed_samples(self, date, target_schema):
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
                raise jcd.common.JcdException(
                    "Archive operation failed (%i inserted, %i deleted)" % (
                        inserted, deleted))
            # return number of archived records
            return inserted
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException(
                "Database error achiving changed samples to %s" % target_schema)

    def get_changed_count(self):
        return self._database.get_count(self.TableNameChanged)

    def get_overall_earliest_timestamp(self, target_schema):
        try:
            req = self._database.connection.execute(
                '''
                SELECT MIN(timestamp)
                FROM %s.%s
                ''' % (target_schema, self.TableNameArchive))
            result = req.fetchone()
            return result[0]
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException("Database error getting earliest sample")

    def insert_samples(self, samples, target_schema):
        # do not do anything if nothing is to be done
        if len(samples) == 0:
            return
        try:
            # add samples
            req = self._database.connection.executemany(
                '''
                INSERT INTO %s.%s (
                    timestamp,
                    contract_id,
                    station_number,
                    available_bikes,
                    available_bike_stands)
                VALUES (?, ?, ?, ?, ?)
                ''' % (target_schema, self.TableNameArchive), (samples))
            # verify insertion
            if len(samples) != req.rowcount:
                raise jcd.common.JcdException(
                    "Stored only %i of %i samples to target database" % (
                        req.rowcount, len(samples)))
            # return number of inserted records
            return req.rowcount
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException(
                "Database error while inserting %i samples into %s.%s" % (
                    len(samples), target_schema, self.TableNameArchive))

# stored sample DAO
class Version1Dao(object):

    TableName = "samples"
    SchemaName = "version1"

    def __init__(self, database):
        self._database = database

    def has_sample_table(self):
        return self._database.has_table(self.TableName, self.SchemaName)

    def list_samples(self):
        # do the query
        try:
            req = self._database.connection.execute(
                '''
                SELECT s.timestamp,
                    date(s.timestamp,'unixepoch'),
                    c.contract_id,
                    s.station_number,
                    s.bike,
                    s.empty
                FROM %s AS c JOIN %s.%s AS s
                ON c.contract_name = s.contract_name
                ''' % (ContractsDAO.TableName,
                       self.SchemaName,
                       self.TableName))
            while True:
                samples = req.fetchmany(1000)
                if not samples:
                    break
                for sample in samples:
                    yield sample
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException(
                "Database error listing all samples in version 1 data")
