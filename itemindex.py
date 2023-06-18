#!/usr/bin/python
# -*- coding: UTF-8 -*-
#

import os
import re
import html
from urllib import request
import logging
import signal
import ssl
import math

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SOURCE = 'http://kol.coldfront.net/newmarket'
SOURCE_GRAPH = 'http://kol.coldfront.net/newmarket/itemgraph.php'
SOURCE_GRAPH2 = 'newmarket/itemgraph.php'

STYLE = """<style type="text/css">
body
{
	background-color:#fff;
	color:#000;
	font-family:verdana, arial, sans-serif;
	font-size:10px;
	margin:15px;
}

a
{
	color:#000;
	font-weight:bold;
	text-decoration:underline;
}

td
{
	font-size:11px;
	padding:4px;
}

.topbar
{
	background-color:#930;
	color:#fff;
	font-weight:bold;
}

.topbar a
{
	color:#fff;
	text-decoration:none;
}

.topbar a:hover
{
	text-decoration:underline;
}

.options
{
	color:#930;
	font-size:10px;
	font-weight:bold;
}

.row1
{
	background-color:#eee;
}

.row2
{
	background-color:#fdc;
}

select
{
	font-size:9px;
}

input
{
	font-size:9px;
}

button
{
	font-size:9px;
}

/* calendar icon */
img.tcalIcon {
	cursor: pointer;
	margin-left: 1px;
	vertical-align: middle;
}
/* calendar container element */
div#tcal {
	position: absolute;
	visibility: hidden;
	z-index: 100;
	width: 158px;
	padding: 2px 0 0 0;
}
/* all tables in calendar */
div#tcal table {
	width: 100%;
	border: 1px solid silver;
	border-collapse: collapse;
	background-color: white;
}
/* navigation table */
div#tcal table.ctrl {
	border-bottom: 0;
}
/* navigation buttons */
div#tcal table.ctrl td {
	width: 15px;
	height: 20px;
}
/* month year header */
div#tcal table.ctrl th {
	background-color: white;
	color: black;
	border: 0;
}
/* week days header */
div#tcal th {
	border: 1px solid silver;
	border-collapse: collapse;
	text-align: center;
	padding: 3px 0;
	font-family: tahoma, verdana, arial;
	font-size: 10px;
	background-color: gray;
	color: white;
}
/* date cells */
div#tcal td {
	border: 0;
	border-collapse: collapse;
	text-align: center;
	padding: 2px 0;
	font-family: tahoma, verdana, arial;
	font-size: 11px;
	width: 22px;
	cursor: pointer;
}
/* date highlight
   in case of conflicting settings order here determines the priority from least to most important */
div#tcal td.othermonth {
	color: silver;
}
div#tcal td.weekend {
	background-color: #ACD6F5;
}
div#tcal td.today {
	border: 1px solid red;
}
div#tcal td.selected {
	background-color: #FFB3BE;
}
/* iframe element used to suppress windowed controls in IE5/6 */
iframe#tcalIF {
	position: absolute;
	visibility: hidden;
	z-index: 98;
	border: 0;
}
/* transparent shadow */
div#tcalShade {
	position: absolute;
	visibility: hidden;
	z-index: 99;
}
div#tcalShade table {
	border: 0;
	border-collapse: collapse;
	width: 100%;
}
div#tcalShade table td {
	border: 0;
	border-collapse: collapse;
	padding: 0;
}
</style>"""


def respond(err, res=None):
	return {
		'statusCode': '400' if err else '200',
		'body': err.message if err else res,
		'headers': {
			'Content-Type': 'text/html',
		},
	}

timeoutResponse = '''
<html><head></head>
<body><h1>Sorry</h1>
<p>The page timed out while {}.  Please try reloading the page.
<p>- Aventuristo
</body></html>
'''

state = "I was screwing around with it"

class MyTimeout(BaseException):
	pass

def timeout_handler(_signal, _frame):
	logger.info("## TIMEOUT")
	raise MyTimeout("Time exceeded")

def on_aws():
	"""Return whether running as AWS Lambda"""
	return "LAMBDA_TASK_ROOT" in os.environ

