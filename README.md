# OBSOLETE

This repository has been archived and will not be updated anymore.

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

## export_csv

See `export_csv --help` for export_csv parameter list.

Export contracts by using `export_csv contracts`. Sample output :

	"11","1459598403","Amiens","Velam","FR","Amiens"
	"27","1459598403","Besancon","VéloCité","FR","Besançon"
	"20","1459598403","Bruxelles-Capitale","villo","BE","Anderlecht/Berchem-Sainte-Agathe/Bruxelles/Etterbeek/Forest/Ganshoren/Ixelles/Jette/Koekelberg/Molenbeek-Saint-Jean/Saint-Gilles/Saint-Josse-ten-noode/Schaerbeek/Uccle/Woluwe-Saint-Lambert/Woluwe-Saint-Pierre"
	"21","1459598403","Cergy-Pontoise","Velo2","FR","Cergy/Courdimanche/Eragny-sur-Oise/Neuville-sur-Oise/Pontoise/Saint-Ouen-L'Aumone/Vauréal"

Export stations by using `export_csv stations`. Sample output :

	"1459598703","1","1","1","25","0","1","49.4395241491/1.08880494987","DEVANT N°7 BIS RUE JEANNE D'ARC","01 - THEATRE DES ARTS","1459598111000"
	"1459598703","1","2","1","20","0","1","49.4442849737/1.07838302561","AVENUE PASTEUR","02- PASTEUR - FAC DE DROIT","1459598074000"
	"1459598703","1","3","1","24","0","1","49.4434006164/1.08923406532","PLACE DU VIEUX MARCHE","03- VIEUX MARCHE","1459598266000"
	"1459598703","1","4","1","20","0","1","49.4443079768/1.09357958613","DEVANT N° 39 ALLEE EUGENE DELACROIX","04- MUSEE DES BEAUX ARTS","1459598219000"

Export daily database by date, using `export_csv YYYY-MM-DD`. Sample output :

	"1459598403","1","1","11","14"
	"1459598403","1","2","10","10"
	"1459598403","1","3","10","14"
	"1459598403","1","4","8","12"

Refer to the database schemas for column significance.

## import_v1

See `import_v1 --help` for import_v1 parameter list.

`--source` defines the folder containing data to be imported (version 1 format). Defaults to version 1 default path, ie `~/.jcd`.

`--sync` defines the [SQLite *pragma synchronous*](https://www.sqlite.org/pragma.html#pragma_synchronous) used for databases during the import operation. Values are `0, 1, 2, 3` (OFF, NORMAL, FULL, EXTRA). Defaults to 0 (=OFF) for maximum speed. *Please be advised to use higher values for a better resilience regarding eventual system crashes*.

Sample output for the deduplication phase, and CSV export

	Read and deduplicate all version 1 data
	Store results in daily CSV files
	This will take a while :-)
	...............................................................
	... (and so on)
	...............................................................
	23144609 samples read and 18746591 extracted to CSV files

Sample output for a part of the import phase (with no target data)

	Importing CSV for 2016-02-23
	Database samples_2016_02_23.db created
	...............................................
	... (and so on)
	.............................................Done.
	240773 samples added and 0 skipped

Sample output for a part of the import phase (with target data)

	Removing CSV file for 2016-02-23

	Importing CSV for 2016-02-27
	...............................................
	... (and so on)
	.............................................Done.
	33817 samples added and 139232 skipped
	Removing CSV file for 2016-02-27

Information: for 1GB of version 1 data, representing approximately 60 days, the total processing time takes about 12 minutes, on a laptop with Core 2 Duo T7500 CPU at 2.20GHz, and 2GB of RAM.

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

Depending on the day of the week, the weather, holiday or not, **each day** represents between **2-7 MBytes** of disk space (source: data from 2015-12-05 to 2016-03-17).

If you do not want the whole data database, it is possible. Just :
- use to tool to collect everything daily
- purge yesterday's databases of all un-needed data
- or extract the data you want in a separate database

That way, you can tailor the data to your needs, and of course store a longer history in the same disk size.

I will add a command to do this when i have some time.

# FAQ #3: "No sample found" when importing from version 1

Importing from version 1 requires that the version 2 already knows available contracts (to translate `contract_name` in v1 with `contract_id` in v2)

As a consequence, setup your version 2 (apikey) and run `fetch --contracts` to populate the contracts data. Then, retry `import_v1`.
