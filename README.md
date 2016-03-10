# What is this ?

This is a python package which uses [JCDecaux API](https://developer.jcdecaux.com/) to get information from [their bike sharing service](http://www.cyclocity.com), and store station data changes (available bikes and empty stands) efficiently in a series of SQLite daily database.

# Requirements

Pyhton 2.7, with python-requests (not too antique version) and python-pysqlite2 (for SQLite3)

# Storage path

If you want to use another path, either use the move the default one and create a symlink to it in its place, or use the `--datadir` parameter (see below) *consistently across all your commands*.

The default path for version 2 is `~/.jcd_v2/`.

# Upgrade path from version 1

Version 2 is incompatible with version 1, yet they can of course co-exist **in separate folders**.

I recommend to use version 2 as soon as possible, as version 1 will not be maintained.

Please migrate as follows :
- initialize version 2 (defaults path are already different for v1 and v2)
- configure the apikey for version 2
- do a test cron for version 2 job with `./jcdtool.py--verbose cron`
- if all goes ok, configure the real cron job for the version 2
- wait a few minutes to bridge the gap between end of version 1 data and beginning of version 2 data
- un-configure all cron jobs related to version 1

The following can be done anytime later :
- use (v2.1+) `import_v1` command to import version 1 data
- archive version 1 data if you want to or remove it

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

`--verbose` displays output for each operation. By default `jcdtool.py` is mute when all goes right. There are two exceptions to this rule : "config" command with no settings displays the current configuration unconditionnaly of this parameter ; and the "import_v1" command which always displays progress.

`--datadir` uses the specified folder instead of the default path

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

`--vacuum` does a "defragmentation" of the application database. Not much use outside of v1.0 as samples are in their own daily database now, but why not keep it. By the way, the daily databases are **not** vacuum'ed, as they are not modified and only grow, and thus do not fragment.

Sample output when using `--verbose`:

	Vacuuming app.db

	Testing JCDecaux API access
	Searching contracts ...
	Found 27 contracts.
	Fetching stations contract [Nantes] ...
	Found 100 stations.
	Fetching a single station [9] of contract [Nantes] ...
	Station name is [00009-GUEPIN]
	API TEST SUCCESS

## import_v1

See `import_v1 --help` for import_v1 parameter list.

`--source` defines the folder containing data to be imported (version 1 format). Defaults to version 1 default path, ie `~/.jcd`.

`--sync` defines the [SQLite *pragma synchronous*](https://www.sqlite.org/pragma.html#pragma_synchronous) used for databases during the import operation. Values are `0,1,2,3` (=OFF/NORMAL/FULL/EXTRA). **Defaults to 0 (=OFF) for maximum speed.**. Please be advised to use higher values for a better resilience regarding eventual system crashes.

Sample output when using `--verbose`:

	Processing contract 1 station 19 date 2016-01-14... Committing. Stored 12 and removed 12
	Processing contract 1 station 19 date 2016-01-15... Committing. Stored 12 and removed 12
	Processing contract 1 station 19 date 2016-01-16... Committing. Stored 8 and removed 8
	Processing contract 1 station 19 date 2016-01-17... Committing. Stored 1 and removed 1
	Processing contract 1 station 19 date 2016-01-18... Committing. Stored 17 and removed 17

# Return value

`0` when everything was fine

`1` when something was detected wrong

And a traceback for anything bad not yet handled ...

# Licensing for the collected data

The data provider is very clear in the licence ([english](https://developer.jcdecaux.com/files/Open-Licence-en.pdf) / [french](https://developer.jcdecaux.com/files/Open-Licence-fr.pdf)) you accept when using their api.

Basically you can to everything you want with the collected data, as long as you :
- provide **paternity** reference, for example a link back to the API website.
- provide the **date/time of the last update**

Notably, they say their license is compatible with the "Open Government Licence" (OGL) from the United Kingdom, with "CC-BY 2.0" from Creative Commons, and "Open Data Commons Attribution" (ODC-BY) from the Open
Knowledge Foundation.

So i think we can go wild with the collected data !

# FAQ #1: time, timezones and UTC vs localtime

The python script uses `time.time()` and [linux/glibc](http://linux.die.net/man/2/time) says it's in UTC. The SQLite statements use `strftime('%s','now')` and the [documentation](https://www.sqlite.org/lang_datefunc.html) says UTC is used. *Thus the whole tool uses UTC for time*.

As a consequence :
- the "daily" database file names are referring to **UTC date**
- depending on your timezones, your "daily" data bases will be modified up to "sooner" or "later" than what you might expect (see `ls -l ~/.jcd_v2` )
- when using the collected databases, remember to use/convert to UTC time, and query multiple databases files accordingly (using SQLite `ATTACH` with different schema name, for example)

Example: on 2016-02-28 in France (GMT+1, DST not active on that day) the last modification for the '2016-02-27' happened at 00:59 on 2016-02-28. That's because at the time that cron job ran, UTC time was 2016-02-27 23:59:00.

Why do it that way ? JCDecaux API is providing information mainly for France, but for cities in other timezones too. Because of that, i deemed it more sensible to use UTC across the board when *collecting*, and delegate timezone (eventual) management when the collected data is *used*. Second reason, this should allow for clean handling of DST (daylight saving time) for the timezones using it (including France)

This behaviour is consistent with version 1 way of handling time and dates.

# FAQ #2: database size and contract/stations filtering

Each daily database contains changes for every single contract and station for that day. As a consequence, the storage size is maximal.

Depending on the day of the week, the weather, holiday or not, **each day** represents between **6-15 MBytes** of disk space.

If you do not want the whole data database, it is possible. Just :
- use to tool to collect everything daily
- purge yesterday's databases of all un-needed data
- or extract the data you want in a separate database

That way, you can tailor the data to your needs, and of course store a longer history in the same disk size.

I will add a command to do this when i have some time.

