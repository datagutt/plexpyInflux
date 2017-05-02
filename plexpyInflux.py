#!/usr/bin/env python

import time
import requests
import ConfigParser
import re
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from multiprocessing import Process
from datetime import datetime  # for obtaining the curren time and formatting it
from influxdb import InfluxDBClient  # via apt-get install python-influxdb
from syslog import syslog
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)  # suppress unverified cert warnings

# Set global variables:
PLEXPY_URL_FORMAT = '{0}://{1}:{2}{4}/api/v2?apikey={3}'

conf = ConfigParser.ConfigParser()
conf.read("plexpyInflux.conf")

INTERVAL = int(conf.get("Script", "INTERVAL"))
PLEXPY_PROTO = conf.get("PlexPy", "protocol")
PLEXPY_HOST = conf.get("PlexPy", "host")
PLEXPY_PORT = conf.get("PlexPy", "port")
PLEXPY_API_KEY = conf.get("PlexPy", "apikey")
PLEXPY_BASE_URL = conf.get("PlexPy", "baseurl")
INFLUXDB_HOST = conf.get("InfluxDB", "host")
INFLUXDB_PORT = conf.get("InfluxDB", "port")
INFLUXDB_USER = conf.get("InfluxDB", "user")
INFLUXDB_PASSWORD = conf.get("InfluxDB", "password")
INFLUXDB_DATABASE = conf.get("InfluxDB", "database")


def get_url(protocol, host, port, apikey, baseurl):
    base = ""
    if baseurl:
        base = "/{}".format(baseurl)  # place / in front of baseurl if present

    return PLEXPY_URL_FORMAT.format(protocol, host, port, apikey, base)  # return fully formatted URL
# end get_url


def run(url, influx):
    while True:
        proc_get_activity = Process(target=get_activity, args=(url, influx))
        proc_get_activity.start()

        proc_get_users = Process(target=get_users, args=(url, influx))
        proc_get_users.start()

        proc_get_libs = Process(target=get_libs, args=(url, influx))
        proc_get_libs.start()

        time.sleep(INTERVAL)
# end run


def get_activity(url, influx):
    cmd = url + '&cmd=get_activity'  # set full request URI

    data = requests.get(cmd, verify=False).json()  # pull data, formatted in json

    if data:
        stream_count = int(data['response']['data']['stream_count'])  # grab total stream count

        sessions = data['response']['data']['sessions']  # subsection data to the sessions

        total_playing = 0
        transcode_count = 0
        transcode_playing = 0
        direct_count = 0
        direct_playing = 0

        # loop through sessions counting the number of transcoding and direct play streams:
        for session in sessions:
            if session['video_decision'] == 'direct play':
                direct_count += 1
                if session['state'] == 'playing':
                    direct_playing += 1
            else:
                transcode_count += 1
                if session['state'] == 'playing':
                    transcode_playing += 1

            if session['state'] == 'playing':
                total_playing += 1

        # format the extracted values into json:
        export_data = [
            {
                "measurement": "get_activity",
                "time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                "tags": {'host': PLEXPY_HOST},
                "fields": {
                    "stream_count": stream_count,
                    "transcode_count": transcode_count,
                    "transcode_playing": transcode_playing,
                    "direct_count": direct_count,
                    "direct_playing": direct_playing
                }
            }
        ]

        influx.write_points(export_data)  # write the values to influxDB
    else:
        syslog("plexpyInflux ERROR-ABORT: failed to query plexPy, please verify your settings")
        exit(0)
# end get_activity


def get_users(url, influx):
    cmd = url + '&cmd=get_users'  # set full request URI

    data = requests.get(cmd, verify=False).json()  # pull data, formatted in json

    if data:
        users = data['response']['data']  # subsection data to the users

        total_users = len(users)  # count the total number of user entries
        total_home_users = 0

        for user in users:  # loop through users, increase count for every "home" user
            if user['is_home_user'] == '1':
                total_home_users += 1

        # format the extracted values into json
        export_data = [
            {
                "measurement": "get_users",
                "time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                "tags": {'host': PLEXPY_HOST},
                "fields": {
                    "total_users": total_users,
                    "home_users": total_home_users
                }
            }
        ]

        influx.write_points(export_data)  # write the values to influxDB

    else:
        syslog("plexpyInflux ERROR-ABORT: failed to query plexPy, please verify your settings")
        exit(0)
# end get_users


def get_libs(url, influx):
    cmd = url + '&cmd=get_libraries'

    data = requests.get(cmd, verify=False).json()  # pull data, formatted in json

    if data:
        libs = data['response']['data']
        num_libs = len(libs)
        lib_count = {}

        for lib in libs:
            key = str(lib['section_name']).lower()
            key = re.sub('[^A-Za-z0-9\s]+', '', key)
            key = key.rstrip()
            key = re.sub('[\s]+', ' ', key)
            key = key.replace(" ", "_")
            key = key + '_count'

            value = int(lib['count'])
            lib_count[key] = value

        lib_count['library_count'] = num_libs

        export_data = [
            {
                "measurement": "get_libraries",
                "time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                "tags": {'host': PLEXPY_HOST}
            }
        ]

        export_data[0]['fields'] = lib_count
        influx.write_points(export_data)  # write the values to influxDB

    else:
        syslog("plexpyInflux ERROR-ABORT: failed to query plexPy, please verify your settings")
        exit(0)
# end get_libs


if __name__ == '__main__':
    syslog("plexpyInflux: Script Started.")

    plexpyUrl = get_url(PLEXPY_PROTO, PLEXPY_HOST, PLEXPY_PORT, PLEXPY_API_KEY, PLEXPY_BASE_URL)
    # example: http://192.168.1.10:8181/api/v2?apikey=0f9j092jfkldsjlfk

    influxdbClient = InfluxDBClient(INFLUXDB_HOST, INFLUXDB_PORT, INFLUXDB_USER, INFLUXDB_PASSWORD, INFLUXDB_DATABASE)
    influxdbClient.query('CREATE DATABASE {0}'.format(INFLUXDB_DATABASE))  # creates the database if it does not exist

    run(plexpyUrl, influxdbClient)
