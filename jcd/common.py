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

import os.path
import sqlite3

import jcd.cmd

# applications specific exception
class JcdException(Exception):

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

# manages access to the application database
class SqliteDB(object):

    def __init__(self, db_filename, data_path):
        self._data_path = data_path
        self._file_name = db_filename
        self._full_path = SqliteDB.get_full_path(self._file_name, self._data_path)
        self._connection = None
        self._att_databases = {}

    @staticmethod
    def get_full_path(filename, path):
        return os.path.normpath(os.path.expanduser(
            "%s/%s" % (path, filename)))

    def open(self):
        if self._connection is None:
            try:
                self._connection = sqlite3.connect(self._full_path)
                self._connection.row_factory = sqlite3.Row
            except sqlite3.Error as error:
                print "%s: %s" % (type(error).__name__, error)
                raise JcdException(
                    "Database error while opening [%s]" % self._full_path)

    def close(self):
        # close main databases
        if self._connection is not None:
            self._connection.close()
        self._connection = None

    def commit(self):
        if self._connection is not None:
            self._connection.commit()

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
        if self._connection is not None:
            self._connection.execute("vacuum")

    def has_table(self, name, schema="main"):
        result = self.execute_fetch_one(
            '''
            SELECT COUNT(*), name
            FROM %s.sqlite_master
            WHERE type = "table" AND name = ?
            ''' % schema,
            (name, ),
            "Database error checking if table [%s] exists" % name)
        return result[0] != 0

    def attach_database(self, file_name, schema_name, path, must_exist=False):
        file_path = SqliteDB.get_full_path(file_name, path)
        if must_exist and not os.path.exists(file_path):
            raise JcdException("Database [%s] does not exist" % file_name)
        if schema_name in self._att_databases:
            raise JcdException(
                "Database is already attached as schema [%s]" % schema_name)
        self.execute_single(
            '''
            ATTACH DATABASE ? AS ?
            ''',
            (file_path, schema_name),
            "Database error while attaching [%s] as schema [%s]" % (file_name, schema_name))
        # memorize attachement
        self._att_databases[schema_name] = file_name

    def detach_database(self, schema_name):
        if schema_name not in self._att_databases:
            raise JcdException(
                "Schema [%s] is not attached" % schema_name)
        self.execute_single(
            '''
            DETACH DATABASE ?
            ''',
            (schema_name, ),
            "Database error while detaching [%s]" % schema_name)
        del self._att_databases[schema_name]

    def get_count(self, target):
        result = self.execute_fetch_one(
            '''
            SELECT COUNT(*) FROM %s
            ''' % target,
            None,
            "Database error while getting rowcount for [%s]" % target)
        return result[0]

    def set_synchronous(self, schema_name, value):
        # see https://www.sqlite.org/pragma.html#pragma_synchronous
        self.execute_single(
            '''
            PRAGMA %s.synchronous=%i
            ''' % (schema_name, value),
            None,
            "Database error while setting synchronous pragma")

    def execute_single(self, sql, params=None, error_message=None):
        try:
            req = None
            if params is None:
                req = self._connection.execute(sql)
            else:
                req = self._connection.execute(sql, params)
            return req.rowcount
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            if error_message is None:
                raise jcd.common.JcdException(
                    "Database error while executing [%s] using [%s]" % (sql, params))
            else:
                raise jcd.common.JcdException(error_message)

    def execute_many(self, sql, params, error_message=None):
        try:
            req = None
            req = self._connection.executemany(sql, params)
            return req.rowcount
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            if error_message is None:
                raise jcd.common.JcdException(
                    "Database error while executing [%s] using [%s]" % (sql, params))
            else:
                raise jcd.common.JcdException(error_message)

    def execute_fetch_one(self, sql, params=None, error_message=None):
        try:
            req = None
            if params is None:
                req = self._connection.execute(sql)
            else:
                req = self._connection.execute(sql, params)
            return req.fetchone()
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            if error_message is None:
                raise jcd.common.JcdException(
                    "Database error while executing [%s] using [%s]" % (sql, params))
            else:
                raise jcd.common.JcdException(error_message)

    def execute_fetch_generator(self, sql, params=None, error_message=None, as_dict=False):
        try:
            req = None
            if params is None:
                req = self._connection.execute(sql)
            else:
                req = self._connection.execute(sql, params)
            while True:
                items = req.fetchmany(1000)
                if not items:
                    break
                for item in items:
                    if as_dict:
                        yield dict(zip(item.keys(), item))
                    else:
                        yield item
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            if error_message is None:
                raise jcd.common.JcdException(
                    "Database error while executing [%s] using [%s]" % (sql, params))
            else:
                raise jcd.common.JcdException(error_message)
