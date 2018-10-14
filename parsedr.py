''' Parse the xml-like token stream coming from DR

User iterwalk to walk the stream

Might want to fix up certain tags before feeding them into this...

If everything is broken, we probably have to write our own walker after all

This is probably best called per xml token that is found

Which means we still need some sort of xml splitter, which is susecptible to breakage.
Any time we get a < we will basically risk triggering the xml splitter.
On failure the xml splitter should display text anyways
But malicious xml in uncontrolled input could cause UI issues

'''
from lxml import etree
from io import BytesIO 

xml = '''
<root><a><b /></a><c /></root>
'''

broken_xml = '''
<root><a><b /></a><c />
'''

print("original: ", broken_xml)


events = ('start', 'end')
context = etree.iterparse(BytesIO(xml.encode('utf-8')), events=events, recover=True)


for action, elem in context:
    print("{}: {}, tag: {}".format(action, elem, elem.tag))

