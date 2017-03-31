# plexpy-influxdb-export

This script will query PlexPy to pull basic stats and store them in influxdb for use with Grafana or other graphing solutions. Credit to Drewster727 for intial script that this was based on/copied from: https://github.com/Drewster727/plexpy-influxdb-export

## Dependencies
  * PlexPy (https://github.com/drzoidberg33/plexpy)
  * Python
  * InfluxDB (https://github.com/influxdata/influxdb)
  * InfluxDB Python Client (https://github.com/influxdata/influxdb-python)
    - install on linux via 'apt-get install python-influxdb'

## Configuration Parameters
  * interval (in seconds, default: 30)
  * plexpywebprotocol (http/https, default: http)
  * plexpyhost (needs to be filled with your plexPy IP)
  * plexpyport (default: 8181)
  * plexpyapikey (needs to be filled with your API key)
  * influxdbhost (default: localhost)
  * influxdbport (default: 8086)
  * influxdbuser (default: empty)
  * influxdbpassword (default: empty)
  * influxdbdatabase (default: plexpy_stats)

## Exported Data
  * Activity
    - Total Streams
    - Total Streams (Playing)
    - Transcode Streams
    - Transcode Streams (Playing)
    - Direct Play Streams
    - Direct Play Streams (Playing)
  * Users
    - Total Users
    - Home Users
  * Libraries
    - Item count in each library
  
## Usage
  * Download plexpyInflux.py, plexpyInflux.conf, and plexpyInflux.service
  * Modify plexpyInflux.conf with the information appropriate to your environment
  * Modify plexpyInflux.service, replacing /path/to with the path to the script in both the ExecStart and WorkingDirectory options
  * Copy plexpyInflux.service to /etc/systemd/system/
  * Issue the following to set plexpyInflux to start on boot and run:
  
  ```
  sudo systemctl daemon-reload
  sudo systemctl enable plexpyInflux.service
  sudo systemctl start plexpyInflux
  ```
