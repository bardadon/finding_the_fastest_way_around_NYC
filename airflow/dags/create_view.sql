create or replace view `amplified-bee-376217.citi_bikes_nyc.rides_under_hour` as
select 
    aaa.*,
    minutes + 60 * hours as duration_in_minutes
from 
(
    select 
    ride_id,
    start_station_name,
    end_station_name,
    started_at,
    ended_at,
    (ended_at - started_at) as duration,
    extract(minute FROM (ended_at - started_at)) minutes,
    extract(hour FROM (ended_at - started_at)) hours
    FROM `amplified-bee-376217.citi_bikes_nyc.bikes_data`
    where 
    start_station_name is not null and
    end_station_name is not null and
    start_station_name != end_station_name and
    extract(day from started_at) = extract(day from ended_at) 
    order by duration desc
) as aaa
where 
    minutes + 60 * hours <= 60;