MY_JAVASCRIPT = """

function opt(txt, val) {
	var o = document.createElement("option");
	o.value = val;
	o.innerText = txt;
	return o;
}

function loadItemlist(filter) {
	var il = document.getElementById("itemlist");
	while (il.options.length) { il.remove(0); }
	if (filter == '') {
		il.appendChild(opt("Please enter filter above and apply", 0));	
		return;
	}
	var f = filter.toLowerCase();
	// hiddenlist has all the items
	var opts = document.getElementById("hiddenlist").options;
	var opt0 = opt("Select " + f + " item", 0);
	il.appendChild(opt0);
	var found = false;
	for (var i=0; i<opts.length; i++) {
		o = opts[i];
		txt = o.innerText
		if (txt == "Select item")  continue;
		// copy to itemlist the matching options in hiddenlist
		var appending = true;
		if (f != '') {
			appending = txt.toLowerCase().includes(f);	 
		}	
		if (appending) {
			il.appendChild(opt(txt, o.value));
			found = true;
		}
	}
	if (! found) 
		opt0.innerText = "No " + f + " item found";
	il.value = 0;
}

function applyFilter() {
	loadItemlist(document.getElementById("filter").value);
}

function showGraph(itemid) {
	if (itemid > 0) 
		top.main.location.href = "REPLACEME?timespan=1&noanim=1&itemid=" + itemid;
}

"""

MY_FIELDS = """
<br/>Filter: <input type='text' name='filter' id='filter'>
<button onclick='applyFilter();'>apply</button>
<br/>
"""

def corrected_options():
	result = { }
	fn = 'bonanomoj.txt'
	if on_aws():
		fn = os.environ['LAMBDA_TASK_ROOT']+'/'+fn
	else:
		fn = '/home/markmeyer/git/kol-marketplace/'+fn
	with open(fn, 'r', encoding='utf-8') as bn:
		ls = bn.readlines()
		for ln in ls:
			l = ln.split('\t')
			result[int(l[0])] = l[2]
	return result

def repaired_options(options_html):
	# extract item ids and HTML-encoded names
	opts = re.findall("<option.*?itemid=([0-9]*).*?> *(.*?)</option>", options_html)
	# first thing should be "Select item" - remove it
	if opts[0][1] == "Select item":
		opts.remove(opts[0])
	# look for erroneous elements and replace them with good ones
	replacements = [ ]
	korektoj = corrected_options()
	for o in opts:
		i = int(o[0])
		if i in korektoj:
			replacements.append((o[0], korektoj[i]))
	opts[:] = [o for o in opts if int(o[0]) not in korektoj]	# only good ones
	opts = opts + replacements	# add replacements
	# sort by html-unencoded names, case-insensitive
	opts.sort(key=lambda o: html.unescape(o[1]).lower())
	# rebuild list of options
	result = [ ]
	for o in opts:
		result.append(f'<option value={o[0]}>{o[1]}</option>')
	return "\n".join(result)

def transform(b, thisPage):
	b = re.sub('<link [^>]*marketstyle.css[^>]*>', STYLE, b)
	# Replace original links to source with ours
	thatPage = thisPage.replace('itemindex', 'itemgraph')
	b = b.replace(SOURCE_GRAPH, thatPage)
	b = b.replace(SOURCE_GRAPH2, thatPage)
	# Split original page into pieces
	pieces = re.match("(.*?<script type=\"text/javascript\">.*?)(</script>.*?)<body>(.*?BROWSE:</b>)(.*?)<select[^>]*>(.*?)</select>(.*)", 
		b, flags=re.S+re.I)
	pre_script = pieces.group(1)
	pre_body = pieces.group(2)
	pre_fields = pieces.group(3)
	pre_select = pieces.group(4)
	# We need to save the options after we massage them, to use in a hidden
	# select.  That's the easiest way to handle the occasional weird char
	options = repaired_options(pieces.group(5))
	#options = re.sub("value=.*?itemid=", "value=", pieces.group(5))
	#options = re.sub("&timespan.*?>", ">", options)
	post_select = pieces.group(6)
	# Insert my code
	b = (pre_script + MY_JAVASCRIPT.replace('REPLACEME', thatPage) + pre_body 
		+ "<body onload='applyFilter();'>" + pre_fields 
		+ MY_FIELDS
		+ pre_select 
		+ f'<select name="itemlist" id="itemlist" onchange="showGraph(this.options[this.selectedIndex].value);">'
		+ "<option value='0'>Loading...</option>"
		+ "</select><select name='hiddenlist' id='hiddenlist' hidden>" + options + "</select>" 
		+ post_select.replace('width=900', 'width=800'))
	# Put my little stamp on it
	b = b.replace('<b>KoL Marketplace v2.0',
				  '<b>KoL Marketplace v2.<span style="color: green">2</span>')
	b = b.replace('KoL Marketplace v2.0', 'KoL Marketplace v2.2')
	return b

