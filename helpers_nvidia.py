import subprocess

try:
    from xml.etree.ElementTree import * #Python 2.5.
    import xml.etree.ElementTree as ET
except ImportError:
    try:
        from elementtree.ElementTree import *
        import elementtree.ElementTree as ET
    except ImportError:
        raise ImportError('Cannot find any version of ElementTree')



def list_targets():
    targets = []
    p = subprocess.Popen(["/usr/bin/nvidia-smi", "-L"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    for line in out.strip().splitlines():
        if 'GPU' in line and ':' in line:
            targets.append(  int(line.split(':')[0].split(' ')[-1])  )
    return targets



def smi_info(target):
    ret = {'target':target}
    cmd = ["/usr/bin/nvidia-smi", "-q", "-x", "-i", '%d'%target]
    #print ' '.join( cmd )
    nvidia_smi_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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


