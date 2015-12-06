# munin-stuff

Everyone's got their own munin plugins :)
Note that there have proof of concept / plaything status, in that it uses some linux specifics and aren't hugely portable.


### diskstats_simplified
Like the stock diskstats, but avoids per-device graphs and tries to use meaningful device names.

Yields four graphs:
* throughput of each devices, STACKed (read and write separately)
* IOPS of each device, STACKed
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

Attempts to record CPU use per user. For kernel/daemon stuff it tries to categorize a bit, e.g. into database, web, appsupport, filesystem, services, kernel.
(That categorizing can use a bunch of work)


### procmem_

Meant to be linked as procmem_res and/or procmem_virt, to see which processes are using / mapping the most memory.