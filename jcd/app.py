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

import re
import sys
import json
import argparse
import requests

import jcd.common
import jcd.cmd

# access jcdecaux web api
class ApiAccess(object):

    BaseUrl = "https://api.jcdecaux.com/vls/v1"

    def __init__(self, apikey):
        self._apikey = apikey[0]

    @staticmethod
    def _parse_reply(reply_text):
        try:
            reply_json = json.loads(reply_text)
        except (ValueError, OverflowError, TypeError) as error:
            print "%s: %s" % (type(error).__name__, error)
            raise jcd.common.JcdException(
                "Could not parse JSON reply :\n%s" % (reply_text, ))
        if isinstance(reply_json, dict) and reply_json.has_key("error"):
            error = reply_json["error"]
            raise jcd.common.JcdException(
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
            if request.status_code != requests.codes.ok:
                raise jcd.common.JcdException("JCDecaux Requests exception: (%i) %s headers=%s content=%s" % (
                    request.status_code, url, repr(request.headers), repr(request.text)))
            # avoid ultra-slow character set auto-detection
            # see https://github.com/kennethreitz/requests/issues/2359
            request.encoding = "utf-8"
            # check for api error
            return self._parse_reply(request.text)
        except requests.exceptions.RequestException as exception:
            raise jcd.common.JcdException(
                "JCDecaux Requests exception: (%s) %s" % (
                    type(exception).__name__, exception))

    def get_all_stations(self):
        return self._get("stations")

    def get_contract_station(self, contract_name, station_id):
        return self._get("stations/%i" % station_id,
                         {"contract": contract_name})

    def get_contract_stations(self, contract_name):
        return self._get("stations",
                         {"contract": contract_name})

    def get_contracts(self):
        return self._get("contracts")

# main app
class App(object):

    DataPath = None
    DbName = None
    Verbose = None

    def __init__(self, default_data_path, default_app_dbname):
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
        for value in jcd.cmd.ConfigCmd.Parameters:
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
        for value in jcd.cmd.AdminCmd.Parameters:
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
        # cron command
        top_command.add_parser(
            'cron',
            help='do a full acquisition cycle',
            description='Fetch and store according to configuration'
        )
        # import v1 command
        import_v1 = top_command.add_parser(
            'import_v1',
            help='import data from version 1',
            description='Analize and import data from the version 1'
        )
        import_v1.add_argument(
            '--source',
            help='directory of version 1 data to import (default: %s)' % jcd.cmd.Import1Cmd.DefaultPath,
            default=jcd.cmd.Import1Cmd.DefaultPath
        )
        import_v1.add_argument(
            '--sync',
            help='sqlite synchronous pragma: 0/1/2/3 (default: 0)',
            type=int,
            choices=range(0, 4),
            default=0
        )
        # export_csv command
        export_csv = top_command.add_parser(
            'export_csv',
            help='export data in csv format',
            description='Dump and store data in csv format'
        )
        export_csv.add_argument(
            'source',
            type=self.export_param_type_check,
            help="'contracts', 'stations', or date (YYYY-MM-DD)"
        )

    def run(self):
        try:
            # parse arguments
            args = self._parser.parse_args()
            # consume data-path argument
            App.DataPath = args.datadir
            del args.datadir
            # consume db name argument
            App.DbName = args.dbname
            del args.dbname
            # consume verbose
            App.Verbose = args.verbose
            del args.verbose
            # consume command
            command = getattr(self, args.command)
            del args.command
            # run requested command
            command(args)
        except jcd.common.JcdException as exception:
            print >>sys.stderr, "JcdException: %s" % exception
            sys.exit(1)

    @staticmethod
    def export_param_type_check(value):
        if value == "contracts" or value == "stations":
            return value
        try:
            return re.match("^\d{4}-\d{2}-\d{2}$", value).group(0)
        except:
            raise argparse.ArgumentTypeError("String '%s' does not match required format"% value)

    @staticmethod
    def init(args):
        init = jcd.cmd.InitCmd(args)
        init.run()

    @staticmethod
    def config(args):
        config = jcd.cmd.ConfigCmd(args)
        config.run()

    @staticmethod
    def admin(args):
        admin = jcd.cmd.AdminCmd(args)
        admin.run()

    @staticmethod
    def fetch(args):
        fetch = jcd.cmd.FetchCmd(args)
        fetch.run()

    @staticmethod
    def store(args):
        store = jcd.cmd.StoreCmd(args)
        store.run()

    @staticmethod
    def cron(args):
        cron = jcd.cmd.CronCmd(args)
        cron.run()

    @staticmethod
    def import_v1(args):
        import1 = jcd.cmd.Import1Cmd(args)
        import1.run()

    @staticmethod
    def export_csv(args):
        exportcsv = jcd.cmd.ExportCsvCmd(args)
        exportcsv.run()
