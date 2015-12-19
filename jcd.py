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
import errno
import shutil
import os.path
import sqlite3
import argparse

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
                    value -- no type, use affinity
                )''' % self.TableName)
        except sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while creating table [%s]" % self.TableName)

# settings table
class ApiCacheDAO:

    TableName = "api_cache"

    def __init__(self, database):
        self._database = database

    def createTable(self):
        print "Creating table [%s]" % self.TableName
        try:
            self._database.connection.execute(
                '''CREATE TABLE %s(
                url TEXT,
                timestamp INTEGER,
                json TEXT NOT NULL,
                PRIMARY KEY(url,timestamp)
                )''' % self.TableName)
        except Sqlite3.Error as e:
            print "%s: %s" % (type(e).__name__, e)
            raise JcdException("Database error while creating table [%s]" % self.TableName)

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
            apiCache = ApiCacheDAO(db)
            apiCache.createTable()

    def run(self):
        # remove folder if creation is forced
        if self._args.force:
            self._removeFolder()
        self._createFolder()
        # create tables in data db
        self._createTables()

# configure settings:
class ConfigCmd:

    Parameters = (
        ('apikey', str, 'JCDecaux API key'),
    )

    def __init__(self, args):
        self._args = args

    def displayParam(self,param):
        # TODO: read parameter from database
        print "display param [%s]" % param

    def setParam(self,param,value):
        # TODO: set parameter to db
        print "set param [%s]=%s" % (param,value)

    def run(self):
        for param, value in self._args.__dict__.iteritems():
            if value is None:
                self.displayParam(param)
            else:
                self.setParam(param,value)

# administration
class AdminCmd:

    def __init__(self, args):
        self._args = args

    def vacuum(self):
        # TODO: vacuum db
        print "vacuum"

    def run(self):
        for param, value in self._args.__dict__.iteritems():
            f = getattr(self, param)
            if not value:
                continue
            if type(value) == bool:
                f()
            else:
                f(value)

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

# main
if __name__ == '__main__':
    app = App("~/.jcd")
    try:
        app.run()
    except KeyboardInterrupt:
        pass
