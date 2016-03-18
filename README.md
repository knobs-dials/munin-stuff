# munin-stuff

Everyone's got their own munin plugins :)

Some have proof of concept / plaything status, partly because they aren't hugely portable.


### diskstats_simplified
Like the stock diskstats, but instead of per-device graphs of everything, uses per-subject graphs with all devices.
And tries to use meaningful device names.

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

Attempts to record CPU use per user. 
Tries to categorize kernel/daemon stuff a bit, e.g. into database, web, appsupport, filesystem, services, kernel.
(which can always use work, of course)



### procmem_

Meant to be linked as procmem_res and/or procmem_virt, to see which processes are using and/or mapping the most memory.





### screenshots

![user_cpu screenshot](/screenshots/user_cpu.png?raw=true)

![smart screenshot](/screenshots/smart.png?raw=true)

![diskstats screenshot](/screenshots/diskstats.png?raw=true)





