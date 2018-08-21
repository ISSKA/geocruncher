# -*- coding: utf-8 -*-
#
# This file is part of gmlib. It is free software.
# You can redistribute it and/or modify it under the terms of the GNU Affero General Public License version 3.
#

"""
Created on Mon Jul 18 12:12:46 2016

@author: lopez
"""

import re
import xml.etree.ElementTree as ET

# from: http://stackoverflow.com/questions/1953761/accessing-xmlns-attribute-with-python-elementree
def parse_and_get_ns(file):
    events = "start", "start-ns"
    root = None
    ns = {}
    for event, elem in ET.iterparse(file, events):
        if event == "start-ns":
            if elem[0] in ns and ns[elem[0]] != elem[1]:
                # NOTE: It is perfectly valid to have the same prefix refer
                #     to different URI namespaces in different parts of the
                #     document. This exception serves as a reminder that this
                #     solution is not robust.    Use at your own peril.
                raise KeyError("Duplicate prefix with different URI found.")
            ns[elem[0]] = "{%s}" % elem[1]
        elif event == "start":
            if root is None:
                root = elem
    return ET.ElementTree(root), ns

    
def extract_namespace(tag):
    m = re.match('\{(.*)\}', tag)
    return m.group(1) if m else ''

def namespace(element):
    return extract_namespace(element.tag)
