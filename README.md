# What is this ?

This is a python package which uses [JCDecaux API](https://developer.jcdecaux.com/) to get information fom [their bike sharing service](http://www.cyclocity.com), and store station information changes station (available bikes and empty stands) efficiently in a series of SQLite daily database.

# Requirements

Pyhton 2.7, with python-requests (not too antique version) and python-pysqlite2 (for SQLite3)

# Storage path

If you want to use another path, either use the move the default one and create a symlink to it in its place, or use the `--datadir` parameter (see below) *consistently across all your commands*.

# Upgrade path from version 1

Version 2 is incompatible with version 1, yet they can of course co-exist **in separate folders**.

I recommend to use version 2 as soon as possible, as version 1 will not be maintained.

Please migrate as follows :
- initialize version 2 (defaults path are already different for v1 and v2)
- configure version 2
- do a test cron for version 2 job with `--verbose`
- if all goes ok, configure the cron job for the version 2
- wait a few minutes to bridge the data gap between version 1 and 2
- un-configure all jobs related to version 1
- use the `import_1to2.py` script to import version 1 data (**Not Yet Implemented**)
- archive version 1 data if you want to rollback
- remove version 1 data

I think it is straightforward but it still deserved to be explained.

# Setup and operation

Initial setup

	./jcdtool.py -v init
	./jcdtool.py -v config --apikey abcdef7890123456789012345678901234567890

Atomic operations

	./jcdtool.py -v fetch --contracts --state
	./jcdtool.py -v store
	./jcdtool.py -v admin --vacuum --apitest

Cron operation (you can of course `-v` to diagnose problems manually)

	./jcdtool.py cron

# Global arguments

See `--help` for full global parameter (and their defaults) and command list.

`--verbose` displays output for each operation. By default `jcdtool.py` is mute when all goes right. There is a single exception to this rule : "config" command with no settings displays the current configuration unconditionnaly of this parameter.

`--datadir` uses the specified folder instead of the default path.

`--dbname` choose the name for main db filename (quite useless, but why not)

# Commands

See `--help` for full command list.

## init

Creates the data folder and the application database inside it (holds settings, cache and contracts)

Use `--force` will **REMOVE** the data folder including all its file, and recreate it

Sample output when using `--verbose`:

	Creating folder [/home/user/.jcd_v2]
	JcdException: Folder [/home/user/.jcd_v2] already exists. Use --force to destroy everything anyway.

	Removing folder [/home/user/.jcd_v2] and its content
	Creating folder [/home/user/.jcd_v2]
	Creating table [settings]
	Creating table [contracts]
	Creating table [new_samples]
	Creating table [old_samples]
	Creating table [changed_samples]
	Setting parameter [contract_ttl] to default value [3600]

## config

See `config --help` for parameter list. With no arguments, show all current settings. With arguments, sets each of them to the provided values. You can provide multiple settings at the same time.

Parameter `apikey` holds your personnal [JCDecaux API key](https://developer.jcdecaux.com/).

Parameter `contract_ttl` holds the time between successfull contract refreshs, *in seconds*.

Sample output displaying configuration:

	apikey = None (last modified on None)
	contract_ttl = 3600 (last modified on 2016-02-27 08:15:34)

Sample output when setting parameters and using `--verbose`:

	Setting apikey = abcdef7890123456789012345678901234567890

## fetch

See `fetch --help` for fetch command list. If no command is provided, nothing is fetched.

`--state` gets all stations from the API and stores the result as new samples. Compares them to the last changed samples to build the `changed` samples list.

`--contracts` gets all contracts from the API and stores them.

Sample output when using `--verbose`:

	New contracts added: 27

	New samples acquired: 3549
	Changed samples available for archive: 3549

## store

Has no options so far.

Stores the changed samples in their daily databases, and updates new/old samples accordingly.

Sample output when using `--verbose`:

	Database [samples_2016_02_27.db] created
	Archiving 3549 changed samples into samples_2016_02_27
	Aged 3549 samples for 2016-02-27

## cron

Has no options so far.

Does a `fetch/store` cycle. The `fetch` action here defaults to fetching `state` and `contracts`, and the contracts are only fetched if their last refresh was enough time ago. See the `contract_ttl` parameter in `config` above.

For sample output when using `--verbose`, see `fetch` and `store`.

## admin

See `admin --help` for admin command list. If no command is provided, nothing is done.

`--apitest` tests if the api is working (it needs a valid API key), and tests each available API entry point for random contracts and stations.

`--vacuum` vacuums the application database. Not much use since v1.0 now samples are in their own daily database, but why not keep it.

Sample output when using `--verbose`:

	Vacuuming SqliteDB

	Testing JCDecaux API access
	Searching contracts ...
	Found 27 contracts.
	Fetching stations contract [Nantes] ...
	Found 100 stations.
	Fetching a single station [9] of contract [Nantes] ...
	Station name is [00009-GUEPIN]
	API TEST SUCCESS

# Return value

`0` when everything was fine

`1` when something was detected wrong

And a traceback for anything bad not yet handled ...