def lambda_handler(event, context):
	'''Demonstrates a simple HTTP endpoint using API Gateway. You have full
	access to the request and response payload, including headers and
	status code.

	This visits a KoL Marketplace search page and relays its content to the caller.
	'''

	if 'source' in event and event['source'] == 'aws.events':
		logger.info('## PING')
		return respond(None, 'Ping acknowledged')

	logger.info('## BEGIN')	
	operation = event['httpMethod']
	if operation == 'GET':
		b = ""
		try:
			global state
			signal.signal(signal.SIGALRM, timeout_handler)
			when = math.floor((context.get_remaining_time_in_millis() / 1000) - 1)
			signal.alarm(when)
			
			state = "retrieving parameters"
			# Retrieve parameters
			params = event['queryStringParameters']
			if params is None: params = { }
			#if not 'itemid' in params:   params['itemid'] = '194'  # Mr. Accessory
			#if not 'timespan' in params: params['timespan'] = '1'  # 1 day
			# Invoke source graph page
			url = SOURCE
			delim = "?"
			for p in params:
				url = url + delim + p + "=" + params[p]
				delim = "&"
			logger.info('## WEB PAGE OPENING')
			#noverify = ssl.SSLContext()
			f = request.urlopen(url) # Remove context=... when cert good
			state = "reading the Marketplace page"
			logger.info('## WEB PAGE READING')
			b = f.read()
			b = b.decode("utf-8", "ignore")
			logger.info('### WEB PAGE RETRIEVED')
			state = "converting the Marketplace page"
			rcon = event['requestContext']
			dom = rcon['domainName']
			if dom == 'localhost':
				thisPage = "http://" + dom + rcon['path']
			else:
				thisPage = "https://" + dom + rcon['path']
			b = transform(b, thisPage)
			logger.info('## WEB PAGE CONVERTED')
		except MyTimeout as e:
			logger.info("## HANDLE TIMEOUT")
			b = 'TImeout!<br/>' + timeoutResponse.format(state)
		except Exception as e:
			b = 'Exception!<br/>' + traceback.format_exc().replace('\n', '<br/>')
		finally:
			signal.alarm(0)
			return respond(None, b)
	else:
		return respond(ValueError('Unsupported method "{}"'.format(operation)))

###############################################################
# If CGI on my laptop, create event and context to pass to lambda_handler
class FakeContext:
	def get_remaining_time_in_millis(self):
		return 300000

if not on_aws():
	import sys
	import urllib.parse
	my_event = { }
	my_event['httpMethod'] = 'GET'
	my_event['queryStringParameters'] = { }
	# web cgi
	method = 'GET'
	if 'REQUEST_METHOD' in os.environ:
		method = os.environ['REQUEST_METHOD']
	if method == 'GET':
		qs = [ ]
		if 'QUERY_STRING' in os.environ:
			qs = urllib.parse.parse_qs(os.environ['QUERY_STRING'])
	for q in qs:
		my_event['queryStringParameters'][q] = qs[q][0]
	my_event['requestContext'] = { }
	my_event['requestContext']['domainName'] = 'localhost'
	my_event['requestContext']['path'] = '/cgi-bin/itemindex.py'
	response = lambda_handler(my_event, FakeContext())
	print(f'Content-Type: {response["headers"]["Content-Type"]}')
	print()
	print(response['body'])
	#with open(f'{os.environ["HOME"]}/marketplace2.0.html', "r") as orig:
	#	b = orig.read()
	#	b = transform(b, 'https://api.aventuristo.net/itemindex')
	#	with open(f'{os.environ["HOME"]}/marketplace2.2.html', "w") as xform:
	#		xform.write(b)
