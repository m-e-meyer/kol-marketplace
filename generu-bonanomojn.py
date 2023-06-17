#!/bin/python

# Read the old Coldfront Marketplace 2.0 page, extract the item IDs and names
# (many of which are wrong), and write them to bonanomoj.txt, where it can
# be Git-controlled and used by the item* scripts.

import urllib.request
import re
import os
import html

mstr = ""
# can't read the original website from Mafia
with urllib.request.urlopen('https://kol.coldfront.net/newmarket/') as fp:
	byts = fp.read()
	mstr = byts.decode("utf8")
# Construct map of ids to HTML-escpaed Coldfront names
opts = re.findall("<option.*?itemid=([0-9]*).*?>(.*?)</option>", mstr)
if opts[0][1] == 'Select item':
	opts = opts[1:]
coldfront_names = { }
for opt in opts:
	coldfront_names[int(opt[0])] = opt[1]
print(f'{len(coldfront_names)} names read from Coldfront')
# Now fetch the correct HTML-escaped names as known to Mafia
mafia_names = { }
os.chdir('/home/markmeyer/kol')
os.system('jar -xvf /home/markmeyer/kol/KoLmafia.jar data/items.txt')
with open('/home/markmeyer/kol/data/items.txt', 'r') as mafits:
	# skip headers
	l = mafits.readline()
	while l.find('seal-clubbing') < 0:
		l = mafits.readline()
	while l != '':
		fs = l.split('\t')
		if len(fs) >= 2:
			mafia_names[int(fs[0])] = fs[1]
		l = mafits.readline()
print(f'{len(mafia_names)} names read from Mafia')
# Process the differences
goodnames = { }
for i in coldfront_names:
	cname = coldfront_names[i]
	mname = mafia_names[i]
	if cname != mname:
		# If Mafia name is too long, truncate it
		short_mname = mname
		dec_mname = html.unescape(mname)
		if len(dec_mname) > 40:
			short_mname = dec_mname[0:37] + '...'
			short_mname = html.escape(short_mname).replace('&#x27;', "'") 
		goodnames[i] = (cname, short_mname, mname)
# Print the results
print(f'{len(goodnames)} names differ')
outfn = '/home/markmeyer/git/kol-marketplace/bonanomoj.txt'
with open(outfn, 'w') as bn:
	for i in sorted(goodnames):
		gn = goodnames[i]
		print(f'{i}\t{gn[0]}\t{gn[1]}\t{gn[2]}', file=bn)
print(f'{outfn} written')
