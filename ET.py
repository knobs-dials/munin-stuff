'''
    A centralized place we can try for the various possible basic ElementTrees,
    and cElementTree if we have it.
    Here to avoid a copy of this code in every module that uses it.

    Uses import *, so most members you want are direct members of this module.

    Since not everything is imported (ElementTree uses __all__), anythign that is
    not imported that way can be accessed via a reference to the module (you would
    probably access it as ET.ET)
'''

try:
    from xml.etree.ElementTree import * #Python 2.5.
    import xml.etree.ElementTree as ET
except ImportError:
    try:
        from elementtree.ElementTree import *
        import elementtree.ElementTree as ET
    except ImportError:
        raise ImportError('Cannot find any version of ElementTree')
 
#We want to replace functions with their cElementTree implementation where possible 
# (cET doesn't reimplement everything)
try:
    from xml.etree.cElementTree import *     #2.5
    import xml.etree.cElementTree as cET
except ImportError:
    try:
        from cElementTree import *
        import cElementTree as cET
    except ImportError:
        pass #possibly complain about the absence of the C implementaiton





def strip_namespace_inplace(etree, namespace=None,remove_from_attr=True):
    """ Takes a parsed ET structure and does an in-place removal of all namespaces,
        or removes a specific namespace (by its URL - and it needs to be exact,
        we don't do anything clever like dealing with final-slash differences).
 
        Can make node searches simpler in structures with unpredictable namespaces
        and in content given to be non-mixed.
 
        By default does so for node names as well as attribute names.       
        (doesn't remove the namespace definitions, but apparently
         ElementTree serialization omits any that are unused)
 
        Note that for attributes that are unique only because of namespace,
        this may attributes to be overwritten. 
        For example: <e p:at="bar" at="quu">   would become: <e at="bar">
 
        I don't think I've seen any XML where this matters, though.

        Returns the URLs for the stripped namespaces, in case you want to report them.
    """
    ret = {}
    if namespace==None: # all namespaces                               
        for elem in etree.getiterator():
            tagname = elem.tag
            if tagname[0]=='{':
                elem.tag = tagname[ tagname.index('}',1)+1:]
 
            if remove_from_attr:
                to_delete=[]
                to_set={}
                for attr_name in elem.attrib:
                    if attr_name[0]=='{':
                        urlendind=attr_name.index('}',1)
                        ret[ attr_name[1:urlendind] ] = True
                        old_val = elem.attrib[attr_name]
                        to_delete.append(attr_name)
                        attr_name = attr_name[urlendind+1:]
                        to_set[attr_name] = old_val
                for key in to_delete:
                    elem.attrib.pop(key)
                elem.attrib.update(to_set)
 
    else: # asked to remove single specific namespace.
        ns = '{%s}' % namespace
        nsl = len(ns)
        for elem in etree.getiterator():
            if elem.tag.startswith(ns):
                elem.tag = elem.tag[nsl:]
 
            if remove_from_attr:
                to_delete=[]
                to_set={}
                for attr_name in elem.attrib:
                    if attr_name.startswith(ns):
                        old_val = elem.attrib[attr_name]
                        to_delete.append(attr_name)
                        ret[ attr_name[1:nsl-1] ] = True
                        attr_name = attr_name[nsl:]
                        to_set[attr_name] = old_val
                for key in to_delete:
                    elem.attrib.pop(key)
                elem.attrib.update(to_set)

    return ret


def indent_inplace(elem, level=0, whitespacestrip=True):
    ''' Alters the text nodes so that the tostring()ed version will look nice and indented.
 
        whitespacestrip can make contents that contain a lot of newlines look cleaner, 
        but changes the stored data even more.
    '''
    i = "\n" + level*"  "
 
    if whitespacestrip:
        if elem.text:
            elem.text=elem.text.strip()
        if elem.tail:
            elem.tail=elem.tail.strip()
 
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent_inplace(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
