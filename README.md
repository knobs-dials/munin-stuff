# munin-stuff
Everyone's got their own munin plugins :)


Note: Uses some linux specifics, and processes subprocess specifics, so these are more proof-of-concept that robustly portable.


### diskstats_simplified
Like the stock diskstats, but avoids per-device graphs and tries to use meaningful device names.

Yields four graphs:
* throughput of each devices in a STACKed graph (read and write separately)
* IOPS of each device, in one STACKed graph.
* wait time 
* utilization


### smart_attributes

Three graphs:
- bad-sector details
- hours and power cycles
- temperatures

You will probably want to run visudo to add a sudoers line like:
munin     ALL=(root)   NOPASSWD: /usr/sbin/smartctl

TODO: more meaningfull things for SSDs. More robustness.


### user_cpu

Attempts to record user's CPU use -- and tries to categorize daemons and kernel processes a bit (database, web, appsupport, filesystem, services, kernel).
(That categorizing can use a lot of work)
