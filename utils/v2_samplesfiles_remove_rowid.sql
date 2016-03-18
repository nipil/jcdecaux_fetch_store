-- ---------------------------------------------------------------------------
-- The MIT License (MIT)
--
-- Copyright (c) 2015-2016 Nicolas Pillot
--
-- Permission is hereby granted, free of charge, to any person obtaining a
-- copy of this software and associated documentation files (the 'Software'),
-- to deal in the Software without restriction, including without limitation
-- the rights to use, copy, modify, merge, publish, distribute, sublicense,
-- and/or sell copies of the Software, and to permit persons to whom the
-- Software is furnished to do so, subject to the following conditions:
--
-- The above copyright notice and this permission notice shall be included
-- in all copies or substantial portions of the Software.
--
-- THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS
-- OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
-- FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
-- THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
-- LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
-- FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
-- DEALINGS IN THE SOFTWARE.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- INFORMATION
--
-- This SQL script is to be used on samples tables
-- 1) in the version 2 format
-- 2) and CREATED using v2.0.x to v2.2.x inclusive
-- Samples databases created using 2.3.0+ are already optimized
--
-- These tables were not created without ROWID, thus wasting storage space
-- Using this script is NOT mandatory. All is working correctly with rowids.
-- This just reduces disk usage, which is quite a good thing :-)
--
-- HOW TO USE / EXAMPLE
--
-- execute this SQL file against each sample db to optimize :
-- sqlite3 -bail samples_2015_12_07.db < v2_samplesfiles_remove_rowid.sql
--
-- RESULTS
--
-- using databases from 2015-12-05 to 2016-03-17
-- total size before : 1020480512 = 973 Mbytes
-- otal sier after : 437910528 = 417 Mbytes
-- storage reduced by 57% (about the same for each daily file)
-- ---------------------------------------------------------------------------

-- create new table without rowid
CREATE TABLE IF NOT EXISTS archived_samples_without_rowid (
	timestamp INTEGER NOT NULL,
	contract_id INTEGER NOT NULL,
	station_number INTEGR NOT NULL,
	available_bikes INTEGER NOT NULL,
	available_bike_stands INTEGER NOT NULL,
	PRIMARY KEY (timestamp, contract_id, station_number)
) WITHOUT ROWID;

-- insert all data from old table into new table
INSERT INTO archived_samples_without_rowid
	SELECT
		timestamp,
		contract_id,
		station_number,
		available_bikes,
		available_bike_stands
	FROM archived_samples;

-- remove old table
DROP TABLE archived_samples;

-- use new table as old
ALTER TABLE archived_samples_without_rowid
	RENAME TO archived_samples;

-- reclaim disk space
VACUUM;
