#!/usr/bin/python3

import time
import os
import sys
import math
import re
import subprocess
import glob

import ET

import helpers_shellcolor as sc
import helpers_format


# next two functions based loosely on nagios-nvidia-smi-plugin

nvidia_smi = "/usr/bin/nvidia-smi" # TODO: use helpers_exec's which()

def nvidia_list_targets():
    targets = []
    cmd = [nvidia_smi, "-L"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
    out, err = p.communicate()
    for line in out.strip().splitlines():
        if b'GPU' in line and b':' in line:
            targets.append(  int(line.split(b':')[0].split(b' ')[-1])  )
    return targets


def nvidia_smi_info(target):
    ret = {'target':target}
    cmd = [nvidia_smi, b"-q", b"-x", b"-i", b'%d'%target]
    #print ' '.join( cmd )
    nvidia_smi_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
    nvidia_smi_proc_out, nvidia_smi_proc_err = nvidia_smi_proc.communicate()
    if nvidia_smi_proc.returncode > 0:
        raise Exception(nvidia_smi_proc_err)
    etree = ET.fromstring(nvidia_smi_proc_out)

    for gpu in etree.iter('gpu'):

        ret['name']  = gpu.find('product_name').text
        #gpuid = gpu.get('id')

        utilization = gpu.find('utilization')
        try:
            ret['util'] = float(utilization.find('gpu_util').text.strip(' %'))
        except:
            ret['util'] = None

        try:
            ret['mem'] = float(utilization.find('memory_util').text.strip(' %'))
        except:
            ret['mem'] = None

        try:
            ret['fbmem_total'] = 1024.*1024.*float(gpu.find('fb_memory_usage/total').text.strip(' MiB'))
            ret['fbmem_used'] = 1024.*1024.*float(gpu.find('fb_memory_usage/used').text.strip(' MiB'))
            ret['fbmem_free'] = 1024.*1024.*float(gpu.find('fb_memory_usage/free').text.strip(' MiB'))
        except:
            raise
            ret['fbmem_total'] = None
            ret['fbmem_used'] = None
            ret['fbmem_free'] = None

        try:
            ret['temp'] = float(gpu.find('temperature/gpu_temp').text.strip(' C'))
        except:
            ret['temp'] = None

        try:
            ret['fan_percent'] = float(gpu.find('fan_speed').text.strip(' %'))
        except:
            ret['fan_percent'] = None

        # TODO
        #if ret['util']:
        #    pass
        #if ret['mem']:
        #    pass

    return ret




statfields='''pid
comm
state
ppid
pgrp
sessionid
ttynr
tpgid
flags
minfault
cminfault
majfault
cmajfault
usertime
systime
childusertime
childsystime
prio
nice
numthread
itrealvalue
starttime
virtsize
rss
rsslim
startcode
endocde
startstack
kstkesp
kstkeip
signal
blocked
sigignore
sigcatch
wchan
nswap
cnswap
exit_signal
processor
rt_prio
policy
delayacct_blkio_ticks
guest_time
childguest_time'''.split()


###


def perprocess(io=1, stat=1, interesting_only=True):
    ''' Gets details from proc for all open processes.
        
        This is relatively expensive, in that it is a few hundred opens (no disk, but still syscall-heavy)
        Try to do this only when you need it.
    '''
    ret={} 
    start_time = time.time()
    for e in os.listdir('/proc/'):
        if e[0] in '0123456789':
            pid=int(e)
            ret[pid]={}
            
            if io:
                ret[pid]['io']={}
                f=open('/proc/%s/io'%e)
                try:
                    for line in f:
                        if ':' in line:
                            k,v = line.rstrip().split(':',1)
                            try:
                                v=int(v,10)
                            except:
                                pass
                            ret[pid]['io'][k]=v
                finally:
                    f.close()

            if stat:
                ret[pid]['stat']={}
                f=open('/proc/%s/stat'%e)
                try:
                    for line in f:
                        l=line.split()
                        for i,v in enumerate(l):
                            k=statfields[i]
                            if interesting_only and k not in ('pid','comm','state','usertime','systime','nice','numthread','rss','processor'):
                                continue
                            ret[pid]['stat'][k]=v
                            if k=='comm':
                                ret[pid]['comm']=v
                finally:
                    f.close()
    ret['time_taken'] = time.time()-start_time
    return ret



def procs_via_ps( root_too=False):
    ''' Geared to report things that use CPU or memory 

        Returns 5-tuple:
         - peruser                     uid -> {pid -> cmd}
         - user_and_procname_to_pids
         - pid_to_cpu     (in percent)
         - pid_to_mem     (in percent)
         - pid_to_state
         - pid_to_cmd     (mostly to pretty-print the previous few)
    '''
    p = subprocess.Popen(b"ps --no-header -eo uid,user,pid,%cpu,%mem,state,comm",shell=True, stdout=subprocess.PIPE, encoding='utf8')
    out,_ = p.communicate()

    peruser      = {}
    user_and_procname_to_pids={}
    pid_to_cpu   = {}
    pid_to_mem   = {}
    pid_to_state = {}
    pid_to_cmd   = {}

    for line in out.splitlines():
        ll = line.strip().split()
        uid   = int(ll[0])
        user  = ll[1]
        pid   = int(ll[2])
        pcpu  = ll[3]
        pmem  = ll[4]
        state = ll[5]
        cmd  = b' '.join(ll[6:])
        if b'<defunct>' in cmd:
            cmd=cmd.replace(b'<defunct>',b'').rstrip()

        up=b'%d//%s'%(uid,cmd)
        if up not in user_and_procname_to_pids:
            user_and_procname_to_pids[up]=[pid]
        else:
            user_and_procname_to_pids[up].append(pid)

        pid_to_cpu[pid]   = float(pcpu)
        pid_to_mem[pid]   = float(pmem)
        pid_to_state[pid] = state
        pid_to_cmd[pid]   = cmd

        if uid==0:
            if not root_too:
                continue
        elif uid<400: # TODO: need a better test
            continue

        if uid not in peruser:
            peruser[uid] = {pid:cmd}
        else:
            peruser[uid][pid] = cmd

    if not root_too:
        if 'root' in peruser: # ignore a bunch of system stuff
            del peruser['root']

    return peruser, user_and_procname_to_pids, pid_to_cpu, pid_to_mem, pid_to_state, pid_to_cmd
    
    
    
def username_by_uid(uid):
    import pwd
    return pwd.getpwuid(int(uid)).pw_name


def dirs_via_lsof(cwd_only=True, pids=None):
    ''' Returns a dict, from PID to the set of directories it has open.

         This only works completely with root rights

         with pids=None it lists everything, which is slow.
         Ideally, you figure out a list of PIDs you are interested in and hand those in.

         CONSIDER: use something like -Fntf0 for more robustness
    '''
    lsof_DIR={} # pid -> opendirs
    import subprocess

    lsof_DIR={}

    lsof_paths = ['/usr/sbin/lsof', '/usr/bin/lsof']
    for option in lsof_paths:
        if os.path.exists(option):
            lsof_path = option
            break

    cmd = [lsof_path,
           '-n', # no host lookup (often faster)
           '-l', # no UID lookup
           '-w', # no warnings
           ]
    if pids!=None and len(pids)>0:
        pidstr = ','.join(str(int(e))  for e in pids) # str(int()) both to ensure strings and for some safety
        cmd.extend(['-p',pidstr])

    t=time.time()
    o=subprocess.Popen(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE, encoding='utf8')
    out,err = o.communicate()
    t=time.time()-t
    #print "Running lsof took %.3fsec"%t

    for line in out.splitlines():
        if b'DIR' in line:
            if cwd_only:
                if not b' cwd ' in line:
                    continue
            l= line.split()
            # for DIR entries the list is name,pid,user, entrytype, ?, ?, ?, dir(+extra)
            #['display.e', '32679', '521', 'cwd', 'DIR', '0,23', '4096', '310050833', '/data/beofiles-2/spanico/David', '(beofiles-2:/data/beofiles-2)']

            dirv = b' '.join(l[8:9]) # and no more, because of the way NFS entries are printed
            pidv = int(l[1])
            #print pidv,dirv
            if pidv not in lsof_DIR:
                lsof_DIR[pidv]=set()
            lsof_DIR[pidv].add(dirv)
    return lsof_DIR




def swapped():
    ' Returns the total amount of pages swapped in and out (from /proc/vmstat) '
    # we could also look at at pgmajfault, but it's basically duplicate with so.
    ret = {'time':time.time()}
    f = open('/proc/vmstat') 
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.startswith('pswpin'):  
            ret['si'] = int(line[7:])
        elif line.startswith('pswpout'):
            ret['so'] = int(line[8:])
    return ret
    


def procstat():
    ret = {'ctxt':None}
    with open('/proc/stat') as f:
        for line in f.readlines():
            line.strip()
            l = line.split()
            if l[0] in (
                    'ctxt',
                    'intr', # first value is total
                    'procs_running',
                    'processes',
                    'procs_blocked',
                    'softirq',
                    ):
                ret[ l[0] ] = int( l[1] )
            if l[0]=='ctxt':
                ctxt = int(l[1])
            
    return ret




#####################################################################
# The below are functions that let you watch CPU, IO, and networking
 
 
# draw bars, fake-sized and geared to show small and large values

def lin_in_cols(v=0, largest=10*1024*1024*1024, cols=60):
    ' accurate, but will not show small functions well '
    return min(1., max(0., float(v)/largest))*cols

def sqrt_in_cols(v=0, largest=10*1024*1024*1024, cols=60):
    return min(1., max(0., math.sqrt(float(v)/largest)))*cols

def oom_in_cols(v=0, largest=10*1024*1024*1024, cols=60):
    v=max(1,v)
    largest_order = math.log(largest,10)
    v_order = math.log(v,10)
    return min(1., max(0., (v_order / largest_order)))*cols


# The below has
#   {statistics-fetcher, difference-between-two-of-those, print-a-difference}
#   x
#   {cpu, disk, network}

def cpu():
    """ Get CPU stats from /proc/stat
        linux-specific  (and probably >=2.6), consider this fragile.
    """
    ret={'time':time.time()}

    cpu={}
    f = open('/proc/stat')
    cpus = 0
    for line in f:
        if line.startswith('cpu'):
            l = line.strip().split()
            name = l[0]
            if name=='cpu':
                continue
            
            cpuc = list(int(e,10) for e in l[1:])
            user, nice, sys, idle = cpuc[0:4]
            cpu[name] = { 'user':cpuc[0],  'nice':cpuc[1],  'sys':cpuc[2],  'idle':cpuc[3] }
            
            if len(l)>=5:
                iowait, irq, softirq = l[4:7]
                cpu[name]['iowait']  = cpuc[4]
                cpu[name]['irq']     = cpuc[5]
                cpu[name]['softirq'] = cpuc[6]
            
            #if len(l)>=8:
            #    cpu[name]['user'] += cpuc[7] # which is steal
            cpu[name]['rest'] = sum(cpuc) - sum(cpu[name].values()) # mostly virualisation stuff.
            cpus+=1
    f.close()
    ret['cpus'] = cpus
    ret['cpu']  = cpu
    return ret


def cpu_diff(procstatdict1, procstatdict2):
    ' calculate CPU-time differences between two results from cpu() '
    ret={'timediff':(procstatdict2['time'] - procstatdict1['time'])}
    cpud1=procstatdict1['cpu']
    cpud2=procstatdict2['cpu']
    for name in cpud2:
        ret[name]={}

        sortkey=999
        n3 = name[3:]
        if len(n3)>0:
            sortkey=int(n3)
        ret[name]['sortkey']=sortkey

        ret[name]['user'] = cpud2[name]['user'] - cpud1[name]['user']
        ret[name]['nice'] = cpud2[name]['nice'] - cpud1[name]['nice']
        ret[name]['sys']  = cpud2[name]['sys']  - cpud1[name]['sys']
        ret[name]['idle'] = cpud2[name]['idle'] - cpud1[name]['idle']
        if 'iowait' in cpud2[name]:
            ret[name]['iowait'] = cpud2[name]['iowait']-cpud1[name]['iowait']
        if 'irq' in cpud2[name]:
            ret[name]['irq'] = cpud2[name]['irq']-cpud1[name]['irq']
        if 'softirq' in cpud2[name]:
            ret[name]['softirq'] = cpud2[name]['softirq']-cpud1[name]['softirq']
        ret[name]['rest'] = cpud2[name]['rest'] - cpud1[name]['rest']
    return ret

def print_cpu_diff(dd,overall=1, separate=1, colwidth=100):
    ' pretty-print the results from cpu_diff()  using colors if possible '
    cw=float(colwidth)
    timediff = dd.pop('timediff')
    d = list(dd.items())
    d.sort( key = lambda x:x[1]['sortkey'] )
    for nm, vals in d:
        if nm=='cpu' and not overall:
            continue
        if nm!='cpu' and not separate:
            continue

        iowaitv=0
        irqv=0
        userv = vals['user']
        nicev = vals['nice']
        sysv  = vals['sys']
        idlev = vals['idle']
        rest  = vals['rest']
        if 'iowait' in vals:
            iowaitv += vals['iowait']
        if 'irq' in vals:
            irqv += vals['irq']
        if 'softirq' in vals:
            irqv += vals['softirq']
        tot=sum([userv,nicev,sysv,idlev,iowaitv,irqv,rest])
        if tot==0:
            # That would mean -- what? No counting? But we're talking USER_HZ.
            # The only reason that should happen is
            #idle=1
            pass
        
        try:
            userf   = round( (cw*userv)/tot )
            nicef   = round( (cw*nicev)/tot )
            sysf    = round( (cw*sysv)/tot  )
            idlef   = round( (cw*idlev)/tot )
            iowaitf = round( (cw*iowaitv)/tot )
            irqf    = round( (cw*irqv)/tot )
            restf   = round( (cw*rest)/tot )
            # CONSIDER: forcefully making it sum to 100 by taking leftovers from user
        except ZeroDivisionError:
            print( nm)
            print( sum([userv,nicev,sysv,idlev,iowaitv,irqv,rest]))
            print( tot)
            print( dd)
            raise
        
        def scalestring(s,amount):
            ''' e.g. 'nice',12 == 'nicenicenice', 'nice',2 == 'ni' '''
            return (s*amount)[:amount] # yeah, the first * is way overkill. Shorter to write, though :)
        
        sys.stderr.write( sc.brightgrey('%7s '%nm) )
        sys.stderr.write( sc.darkgray('') )
        sys.stderr.write(  sc.black(sc.bggreen(       scalestring('_',           int(userf)  )  ) ) )
        #sys.stderr.write(  sc.black(sc.bggreen(       scalestring('user-',           int(userf)  )  ) ) )
        sys.stderr.write(  sc.yellow(sc.bggreen(      scalestring('nice-',        int(nicef)  )  ) ) )
        sys.stderr.write(  sc.black(sc.bgyellow(      scalestring('sys-',         int(sysf)   )  ) ) )
        sys.stderr.write(  sc.black(sc.bgblack(       scalestring(' ',           int(idlef)  )  ) ) )
        sys.stderr.write(  sc.brightred(sc.bgblack(   scalestring('iowait-',     int(iowaitf))  ) ) )
        sys.stderr.write(  sc.brightcyan(sc.bgblack(  scalestring('interrupt',   int(irqf)   )  ) ) )
        sys.stderr.write(  sc.blue(sc.bgblack(        scalestring(' ',           int(restf)  )  ) ) )
        sys.stderr.write( sc.darkgray('|') )

        #sys.stderr.write(  sc.green(sc.bggreen(   'u'*int(userf) ) )  )
        #sys.stderr.write(  sc.yellow(sc.bgyellow( 'n'*int(nicef) ) )  )
        #sys.stderr.write(  sc.red(sc.bgred(       's'*int(sysf)  ) )  )
        #sys.stderr.write(  sc.blue(sc.bgblue(     'i'*int(idlef) ) )  )

        sys.stderr.write('\n')
        sys.stderr.write( sc.reset() )


def mounts(add_ids=False, ignore_types=(), ignore_systemtypes=True):
    ''' if add_ids=True, we try to figure out the id that stat would return (by statting something on there) - makes it easier to figure out what mount any fileis actually on

        ignore_systemstypes is a dozen proc, dev sort of stuff. Meant to declutter, not meant to be thorough.
        ignore_types is there because filtering out squashfs (e.g. snap) or tmpfs seems optional to me.
    '''
    dev_mnt = {}
    f = open('/proc/mounts')
    ret = {}
    for line in f:
        l = line.split()
        dev, mnt, fstype, opts, _, _ = l
        
        if ignore_systemtypes and fstype in ('proc','sysfs','devtmpfs','securityfs','pstore','tracefs','fusectl','configfs','cgroup','cgroup2','debugfs','binfmt_misc','nfsd','mqueue','hugetlbfs','devpts','rpc_pipefs','autofs'):
            continue
        if fstype in ignore_types:
            continue

        entry={'device':dev, 'mountpoint':mnt, 'type':fstype, 'options':opts}
        
        if add_ids:
            stob = os.lstat(mnt)
            devid = stob.st_dev
            entry['device_id'] = devid
        
        ret[dev]=entry
    return ret

    

def df(local_only=True, ignore_types=(), ignore_systemtypes=True):
    ''' Parses output of df tool, adds data from /proc/mounts
        Note that unlike df, this reports in bytes

        entries are (total, used, avail, mountpoint, mountdetaildict)
    '''
    mountdata = mounts(ignore_types=ignore_types, ignore_systemtypes=ignore_systemtypes)    
    if local_only:
        cmd = 'df -l'
    else:
        cmd = 'df'
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
    out, err = p.communicate()
    ret = {}
    for line in out.splitlines()[1:]:
        line = re.sub('\s+',' ', line)
        dev, total, used, avail, percent, mountpoint = line.split(' ',5)
        if dev not in mountdata:
            continue
        #print `dev, total, used, avail, mountpoint`
        total = int(total)*1024
        used  = int(used)*1024
        avail = int(avail)*1024
        ret[dev]=(total,used,avail,mountpoint, mountdata[dev])
    return ret



def devname_to_label():
    ''' figure out name for partitions (get filsystem and partition label via /dev/disk/)
        TODO: figure out whether that is an old interface
        TODO: figure out whether this is heavy enough to suggest cacheing

        For sg* and sd*:
         If there is one labeled partition per disk, 
         then it pretends the one partition is also the volume label (e.g. sda1's label is also sda's)

        https://wiki.archlinux.org/index.php/persistent_block_device_naming
    '''
    d={}
    # filesystem label
    fsbase = '/dev/disk/by-label/' 
    if os.path.exists(fsbase):
        for item in os.listdir(fsbase):
            fullpath = os.path.join(fsbase, item)
            if os.path.islink(fullpath):
                target = os.path.normpath( os.path.join( fsbase, os.readlink(fullpath) ) ) # sort of irrelevant when we only want the basename
                tbn = os.path.basename(target)
                d[tbn] = item

    # GPT partition label. Has preference over filesystem labels (CONSIDER: is that handy?).
    ptbase = '/dev/disk/by-partlabel/'
    if os.path.exists(ptbase):
        for item in os.listdir(ptbase):
            fullpath = os.path.join(ptbase, item)
            if os.path.islink(fullpath):
                target = os.path.normpath( os.path.join( ptbase, os.readlink(fullpath) ) ) # sort of irrelevant when we only want the basename
                tbn = os.path.basename(target)
                d[tbn] = item

    # the fake volume label part
    opd = {} # blackdevname -> [partitiondevnames]
    for devname in d:
        if devname.startswith('sg') or devname.startswith('sd'):
            k3 = devname[:3]
            if k3 not in opd:
                opd[k3] = []
            opd[k3].append(devname)
    for k3 in opd:
        if len(opd[k3])==1:
            d[k3] = d[ opd[k3][0] ] # partition name -> volume name

    return d







def disk_devname_to_prodser(devname=None):
    ''' Returns a list of entries like
        ('ata-HGST_HDN724030ALE640_PK1234P8JKASSP', 'sdb2')
        basically just the contents of /dev/disk/by-id with items like

        If you hand in a devname like sda or /dev/sda that list is filtered by that devname
        The output is sorted (so you can guess that ata- will be first).
    '''
    if devname:
        devname = os.path.basename(devname)

    d={}    
    base = '/dev/disk/by-id/' 
    for item in os.listdir(base):
        #if item.startswith('wnn')
        fullpath = os.path.join(base, item)
        if os.path.islink(fullpath):
            target = os.path.normpath( os.path.join( base, os.readlink(fullpath) ) ) # sort of irrelevant when we only want the basename
            tbn = os.path.basename(target)
            d[item] = tbn
    if devname==None:
        return d.items()
    else:
        ret = []
        for did,devnm in d.items():
            if devnm==devname:
                ret.append(did)
        return sorted(ret)






def disk_interesting_statpaths(ignore_loop=True, ignore_ram=True, ignore_floppy=True ):
    ''' See which disks we can get stats for, 
        ignore some things we probably do not care about

        Returns tuples like 
        ('sda', '/dev/sda', '/sys/block/sda/stat')
        CONSIDER: checking existance of each as further filter
    '''
    ret = []
    for devstatpath in glob.glob( '/sys/block/*/stat'):
        devname = devstatpath[11:-5] # /sys/block/*/stat
        if ignore_loop and '/loop' in devstatpath:
            continue
        if ignore_ram and '/ram' in devstatpath:
            continue
        if ignore_floppy and '/fd' in devstatpath:
            continue
        ret.append( (devname, '/dev/%s'%devname, devstatpath) )
    return ret


def disk_getstats(devpath):
    ''' Taking a thing like 'sda', '/dev/sda', '/sys/block/sda/stat', will look for the last
        parse out the variables there.
        and returns it as a dict like:
        { 'devname': 'sda',
          'time': 1521761417.813765,
          'active_ms': 12767924.0,
          'inflight_ios': 0.0,
          'queuetime_ms': 13567708.0,
          'read_merge_reqs': 438.0,
          'read_reqs': 539253.0,
          'read_sectors': 92696122.0,
          'read_wait_ms': 910180.0,
          'write_merge_reqs': 21214.0,
          'write_reqs': 3020151.0,
          'write_sectors': 37730288.0,
          'write_wait_ms': 12659336.0  }
    '''
    ret = {}
    ret['time']    = time.time()
    # looking for the device basename
    if devpath.count('/')==0:
        devname = devpath
    elif devpath.startswith('/dev/'):
        devname = os.path.basename(devpath)
    elif devpath.startswith('/sys/block'):
        devname = devpath[11:-5] # /sys/block/*/stat
    else:
        raise ValueError("Did not understand input path %r"%devpath)
    ret['devname'] = devname
    statpath = '/sys/block/%s/stat'%devname
    f = open(statpath)
    try:
        for line in f.readlines():
            line = line.strip()
            if len(line)==0:
                continue
            else:
                linenumbers = line.split()
                ret['read_reqs']        = float( linenumbers[0]  ) # int is technically more accurate,
                ret['read_merge_reqs']  = float( linenumbers[1]  ) #  but means more casting later and I'm lazy
                ret['read_sectors']     = float( linenumbers[2]  )
                ret['read_wait_ms']     = float( linenumbers[3]  )
                ret['write_reqs']       = float( linenumbers[4]  )
                ret['write_merge_reqs'] = float( linenumbers[5]  )
                ret['write_sectors']    = float( linenumbers[6]  )
                ret['write_wait_ms']    = float( linenumbers[7]  )
                ret['inflight_ios']     = float( linenumbers[8]  )
                ret['active_ms']        = float( linenumbers[9]  )
                ret['queuetime_ms']     = float( linenumbers[10] )
    finally:   
        f.close()
    return ret


def disk_stats_diff(prev_state, cur_state):
    ''' Given two dicts, which maps from names to individual disk_getstats() results, 
        calculates what happened in the meantime.

        Returns a new dict, like:
        {'foo': {'reqs': 23,
                 'iops': 4,
                 'read_bytespersecond': 219669,
                 'read_percentage': 43,
                 'readwait_mspersecond': 5,
                 'write_bytespersecond': 141870,
                 'write_percentage': 56,
                 'activity_mspersecond': 30,
                 'utilization_percent': 3,
                 'writewait_mspersecond': 24
                }}

        Keep in mind that it will only have entries for devices for which we had previous state.
    '''
    sector_size = 512     # Used for calculation of bandwidth in bytes.
    # VERIFY this is true even on AF disks (pretty sure it is)

    ret = {}
    for devname in cur_state:
        if devname not in prev_state:
            # Could emit a warning?
            continue # no previous state (there should be the next run)
        ret[devname]={}
        prevdict = prev_state[devname]
        curdict  = cur_state[devname]
        #print prevdict
        #print curdict
        
        timediff_sec = curdict['time'] - prevdict['time']
        
        diff_read_reqs   = curdict['read_reqs']  - prevdict['read_reqs']
        diff_write_reqs  = curdict['write_reqs'] - prevdict['write_reqs']
        diff_reqs        = diff_read_reqs + diff_write_reqs
        iops             = diff_reqs / timediff_sec
        
        if diff_reqs == 0:
            read_percentage   = 0.
            write_percentage  = 0.
        else:
            read_percentage  = (100.0 * diff_read_reqs)  / diff_reqs
            write_percentage = (100.0 * diff_write_reqs) / diff_reqs
           
        
        read_wait_ms  = curdict['read_wait_ms']  - prevdict['read_wait_ms']
        write_wait_ms = curdict['write_wait_ms'] - prevdict['write_wait_ms']
        active_ms     = curdict['active_ms'] - prevdict['active_ms']
        queuetime_ms  = curdict['queuetime_ms'] - prevdict['queuetime_ms']
        
        read_bytes =  (curdict['read_sectors']  - prevdict['read_sectors'])  * sector_size
        write_bytes = (curdict['write_sectors'] - prevdict['write_sectors']) * sector_size
        
        utilization = (active_ms / timediff_sec)/10.  # /10 is combination of /1000 for ms and *100 for percent
        
        ret[devname]['reqs']                   = int( diff_reqs                         )
        ret[devname]['iops']                   = int( iops                              )
        ret[devname]['read_percentage']        = int( read_percentage                   )
        ret[devname]['write_percentage']       = int( write_percentage                  )
        ret[devname]['read_bytespersecond']    = int( read_bytes / timediff_sec         )
        ret[devname]['write_bytespersecond']   = int( write_bytes / timediff_sec        )
        ret[devname]['activity_mspersecond']   = int( (active_ms / timediff_sec)        )
        ret[devname]['utilization_percent']    = int( utilization                       )
        ret[devname]['readwait_mspersecond']   = int( float(read_wait_ms)/timediff_sec  )
        ret[devname]['writewait_mspersecond']  = int( float(write_wait_ms)/timediff_sec ) 

    return ret






def disk():
    ret={'time':time.time()}

    f = open('/proc/diskstats')
    for line in f:
        l = line.strip().split()
        devname = l[0]

        # device mapper name can be gotten from: (https://github.com/firehol/netdata/issues/435)
        # /sys/block/<device name>/dm/name
        # /sys/dev/block/<maj:min>/dm/name
        major,minor = l[:2]
        devname = l[2]
        nicername = None
        
        nicernamefn = '/sys/dev/block/%d:%d/dm/name'%(int(major),int(minor)) # ints against injection
        if os.path.exists(nicernamefn):
            nf = open(nicernamefn)
            nicername = nf.read().strip()
            nf.close()
        
        # if not a dm device, look for partition/filesystem labels
        if nicername==None:
            d = devname_to_label()
            if devname in d:
                nicername = d[devname]

        readops, readops_merged, read_sectors, read_ms,  writeops, writeops_merged, write_sectors, write_ms, ioqueue, io_ms, weighed_io_ms = l[3:14]
        ret[devname]={'sectors_read':int(read_sectors), 'sectors_written':int(write_sectors), 'io_ms':int(io_ms), 'nicername':nicername}
    f.close()
    return ret


def disk_diff(dd1,dd2):
    ret={'timediff':(dd2['time']-dd1['time'])}
    for name in dd2:
        if name=='time':
            continue
        ret[name]={'nicername':dd2[name]['nicername']} # TODO: consider insert and remove, currently it borks
        if name in dd1:
            ret[name]['sectors_read_diff']    = dd2[name]['sectors_read']    - dd1[name]['sectors_read']
            ret[name]['sectors_written_diff'] = dd2[name]['sectors_written'] - dd1[name]['sectors_written']
            ret[name]['io_ms_diff']           = dd2[name]['io_ms']           - dd1[name]['io_ms']
    return ret
    
    
def print_disk_diff(dd, colwidth=50., minshow_byps=0):
    cw = float(colwidth)
    def fw(v):
        return sqrt_in_cols(v, largest=800*1024*1024)

    maxnamelen = 0
    for name in dd:
        if name == 'timediff':
            continue
        maxnamelen = max(maxnamelen, len(name))
        if dd[name]['nicername']!=None:
            maxnamelen = max(maxnamelen, 2+len(name+dd[name]['nicername']))
    maxnamelen+=1
                         
    for name in sorted(dd):
        if name=='timediff':
            continue

        # whitelist device names to print/watch
        if 'nicername' in dd[name]:
            pass
        if 'sd' in name or 'sg' in name:    # SATA, SCSI
            if name[-1] in '0123456789': # try to filter out partitons by name
                continue
        elif 'md' in name or 'dm-' in name:     # software RAID, LVM   (should have nicername though)
            pass
        else:
            continue


        if 'sectors_read_diff' in dd[name] and 'sectors_written_diff' in dd[name]: # won't be true first iteration after it's plugged in (VERIFY)
            rdiff = dd[name]['sectors_read_diff']*512      # apparently measured in 512-byte units regardless of AF
            wdiff = dd[name]['sectors_written_diff']*512
            iomsdiff = dd[name]['io_ms_diff']
            timediff = dd['timediff']
            rw = fw(rdiff)
            ww = fw(wdiff)

            if dd[name]['nicername']:
                name = '%s (%s)'%(dd[name]['nicername'], name)
                #name = dd[name]['nicername']
            sys.stderr.write( sc.brightgrey( ('%%%ds '%maxnamelen)%name))

            if wdiff > 1000:
                wtext  = '%11s'%( 'W:%5s '%helpers_format.kmg(wdiff/timediff)  )
            else:
                wtext = ' '*11

            if rdiff > 1000:
                rtext  = '%11s'%( 'R:%5s '%helpers_format.kmg(rdiff/timediff) )
            else:
                rtext  = ' '*11

            # busy%
            util_percent = min( 100, math.ceil((.1*iomsdiff)/timediff) )   # ms -> percent  
            utiltext = '%4d%%'%( util_percent )
            if util_percent==0:
                utiltext = ' '*5
            elif util_percent>=99:
                utiltext = sc.red( utiltext ) 
            elif util_percent>=60:
                utiltext = sc.yellow( utiltext ) 

            if wdiff<300*1000:
                wtext = sc.darkgray(wtext)
            #elif wdiff>200*1000*1000:
            #    wtext = sc.brightmagenta(wtext)
            elif wdiff>50*1000*1000:
                wtext = sc.yellow(wtext)

            if rdiff<300*1000:
                rtext = sc.darkgray(rtext)
            #elif rdiff>200*1000*1000:
            #    rtext = sc.brightmagenta(rtext)
            elif rdiff>50*1000*1000:
                rtext = sc.yellow(rtext)

            sys.stderr.write( utiltext )
            sys.stderr.write( wtext )
            sys.stderr.write( rtext )
            sys.stderr.write( sc.default(' ') )
            sys.stderr.write( sc.black( sc.bgblue(   'w'*int(ww) ) ) )
            sys.stderr.write( sc.black( sc.bgyellow( 'r'*int(rw) ) ) )

            sys.stderr.write('\n')


def ifconfig_parse(): # maybe phase out completely?
    import helpers_network
    ifdetails,_,_ = helpers_network.interfaces()
    ifdetails['time'] = time.time()
    return ifdetails


def net_diff(id1,id2):
    ' calculate the difference between two dicts from ifconfig_parse '
    ret={'timediff':(id2['time']-id1['time'])}
    for name in id2:
        if name=='time':
            continue
        ret[name]={}
        if 'ip' in id2[name]:
            ret[name]['ip']=id2[name]['ip']
        if name in id1:
            if 'txbytes' in id2[name] and 'txbytes' in id1[name]:
                ret[name]['txdiff'] = id2[name]['txbytes'] - id1[name]['txbytes']
            if 'rxbytes' in id2[name] and 'txbytes' in id1[name]:
                ret[name]['rxdiff'] = id2[name]['rxbytes'] - id1[name]['rxbytes']
    return ret


def print_net_diff(dd, colwidth=50., minshow_byps=20000, only_with_ip=True):
    cw = float(colwidth)
    def fw(v):
        return sqrt_in_cols(v, largest=100*1024*1024)
        #return cw*min(2.0, (float(v)/20000000))
        #r = math.log(max(1,v-minshow_byps),10)*(cw/9.)
        #return r

    maxnamelen = 0
    for name in dd:
        if name == 'timediff':
            continue
        maxnamelen = max(maxnamelen, len(name))
    maxnamelen+=1
    
    for name in sorted(dd):
        if name in ('lo',):
            continue
        if name=='timediff':
            continue
        
        if 'rxdiff' not in dd[name]:
            continue
        if 'txdiff' not in dd[name]:
            continue
        
        rxdiff = dd[name]['rxdiff']
        txdiff = dd[name]['txdiff']
        #if rxdiff+txdiff<minshow_byps: # ish.
        #    continue

        rxw = fw(rxdiff)
        txw = fw(txdiff)

        if only_with_ip   and   ('ip' not in dd[name]  or  dd[name]['ip']==None or len(dd[name]['ip'])==0):
            continue

        sys.stderr.write( sc.brightgrey( ('%%%ds'%maxnamelen)%name))
        if 'ip' in dd[name]:
            sys.stderr.write( sc.darkgray(',%-15s '%dd[name]['ip']))
        else:
            sys.stderr.write( '                  ')
       
        txtext = '%13s'%( 'TX:%5s '%helpers_format.kmg(txdiff/dd['timediff'])  )
        rxtext = '%13s'%( 'RX:%5s '%helpers_format.kmg(rxdiff/dd['timediff']) )
        if txdiff < minshow_byps:
            txtext = sc.darkgray(txtext)
        if rxdiff < minshow_byps:
            rxtext = sc.darkgray(rxtext)
        
        sys.stderr.write( txtext )
        sys.stderr.write( rxtext )
            
        sys.stderr.write(  sc.black(sc.bgcyan( 't'*int(txw) ) )  )
        sys.stderr.write(  sc.black(sc.bgmagenta(   'r'*int(rxw) ) )  )

        sys.stderr.write('\n') 
    




def watch(watchcpu=1,  watchdisk=1,  watchnet=1,   sleeptime_sec=1.25):
    ''' Calling this basically makes it a variant of top or such a utility

         on sleeptime: faster than 100Hz makes for silly results
                      Too slow may divide away smallish wait/irq you may want to notice
    '''
    sleeptime_sec = max(sleeptime_sec,0.05)
    # TODO: deal with all div-by-zero issues
    
    prevcpu, curcpu  =  None, None
    prevnet, curnet  =  None, None
    prevdsk, curdsk  =  None, None
    
    while True:
        if watchcpu:
            prevcpu = curcpu
            curcpu = cpu()
        if watchdisk:
            prevdsk = curdsk
            curdsk = disk()
        if watchnet:
            prevnet = curnet
            curnet = ifconfig_parse()

        if sc.supported():
            sys.stderr.write( sc.clearscreen() )
        else:
            sys.stderr.write( '-'*60 )
            sys.stderr.write( '\n' )
            
        if prevcpu:
            try:
                dd = cpu_diff(prevcpu,curcpu)
                print_cpu_diff(dd)
                print
            except:
                raise

        if prevdsk:
            try:
                dd = disk_diff(prevdsk,curdsk)
                print_disk_diff(dd)
                print
            except:
                raise
        
        if prevnet:
            try:
                dd = net_diff(prevnet,curnet)
                print_net_diff(dd)
                print
            except:
                raise

        if watchdisk or watchnet:
            sys.stderr.write( sc.darkgray(' Transfer rates are bytes/second.\n') )
        if watchdisk:
            sys.stderr.write( sc.darkgray(' Disk utilization is %busy, not necessarily %speed.\n') )
            #   see also Documentation/iostats.txt on field 10

        time.sleep(sleeptime_sec)


if __name__ == '__main__':
    try:
        import setproctitle
        setproctitle.setproctitle( os.path.basename(sys.argv[0]) )
    except ImportError:
        pass

    import pprint 

    print('')
    print( " == GPU stats == ")
    try:
        for target in nvidia_list_targets():
            pprint.pprint( nvidia_smi_info(target) ) 
    except OSError:
        print( "Couldn't get nvidia GPU infor. nvidia-smi probably missing")

    #print " == Process stats - perprocess() == "
    #pprint.pprint( perprocess() )


    print('')
    print( " == Process stats - procs_via_ps == ")
    peruser, user_and_procname_to_pids, pid_to_cpu, pid_to_mem, pid_to_state, pid_to_cmd = procs_via_ps()
    #pprint.pprint( peruser )
    #pprint.pprint( user_and_procname_to_pids )
    
    #pprint.pprint( pid_to_cpu )
    for pid in pid_to_cpu:
        cpu_percent = pid_to_cpu[pid]
        if cpu_percent>1:
            print( '%5s%% CPU: PID %s, CMD %r'%(cpu_percent, pid, pid_to_cmd[pid]))

    #print( "Larger memory users")
    for pid in pid_to_mem:
        mem_percent = pid_to_mem[pid]
        if mem_percent>1:
            print( '%5s%% memory: PID %s, CMD %r'%(mem_percent, pid, pid_to_cmd[pid]))
        

    if 1:
        #print( " Non-sleeping processes:")
        state_to_pids = {}
        for pid in pid_to_state:
            state = pid_to_state[pid]
            if state not in state_to_pids:
                state_to_pids[state] = []
            state_to_pids[state].append(pid)
        for state in state_to_pids:
            if state in b'S':
                continue
            print( 'state %s:   %s'%(state, ', '.join('%s (%s)'%(pid_to_cmd[pid],pid)   for pid in state_to_pids[state])))



    print('')
    print( " == Working dirs == ")
    wd = dirs_via_lsof()
    for pid in wd:
        dirlist = tuple(wd[pid])
        if dirlist==('/',): # probably, though not necessarily, unineresting
            continue
        name = '%d (unknown)'%pid
        if pid in pid_to_cmd:
            name = pid_to_cmd[pid]
        print( '%22s   %s'%(name, dirlist))



    print ('')
    print (" == Speed indicators ==")

    print( "Collecing 1 second")
    c1 = cpu()
    d1 = disk()
    i1 = ifconfig_parse()

    time.sleep(1)

    c2 = cpu()
    d2 = disk()
    i2 = ifconfig_parse()

    print
    #print( "CPU state snapshot")
    #pprint.pprint( c2 )
    print( "CPU previous-second difference")
    cd = cpu_diff(c1, c2)
    for k in cd:
        print( ' %6s %s'%(k, cd[k]))

    print
    #print "Disk state snapshot"
    #pprint.pprint( d2 )
    print( "Disk previous-second difference")
    dd = disk_diff(d1, d2)
    for k in dd:
        print( ' %6s %s'%(k, dd[k]))

    print('')
    #print "Network state snapshot"
    #pprint.pprint( i2 )
    print( "Network previous-second difference")
    nd = net_diff(i1, i2)
    for k in nd:
        print( ' %6s %s'%(k, nd[k]))
