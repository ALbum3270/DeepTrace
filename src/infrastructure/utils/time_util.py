import time
from datetime import datetime, timedelta, timezone

def get_current_timestamp() -> int:
    return int(time.time() * 1000)

def get_current_time() -> str:
    return time.strftime('%Y-%m-%d %X', time.localtime())

def get_current_date() -> str:
    return time.strftime('%Y-%m-%d', time.localtime())

def get_unix_timestamp():
    return int(time.time())

def rfc2822_to_china_datetime(rfc2822_time):
    rfc2822_format = "%a %b %d %H:%M:%S %z %Y"
    dt_object = datetime.strptime(rfc2822_time, rfc2822_format)
    dt_object_china = dt_object.astimezone(timezone(timedelta(hours=8)))
    return dt_object_china

def rfc2822_to_timestamp(rfc2822_time):
    rfc2822_format = "%a %b %d %H:%M:%S %z %Y"
    dt_object = datetime.strptime(rfc2822_time, rfc2822_format)
    dt_utc = dt_object.replace(tzinfo=timezone.utc)
    return int(dt_utc.timestamp())
