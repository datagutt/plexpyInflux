#!/usr/bin/env python

import time
import requests
import ConfigParser
import re
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from multiprocessing import Process
from datetime import datetime # for obtaining the curren time and formatting it
from influxdb import InfluxDBClient # via apt-get install python-influxdb
from syslog import syslog
requests.packages.urllib3.disable_warnings(InsecureRequestWarning) # suppress unverified cert warnings

#####Variable definitions#########################
plexpyUrlFormat = '{0}://{1}:{2}{4}/api/v2?apikey={3}'

conf = ConfigParser.ConfigParser()
conf.read("plexpyInflux.conf")

interval = int(conf.get("Script", "interval"))
plexpyProto = conf.get("PlexPy", "protocol")
plexpyHost = conf.get("PlexPy", "host")
plexpyPort = conf.get("PlexPy", "port")
plexpyApiKey = conf.get("PlexPy", "apikey")
plexpyBaseUrl = conf.get("PlexPy", "baseurl")
influxdbHost = conf.get("InfluxDB", "host")
influxdbPort = conf.get("InfluxDB", "port")
influxdbUser = conf.get("InfluxDB", "user")
influxdbPassword = conf.get("InfluxDB", "password")
influxdbDatabase = conf.get("InfluxDB", "database")
#################################################

def GetUrl(protocol, host, port, apikey, baseurl):
	base = ""
	if baseurl:
		base = "/{}".format(baseurl) #place / in front of baseurl if present
		
	return plexpyUrlFormat.format(protocol, host, port, apikey, base) #return fully formatted URL
#end GetUrl

def Run(url, influx):
	while True:
		getActivity = Process(target=GetActivity, args=(url, influx))
		getActivity.start()
		
		getUsers = Process(target=GetUsers, args=(url, influx))
		getUsers.start()
		
		getLibs = Process(target=GetLibs, args=(url, influx))
		getLibs.start()
		
		time.sleep(interval)
#end Run

def GetActivity(url, influx):
	cmd = url + '&cmd=get_activity' #set full request URI

	data = requests.get(cmd, verify=False).json() #pull data, formatted in json
	
	if data:
		streamCount = int(data['response']['data']['stream_count']) #grab total stream count
		
		sessions = data['response']['data']['sessions'] #subsection data to the sessions
		
		totalPlaying = 0
		transcodeCount = 0
		transcodePlaying = 0
		directCount = 0
		directPlaying = 0
		
		for session in sessions: #loop through sessions counting the number of transcoding and direct play streams
			if session['video_decision'] == 'direct play':
				directCount += 1
				if session['state'] == 'playing':
					directPlaying += 1
			else:
				transcodeCount += 1
				if session['state'] == 'playing':
					transcodePlaying += 1
					
			if session['state'] == 'playing':
				totalPlaying += 1
		
		#format the extracted values into json		
		exportData = [
			{
				"measurement": "get_activity",
				"time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
				"tags": {'host': plexpyHost},
				"fields" : { 
					"stream_count": totalPlaying,
					"transcode_count" : transcodeCount,
					"transcode_playing" : transcodePlaying,
					"direct_count" : directCount,
					"direct_playing" : directPlaying
				}
			}
		]
		
		influx.write_points(exportData) #write the values to influxDB
		
	else:
		syslog("plexpyInflux ERROR-ABORT: failed to query plexPy, please verify your settings")
		exit(0)
	
	
#end GetActivity

def GetUsers(url, influx):
	cmd = url + '&cmd=get_users' #set full request URI

	data = requests.get(cmd, verify=False).json() #pull data, formatted in json
	
	if data:
		users = data['response']['data'] #subsection data to the users
		
		totalUsers = len(users) #count the total number of user entries
		totalHomeUsers = 0
		
		for user in users: #loop through users, increase count for every "home" user
			if user['is_home_user'] == '1':
				totalHomeUsers += 1
		
		#format the extracted values into json		
		exportData = [
			{
				"measurement": "get_users",
				"time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
				"tags": {'host': plexpyHost},
				"fields" : {
					"total_users": totalUsers,
					"home_users": totalHomeUsers
				}
			}
		]
		
		influx.write_points(exportData) #write the values to influxDB
		
	else:
		syslog("plexpyInflux ERROR-ABORT: failed to query plexPy, please verify your settings")
		exit(0)
#end GetUsers

def GetLibs(url, influx):
	cmd = url + '&cmd=get_libraries'
	
	data = requests.get(cmd, verify=False).json() #pull data, formatted in json
	
	if data:
		libs = data['response']['data']
		
		numLibs = len(libs)
		
		libCount = {}
		
		for lib in libs:
			key = str(lib['section_name']).lower()
			
			key = re.sub('[^A-Za-z0-9\s]+', '', key)
			key = key.rstrip()
			key = re.sub('[\s]+', ' ', key)
			key = key.replace(" ", "_")
			key = key + '_count'
			
			value = int(lib['count'])
			
			libCount[key] = value
		
		libCount['library_count'] = numLibs
		
		exportData = [
			{
				"measurement": "get_libraries",
				"time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
				"tags": {'host': plexpyHost}
			}
		]
		
		exportData[0]['fields'] = libCount
		
		influx.write_points(exportData) #write the values to influxDB
		
	else:
		syslog("plexpyInflux ERROR-ABORT: failed to query plexPy, please verify your settings")
		exit(0)
#end GetLibs

if __name__ == '__main__':
	syslog("plexpyInflux: Script Started.")
	
	plexpyUrl = GetUrl(plexpyProto, plexpyHost, plexpyPort, plexpyApiKey, plexpyBaseUrl)
	#example: http://192.168.1.10:8181/api/v2?apikey=0f9j092jfkldsjlfk
	
	influxdbClient = InfluxDBClient(influxdbHost, influxdbPort, influxdbUser, influxdbPassword, influxdbDatabase)
	influxdbClient.query('CREATE DATABASE {0}'.format(influxdbDatabase)) #creates the database if it does not exist
	
	Run(plexpyUrl, influxdbClient)