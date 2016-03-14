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
        self.connection = None
        self._att_databases = {}

    @staticmethod
    def get_full_path(filename, path):
        return os.path.normpath(os.path.expanduser(
            "%s/%s" % (path, filename)))

    def open(self):
        if self.connection is None:
            try:
                self.connection = sqlite3.connect(self._full_path)
            except sqlite3.Error as error:
                print "%s: %s" % (type(error).__name__, error)
                raise JcdException(
                    "Database error while opening [%s]" % self._full_path)

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

    def has_table(self, name, schema="main"):
        try:
            req = self.connection.execute(
                '''
                SELECT count(*), name
                FROM %s.sqlite_master
                WHERE type = "table" AND name = ?
                ''' % schema, (name, ))
            count, name = req.fetchone()
            return count != 0
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error checking if table [%s] exists" % name)

    def attach_database(self, file_name, schema_name, path):
        file_path = SqliteDB.get_full_path(file_name, path)
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

    def detach_database(self, schema_name):
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

    def get_count(self, target):
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

    def set_synchronous(self, schema_name, value):
        # see https://www.sqlite.org/pragma.html#pragma_synchronous
        try:
            self.connection.execute(
                '''
                PRAGMA %s.synchronous=%i
                ''' % (schema_name, value))
        except sqlite3.Error as error:
            print "%s: %s" % (type(error).__name__, error)
            raise JcdException(
                "Database error while setting synchronous pragma")
