-- finds stations present in stats, but not in stations list
-- run with :
-- cat utils/find_forgotten_stations.sql | sqlite3 app.db

.headers on
.mode column

ATTACH 'stats.db' AS stats;

CREATE TEMPORARY TABLE temp.latest AS
    SELECT contract_id, station_number, MAX(b.start_of_day) AS latest
    FROM stats.activity_stations_day AS b
    GROUP BY contract_id, station_number;

SELECT
    c.contract_name AS name,
    c.contract_id AS contract_id,
    l.station_number AS station_number,
    DATE(latest, 'unixepoch') AS last_seen
FROM
    main.contracts AS c,
    temp.latest AS l
WHERE
    c.contract_id = l.contract_id
    AND l.station_number NOT IN (
        SELECT station_number
        FROM main.old_samples AS o
        WHERE o.contract_id = c.contract_id
    )
ORDER BY contract_id, station_number, last_seen;
