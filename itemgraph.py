#!/usr/bin/python
# -*- coding: UTF-8 -*-
#

import re
import os
import logging
import math
from urllib import request
import traceback
import signal
import ssl
# No longer a need for database, since we can only go back 2 years now
#import boto3
#from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime, timedelta, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

#WIKILOC = "80.94.68.82"
WIKILOC = "kol.coldfront.net"
SOURCE = f'https://{WIKILOC}/newmarket/itemgraph.php'
SOURCE_IMG = f'http://{WIKILOC}/newmarket/newmarket/'
ECON_URL = "https://www.kingdomofloathing.com/econ/result.php"
SVG_WIDTH = 440
SVG_HEIGHT = 310
GRAPH_WIDTH = 300
GRAPH_HEIGHT = 200
TOP_MARGIN = 5
SIDE_MARGIN = (SVG_WIDTH-GRAPH_WIDTH)/2
GRAPH_BOTTOM = TOP_MARGIN+GRAPH_HEIGHT
BEGINNING_OF_HISTORY = datetime.strptime('2015-06-09 +0000', '%Y-%m-%d %z')
BEGINNING_OF_ECON = datetime.strptime('2020-04-19 +0000', '%Y-%m-%d %z')
KOL_MARKETPLACE_OUTAGE = datetime.strptime('2020-05-04 12:00 +0000', '%Y-%m-%d %H:%M %z')
# Below is the difference I'm seeing between graph times and actual times
# On July 2, 2020, at 13:13 CDT (18:13Z) I bought 50 seal-skull helmets.
# Let's see when the sale shows up on Marketplace
TIMESHIFT = timedelta(hours=-8)

STYLE = R"""<style type="text/css">
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

OLD_DATESTYLE = "<link rel='stylesheet' type='text/css' href='datepicker_vista.css' />"
OLD_MOOTOOLS = f'<script language="JavaScript" src="http://{WIKILOC}/newmarket/mootools-1.2.4-core-jm.js"></script>'
OLD_DATEPICKER = f'<script language="JavaScript" src="http://{WIKILOC}/newmarket/datepicker_mod.js"></script>'

DATESTYLE = Rf'''
<style>
.datepicker_vista {{
	position: absolute;
	font-size: 10px;
	font-family: Tahoma, sans-serif;
	color: #000;
	line-height: normal;
	width: 172px;
	height: 135px;
	padding: 14px;
	background: url(https://{WIKILOC}/newmarket/frame.png) no-repeat;
}}

/* header
********************************************************/
.datepicker_vista .header {{
	position: relative;
	height: 15px;
	margin-bottom: 5px;
	padding-top: 1px;
}}

.datepicker_vista .header .title {{
	text-align: center;
	margin: 0 18px 0 18px;
}}

.datepicker_vista .header .titleText {{
}}

.datepicker_vista .header .previous,
.datepicker_vista .header .next,
.datepicker_vista .header .closeButton {{
	position: absolute;
	cursor: pointer;
	text-indent: -40px;
	overflow: hidden;
	width: 12px;
	height: 12px;
	top: 2px;
	background-image: url(https://{WIKILOC}/newmarket/buttons.png);
	background-position: left top;
	background-repeat: no-repeat;
}}

.datepicker_vista .header .previous {{
	left: 4px;
}}
.datepicker_vista .header .previous:hover {{
	background-position: left bottom;
}}
.datepicker_vista .header .next {{
	right: 4px;
	background-position: -13px top;
}}
.datepicker_vista .header .next:hover {{
	background-position: -13px bottom;
}}
.datepicker_vista .header .closeButton {{
	display: none;
	right: 0px;
	top: 0px;
	background-position: right top;
}}
.datepicker_vista .header .closeButton:hover {{
	background-position: right bottom;
}}

/* body
********************************************************/
.datepicker_vista .body {{
	position: relative;
	top: 0px;
	left: 2px;
	width: 168px;
	height: 112px;
	overflow: hidden;
}}

/* time
********************************************************/
.datepicker_vista .time {{
	position: relative;
	width: 100%;
	height: 100%;
}}

.datepicker_vista .time .hour,
.datepicker_vista .time .separator,
.datepicker_vista .time .minutes {{
	border: 1px solid #ccc;
	background: #fff;
	width: 50px;
	font-size: 32px;
	position: absolute;
	top: 10px;
	text-align: center;
	padding: 2px;
}}

.datepicker_vista .time .hour {{
	left: 15px;
}}
.datepicker_vista .time .separator {{
	background: transparent;
	border: 0px;
	width: 10px;
	left: 76px;
}}

.datepicker_vista .time .minutes {{
	left: 95px;
}}
.datepicker_vista .time .ok {{
	position: absolute;
	top: 65px;
	width: 136px;
	left: 15px;
	font-size: 20px;
}}

/* days-grid
********************************************************/
.datepicker_vista .days .day {{
	float: left;
	text-align: center;
	overflow: hidden;
	width: 23px;
	height: 15px;
	margin: 0 1px 1px 0;
}}
.datepicker_vista .days .titles {{
	height: 15px;
	border-bottom: 1px solid #e0e0e0;
	margin-bottom: 1px;
}}
.datepicker_vista .days .day0 {{
	margin-right: 0;
}}

.datepicker_vista .days .week5 .day {{
	margin-bottom: 0;
}}

/* days-colors
********************************************************/
.datepicker_vista .days .week .day {{
	cursor: pointer;
}}
.datepicker_vista .days .week .day:hover {{
	background: url(https://{WIKILOC}/newmarket/days.png) left top no-repeat;
	color: #0084AA;
}}

.datepicker_vista .days .otherMonth {{
	color: #aaa;
}}

.datepicker_vista .days .selected {{
	background: url(https://{WIKILOC}/newmarket/days.png) left bottom no-repeat;
	color: #316879;
}}

/* months-grid
********************************************************/
.datepicker_vista .months .month {{
	float: left;
	cursor: pointer;
	text-align: center;
	padding-top: 6px;
	width: 55px;
	overflow: hidden;
	height: 21px;
	margin: 0 1px 1px 0;
}}

.datepicker_vista .months .month3,
.datepicker_vista .months .month6,
.datepicker_vista .months .month9,
.datepicker_vista .months .month12 {{
	margin-right: 0;
}}

.datepicker_vista .months .month10,
.datepicker_vista .months .month11,
.datepicker_vista .months .month12 {{
	margin-bottom: 0;
}}

/* months-colors
********************************************************/
.datepicker_vista .months .month:hover {{
	background: url(https://{WIKILOC}/newmarket/months.png) left top no-repeat;
	color: #0084AA;
}}

.datepicker_vista .months .selected {{
	background: url(https://{WIKILOC}/newmarket/months.png) left bottom no-repeat;
	color: #316879;
}}

/* years-grid
********************************************************/
.datepicker_vista .years .year {{
	float: left;
	cursor: pointer;
	text-align: center;
	padding-top: 6px;
	width: 32px;
	overflow: hidden;
	height: 21px;
	margin: 0 1px 1px 0;
}}

.datepicker_vista .years .year4,
.datepicker_vista .years .year9,
.datepicker_vista .years .year14,
.datepicker_vista .years .year19 {{
	margin-right: 0;
}}

.datepicker_vista .years .year15,
.datepicker_vista .years .year16,
.datepicker_vista .years .year17,
.datepicker_vista .years .year18,
.datepicker_vista .years .year19 {{
	margin-bottom: 0;
}}

/* years-colors
********************************************************/
.datepicker_vista .years .year:hover {{
	background: url(https://{WIKILOC}/newmarket/years.png) left top no-repeat;
	color: #0084AA;
}}

.datepicker_vista .years .selected {{
	background: url(https://{WIKILOC}/newmarket/years.png) left bottom no-repeat;
	color: #316879;
}}

/* global
********************************************************/
.datepicker_vista .unavailable {{
	background: none !important;
	color: #fbb !important;
	cursor: default !important;
}}
</style>
'''

MOOTOOLS = R'''<script language="JavaScript">
//MooTools, <http://mootools.net>, My Object Oriented (JavaScript) Tools. Copyright (c) 2006-2009 Valerio Proietti, <http://mad4milk.net>, MIT Style License.

var MooTools={'version':'1.2.4','build':'0d9113241a90b9cd5643b926795852a2026710d4'};var Native=function(options){options=options||{};var name=options.name;var legacy=options.legacy;var protect=options.protect;var methods=options.implement;var generics=options.generics;var initialize=options.initialize;var afterImplement=options.afterImplement||function(){};var object=initialize||legacy;generics=generics!==false;object.constructor=Native;object.$family={name:'native'};if(legacy&&initialize)object.prototype=legacy.prototype;object.prototype.constructor=object;if(name){var family=name.toLowerCase();object.prototype.$family={name:family};Native.typize(object,family);}
var add=function(obj,name,method,force){if(!protect||force||!obj.prototype[name])obj.prototype[name]=method;if(generics)Native.genericize(obj,name,protect);afterImplement.call(obj,name,method);return obj;};object.alias=function(a1,a2,a3){if(typeof a1=='string'){var pa1=this.prototype[a1];if((a1=pa1))return add(this,a2,a1,a3);}
for(var a in a1)this.alias(a,a1[a],a2);return this;};object.implement=function(a1,a2,a3){if(typeof a1=='string')return add(this,a1,a2,a3);for(var p in a1)add(this,p,a1[p],a2);return this;};if(methods)object.implement(methods);return object;};Native.genericize=function(object,property,check){if((!check||!object[property])&&typeof object.prototype[property]=='function')object[property]=function(){var args=Array.prototype.slice.call(arguments);return object.prototype[property].apply(args.shift(),args);};};Native.implement=function(objects,properties){for(var i=0,l=objects.length;i<l;i++)objects[i].implement(properties);};Native.typize=function(object,family){if(!object.type)object.type=function(item){return($type(item)===family);};};(function(){var natives={'Array':Array,'Date':Date,'Function':Function,'Number':Number,'RegExp':RegExp,'String':String};for(var n in natives)new Native({name:n,initialize:natives[n],protect:true});var types={'boolean':Boolean,'native':Native,'object':Object};for(var t in types)Native.typize(types[t],t);var generics={'Array':["concat","indexOf","join","lastIndexOf","pop","push","reverse","shift","slice","sort","splice","toString","unshift","valueOf"],'String':["charAt","charCodeAt","concat","indexOf","lastIndexOf","match","replace","search","slice","split","substr","substring","toLowerCase","toUpperCase","valueOf"]};for(var g in generics){for(var i=generics[g].length;i--;)Native.genericize(natives[g],generics[g][i],true);}})();var Hash=new Native({name:'Hash',initialize:function(object){if($type(object)=='hash')object=$unlink(object.getClean());for(var key in object)this[key]=object[key];return this;}});Hash.implement({forEach:function(fn,bind){for(var key in this){if(this.hasOwnProperty(key))fn.call(bind,this[key],key,this);}},getClean:function(){var clean={};for(var key in this){if(this.hasOwnProperty(key))clean[key]=this[key];}
return clean;},getLength:function(){var length=0;for(var key in this){if(this.hasOwnProperty(key))length++;}
return length;}});Hash.alias('forEach','each');Array.implement({forEach:function(fn,bind){for(var i=0,l=this.length;i<l;i++)fn.call(bind,this[i],i,this);}});Array.alias('forEach','each');function $A(iterable){if(iterable.item){var l=iterable.length,array=new Array(l);while(l--)array[l]=iterable[l];return array;}
return Array.prototype.slice.call(iterable);};function $arguments(i){return function(){return arguments[i];};};function $chk(obj){return!!(obj||obj===0);};function $clear(timer){clearTimeout(timer);clearInterval(timer);return null;};function $defined(obj){return(obj!=undefined);};function $each(iterable,fn,bind){var type=$type(iterable);((type=='arguments'||type=='collection'||type=='array')?Array:Hash).each(iterable,fn,bind);};function $empty(){};function $extend(original,extended){for(var key in(extended||{}))original[key]=extended[key];return original;};function $H(object){return new Hash(object);};function $lambda(value){return($type(value)=='function')?value:function(){return value;};};function $merge(){var args=Array.slice(arguments);args.unshift({});return $mixin.apply(null,args);};function $mixin(mix){for(var i=1,l=arguments.length;i<l;i++){var object=arguments[i];if($type(object)!='object')continue;for(var key in object){var op=object[key],mp=mix[key];mix[key]=(mp&&$type(op)=='object'&&$type(mp)=='object')?$mixin(mp,op):$unlink(op);}}
return mix;};function $pick(){for(var i=0,l=arguments.length;i<l;i++){if(arguments[i]!=undefined)return arguments[i];}
return null;};function $random(min,max){return Math.floor(Math.random()*(max-min+1)+min);};function $splat(obj){var type=$type(obj);return(type)?((type!='array'&&type!='arguments')?[obj]:obj):[];};var $time=Date.now||function(){return+new Date;};function $try(){for(var i=0,l=arguments.length;i<l;i++){try{return arguments[i]();}catch(e){}}
return null;};function $type(obj){if(obj==undefined)return false;if(obj.$family)return(obj.$family.name=='number'&&!isFinite(obj))?false:obj.$family.name;if(obj.nodeName){switch(obj.nodeType){case 1:return'element';case 3:return(/\S/).test(obj.nodeValue)?'textnode':'whitespace';}}else if(typeof obj.length=='number'){if(obj.callee)return'arguments';else if(obj.item)return'collection';}
return typeof obj;};function $unlink(object){var unlinked;switch($type(object)){case'object':unlinked={};for(var p in object)unlinked[p]=$unlink(object[p]);break;case'hash':unlinked=new Hash(object);break;case'array':unlinked=[];for(var i=0,l=object.length;i<l;i++)unlinked[i]=$unlink(object[i]);break;default:return object;}
return unlinked;};var Browser=$merge({Engine:{name:'unknown',version:0},Platform:{name:(window.orientation!=undefined)?'ipod':(navigator.platform.match(/mac|win|linux/i)||['other'])[0].toLowerCase()},Features:{xpath:!!(document.evaluate),air:!!(window.runtime),query:!!(document.querySelector)},Plugins:{},Engines:{presto:function(){return(!window.opera)?false:((arguments.callee.caller)?960:((document.getElementsByClassName)?950:925));},trident:function(){return(!window.ActiveXObject)?false:((window.XMLHttpRequest)?((document.querySelectorAll)?6:5):4);},webkit:function(){return(navigator.taintEnabled)?false:((Browser.Features.xpath)?((Browser.Features.query)?525:420):419);},gecko:function(){return(!document.getBoxObjectFor&&window.mozInnerScreenX==null)?false:((document.getElementsByClassName)?19:18);}}},Browser||{});Browser.Platform[Browser.Platform.name]=true;Browser.detect=function(){for(var engine in this.Engines){var version=this.Engines[engine]();if(version){this.Engine={name:engine,version:version};this.Engine[engine]=this.Engine[engine+version]=true;break;}}
return{name:engine,version:version};};Browser.detect();Browser.Request=function(){return $try(function(){return new XMLHttpRequest();},function(){return new ActiveXObject('MSXML2.XMLHTTP');},function(){return new ActiveXObject('Microsoft.XMLHTTP');});};Browser.Features.xhr=!!(Browser.Request());Browser.Plugins.Flash=(function(){var version=($try(function(){return navigator.plugins['Shockwave Flash'].description;},function(){return new ActiveXObject('ShockwaveFlash.ShockwaveFlash').GetVariable('$version');})||'0 r0').match(/\d+/g);return{version:parseInt(version[0]||0+'.'+version[1],10)||0,build:parseInt(version[2],10)||0};})();function $exec(text){if(!text)return text;if(window.execScript){window.execScript(text);}else{var script=document.createElement('script');script.setAttribute('type','text/javascript');script[(Browser.Engine.webkit&&Browser.Engine.version<420)?'innerText':'text']=text;document.head.appendChild(script);document.head.removeChild(script);}
return text;};Native.UID=1;var $uid=(Browser.Engine.trident)?function(item){return(item.uid||(item.uid=[Native.UID++]))[0];}:function(item){return item.uid||(item.uid=Native.UID++);};var Window=new Native({name:'Window',legacy:(Browser.Engine.trident)?null:window.Window,initialize:function(win){$uid(win);if(!win.Element){win.Element=$empty;if(Browser.Engine.webkit)win.document.createElement("iframe");win.Element.prototype=(Browser.Engine.webkit)?window["[[DOMElement.prototype]]"]:{};}
win.document.window=win;return $extend(win,Window.Prototype);},afterImplement:function(property,value){window[property]=Window.Prototype[property]=value;}});Window.Prototype={$family:{name:'window'}};new Window(window);var Document=new Native({name:'Document',legacy:(Browser.Engine.trident)?null:window.Document,initialize:function(doc){$uid(doc);doc.head=doc.getElementsByTagName('head')[0];doc.html=doc.getElementsByTagName('html')[0];if(Browser.Engine.trident&&Browser.Engine.version<=4)$try(function(){doc.execCommand("BackgroundImageCache",false,true);});if(Browser.Engine.trident)doc.window.attachEvent('onunload',function(){doc.window.detachEvent('onunload',arguments.callee);doc.head=doc.html=doc.window=null;});return $extend(doc,Document.Prototype);},afterImplement:function(property,value){document[property]=Document.Prototype[property]=value;}});Document.Prototype={$family:{name:'document'}};new Document(document);Array.implement({every:function(fn,bind){for(var i=0,l=this.length;i<l;i++){if(!fn.call(bind,this[i],i,this))return false;}
return true;},filter:function(fn,bind){var results=[];for(var i=0,l=this.length;i<l;i++){if(fn.call(bind,this[i],i,this))results.push(this[i]);}
return results;},clean:function(){return this.filter($defined);},indexOf:function(item,from){var len=this.length;for(var i=(from<0)?Math.max(0,len+from):from||0;i<len;i++){if(this[i]===item)return i;}
return-1;},map:function(fn,bind){var results=[];for(var i=0,l=this.length;i<l;i++)results[i]=fn.call(bind,this[i],i,this);return results;},some:function(fn,bind){for(var i=0,l=this.length;i<l;i++){if(fn.call(bind,this[i],i,this))return true;}
return false;},associate:function(keys){var obj={},length=Math.min(this.length,keys.length);for(var i=0;i<length;i++)obj[keys[i]]=this[i];return obj;},link:function(object){var result={};for(var i=0,l=this.length;i<l;i++){for(var key in object){if(object[key](this[i])){result[key]=this[i];delete object[key];break;}}}
return result;},contains:function(item,from){return this.indexOf(item,from)!=-1;},extend:function(array){for(var i=0,j=array.length;i<j;i++)this.push(array[i]);return this;},getLast:function(){return(this.length)?this[this.length-1]:null;},getRandom:function(){return(this.length)?this[$random(0,this.length-1)]:null;},include:function(item){if(!this.contains(item))this.push(item);return this;},combine:function(array){for(var i=0,l=array.length;i<l;i++)this.include(array[i]);return this;},erase:function(item){for(var i=this.length;i--;i){if(this[i]===item)this.splice(i,1);}
return this;},empty:function(){this.length=0;return this;},flatten:function(){var array=[];for(var i=0,l=this.length;i<l;i++){var type=$type(this[i]);if(!type)continue;array=array.concat((type=='array'||type=='collection'||type=='arguments')?Array.flatten(this[i]):this[i]);}
return array;},hexToRgb:function(array){if(this.length!=3)return null;var rgb=this.map(function(value){if(value.length==1)value+=value;return value.toInt(16);});return(array)?rgb:'rgb('+rgb+')';},rgbToHex:function(array){if(this.length<3)return null;if(this.length==4&&this[3]==0&&!array)return'transparent';var hex=[];for(var i=0;i<3;i++){var bit=(this[i]-0).toString(16);hex.push((bit.length==1)?'0'+bit:bit);}
return(array)?hex:'#'+hex.join('');}});Function.implement({extend:function(properties){for(var property in properties)this[property]=properties[property];return this;},create:function(options){var self=this;options=options||{};return function(event){var args=options.arguments;args=(args!=undefined)?$splat(args):Array.slice(arguments,(options.event)?1:0);if(options.event)args=[event||window.event].extend(args);var returns=function(){return self.apply(options.bind||null,args);};if(options.delay)return setTimeout(returns,options.delay);if(options.periodical)return setInterval(returns,options.periodical);if(options.attempt)return $try(returns);return returns();};},run:function(args,bind){return this.apply(bind,$splat(args));},pass:function(args,bind){return this.create({bind:bind,arguments:args});},bind:function(bind,args){return this.create({bind:bind,arguments:args});},bindWithEvent:function(bind,args){return this.create({bind:bind,arguments:args,event:true});},attempt:function(args,bind){return this.create({bind:bind,arguments:args,attempt:true})();},delay:function(delay,bind,args){return this.create({bind:bind,arguments:args,delay:delay})();},periodical:function(periodical,bind,args){return this.create({bind:bind,arguments:args,periodical:periodical})();}});Number.implement({limit:function(min,max){return Math.min(max,Math.max(min,this));},round:function(precision){precision=Math.pow(10,precision||0);return Math.round(this*precision)/precision;},times:function(fn,bind){for(var i=0;i<this;i++)fn.call(bind,i,this);},toFloat:function(){return parseFloat(this);},toInt:function(base){return parseInt(this,base||10);}});Number.alias('times','each');(function(math){var methods={};math.each(function(name){if(!Number[name])methods[name]=function(){return Math[name].apply(null,[this].concat($A(arguments)));};});Number.implement(methods);})(['abs','acos','asin','atan','atan2','ceil','cos','exp','floor','log','max','min','pow','sin','sqrt','tan']);String.implement({test:function(regex,params){return((typeof regex=='string')?new RegExp(regex,params):regex).test(this);},contains:function(string,separator){return(separator)?(separator+this+separator).indexOf(separator+string+separator)>-1:this.indexOf(string)>-1;},trim:function(){return this.replace(/^\s+|\s+$/g,'');},clean:function(){return this.replace(/\s+/g,' ').trim();},camelCase:function(){return this.replace(/-\D/g,function(match){return match.charAt(1).toUpperCase();});},hyphenate:function(){return this.replace(/[A-Z]/g,function(match){return('-'+match.charAt(0).toLowerCase());});},capitalize:function(){return this.replace(/\b[a-z]/g,function(match){return match.toUpperCase();});},escapeRegExp:function(){return this.replace(/([-.*+?^${}()|[\]\/\\])/g,'\\$1');},toInt:function(base){return parseInt(this,base||10);},toFloat:function(){return parseFloat(this);},hexToRgb:function(array){var hex=this.match(/^#?(\w{1,2})(\w{1,2})(\w{1,2})$/);return(hex)?hex.slice(1).hexToRgb(array):null;},rgbToHex:function(array){var rgb=this.match(/\d{1,3}/g);return(rgb)?rgb.rgbToHex(array):null;},stripScripts:function(option){var scripts='';var text=this.replace(/<script[^>]*>([\s\S]*?)<\/script>/gi,function(){scripts+=arguments[1]+'\n';return'';});if(option===true)$exec(scripts);else if($type(option)=='function')option(scripts,text);return text;},substitute:function(object,regexp){return this.replace(regexp||(/\\?\{([^{}]+)\}/g),function(match,name){if(match.charAt(0)=='\\')return match.slice(1);return(object[name]!=undefined)?object[name]:'';});}});Hash.implement({has:Object.prototype.hasOwnProperty,keyOf:function(value){for(var key in this){if(this.hasOwnProperty(key)&&this[key]===value)return key;}
return null;},hasValue:function(value){return(Hash.keyOf(this,value)!==null);},extend:function(properties){Hash.each(properties||{},function(value,key){Hash.set(this,key,value);},this);return this;},combine:function(properties){Hash.each(properties||{},function(value,key){Hash.include(this,key,value);},this);return this;},erase:function(key){if(this.hasOwnProperty(key))delete this[key];return this;},get:function(key){return(this.hasOwnProperty(key))?this[key]:null;},set:function(key,value){if(!this[key]||this.hasOwnProperty(key))this[key]=value;return this;},empty:function(){Hash.each(this,function(value,key){delete this[key];},this);return this;},include:function(key,value){if(this[key]==undefined)this[key]=value;return this;},map:function(fn,bind){var results=new Hash;Hash.each(this,function(value,key){results.set(key,fn.call(bind,value,key,this));},this);return results;},filter:function(fn,bind){var results=new Hash;Hash.each(this,function(value,key){if(fn.call(bind,value,key,this))results.set(key,value);},this);return results;},every:function(fn,bind){for(var key in this){if(this.hasOwnProperty(key)&&!fn.call(bind,this[key],key))return false;}
return true;},some:function(fn,bind){for(var key in this){if(this.hasOwnProperty(key)&&fn.call(bind,this[key],key))return true;}
return false;},getKeys:function(){var keys=[];Hash.each(this,function(value,key){keys.push(key);});return keys;},getValues:function(){var values=[];Hash.each(this,function(value){values.push(value);});return values;},toQueryString:function(base){var queryString=[];Hash.each(this,function(value,key){if(base)key=base+'['+key+']';var result;switch($type(value)){case'object':result=Hash.toQueryString(value,key);break;case'array':var qs={};value.each(function(val,i){qs[i]=val;});result=Hash.toQueryString(qs,key);break;default:result=key+'='+encodeURIComponent(value);}
if(value!=undefined)queryString.push(result);});return queryString.join('&');}});Hash.alias({keyOf:'indexOf',hasValue:'contains'});var Event=new Native({name:'Event',initialize:function(event,win){win=win||window;var doc=win.document;event=event||win.event;if(event.$extended)return event;this.$extended=true;var type=event.type;var target=event.target||event.srcElement;while(target&&target.nodeType==3)target=target.parentNode;if(type.test(/key/)){var code=event.which||event.keyCode;var key=Event.Keys.keyOf(code);if(type=='keydown'){var fKey=code-111;if(fKey>0&&fKey<13)key='f'+fKey;}
key=key||String.fromCharCode(code).toLowerCase();}else if(type.match(/(click|mouse|menu)/i)){doc=(!doc.compatMode||doc.compatMode=='CSS1Compat')?doc.html:doc.body;var page={x:event.pageX||event.clientX+doc.scrollLeft,y:event.pageY||event.clientY+doc.scrollTop};var client={x:(event.pageX)?event.pageX-win.pageXOffset:event.clientX,y:(event.pageY)?event.pageY-win.pageYOffset:event.clientY};if(type.match(/DOMMouseScroll|mousewheel/)){var wheel=(event.wheelDelta)?event.wheelDelta/120:-(event.detail||0)/3;}
var rightClick=(event.which==3)||(event.button==2);var related=null;if(type.match(/over|out/)){switch(type){case'mouseover':related=event.relatedTarget||event.fromElement;break;case'mouseout':related=event.relatedTarget||event.toElement;}
if(!(function(){while(related&&related.nodeType==3)related=related.parentNode;return true;}).create({attempt:Browser.Engine.gecko})())related=false;}}
return $extend(this,{event:event,type:type,page:page,client:client,rightClick:rightClick,wheel:wheel,relatedTarget:related,target:target,code:code,key:key,shift:event.shiftKey,control:event.ctrlKey,alt:event.altKey,meta:event.metaKey});}});Event.Keys=new Hash({'enter':13,'up':38,'down':40,'left':37,'right':39,'esc':27,'space':32,'backspace':8,'tab':9,'delete':46});Event.implement({stop:function(){return this.stopPropagation().preventDefault();},stopPropagation:function(){if(this.event.stopPropagation)this.event.stopPropagation();else this.event.cancelBubble=true;return this;},preventDefault:function(){if(this.event.preventDefault)this.event.preventDefault();else this.event.returnValue=false;return this;}});function Class(params){if(params instanceof Function)params={initialize:params};var newClass=function(){Object.reset(this);if(newClass._prototyping)return this;this._current=$empty;var value=(this.initialize)?this.initialize.apply(this,arguments):this;delete this._current;delete this.caller;return value;}.extend(this);newClass.implement(params);newClass.constructor=Class;newClass.prototype.constructor=newClass;return newClass;};Function.prototype.protect=function(){this._protected=true;return this;};Object.reset=function(object,key){if(key==null){for(var p in object)Object.reset(object,p);return object;}
delete object[key];switch($type(object[key])){case'object':var F=function(){};F.prototype=object[key];var i=new F;object[key]=Object.reset(i);break;case'array':object[key]=$unlink(object[key]);break;}
return object;};new Native({name:'Class',initialize:Class}).extend({instantiate:function(F){F._prototyping=true;var proto=new F;delete F._prototyping;return proto;},wrap:function(self,key,method){if(method._origin)method=method._origin;return function(){if(method._protected&&this._current==null)throw new Error('The method "'+key+'" cannot be called.');var caller=this.caller,current=this._current;this.caller=current;this._current=arguments.callee;var result=method.apply(this,arguments);this._current=current;this.caller=caller;return result;}.extend({_owner:self,_origin:method,_name:key});}});Class.implement({implement:function(key,value){if($type(key)=='object'){for(var p in key)this.implement(p,key[p]);return this;}
var mutator=Class.Mutators[key];if(mutator){value=mutator.call(this,value);if(value==null)return this;}
var proto=this.prototype;switch($type(value)){case'function':if(value._hidden)return this;proto[key]=Class.wrap(this,key,value);break;case'object':var previous=proto[key];if($type(previous)=='object')$mixin(previous,value);else proto[key]=$unlink(value);break;case'array':proto[key]=$unlink(value);break;default:proto[key]=value;}
return this;}});Class.Mutators={Extends:function(parent){this.parent=parent;this.prototype=Class.instantiate(parent);this.implement('parent',function(){var name=this.caller._name,previous=this.caller._owner.parent.prototype[name];if(!previous)throw new Error('The method "'+name+'" has no parent.');return previous.apply(this,arguments);}.protect());},Implements:function(items){$splat(items).each(function(item){if(item instanceof Function)item=Class.instantiate(item);this.implement(item);},this);}};var Chain=new Class({$chain:[],chain:function(){this.$chain.extend(Array.flatten(arguments));return this;},callChain:function(){return(this.$chain.length)?this.$chain.shift().apply(this,arguments):false;},clearChain:function(){this.$chain.empty();return this;}});var Events=new Class({$events:{},addEvent:function(type,fn,internal){type=Events.removeOn(type);if(fn!=$empty){this.$events[type]=this.$events[type]||[];this.$events[type].include(fn);if(internal)fn.internal=true;}
return this;},addEvents:function(events){for(var type in events)this.addEvent(type,events[type]);return this;},fireEvent:function(type,args,delay){type=Events.removeOn(type);if(!this.$events||!this.$events[type])return this;this.$events[type].each(function(fn){fn.create({'bind':this,'delay':delay,'arguments':args})();},this);return this;},removeEvent:function(type,fn){type=Events.removeOn(type);if(!this.$events[type])return this;if(!fn.internal)this.$events[type].erase(fn);return this;},removeEvents:function(events){var type;if($type(events)=='object'){for(type in events)this.removeEvent(type,events[type]);return this;}
if(events)events=Events.removeOn(events);for(type in this.$events){if(events&&events!=type)continue;var fns=this.$events[type];for(var i=fns.length;i--;i)this.removeEvent(type,fns[i]);}
return this;}});Events.removeOn=function(string){return string.replace(/^on([A-Z])/,function(full,first){return first.toLowerCase();});};var Options=new Class({setOptions:function(){this.options=$merge.run([this.options].extend(arguments));if(!this.addEvent)return this;for(var option in this.options){if($type(this.options[option])!='function'||!(/^on[A-Z]/).test(option))continue;this.addEvent(option,this.options[option]);delete this.options[option];}
return this;}});var Element=new Native({name:'Element',legacy:window.Element,initialize:function(tag,props){var konstructor=Element.Constructors.get(tag);if(konstructor)return konstructor(props);if(typeof tag=='string')return document.newElement(tag,props);return document.id(tag).set(props);},afterImplement:function(key,value){Element.Prototype[key]=value;if(Array[key])return;Elements.implement(key,function(){var items=[],elements=true;for(var i=0,j=this.length;i<j;i++){var returns=this[i][key].apply(this[i],arguments);items.push(returns);if(elements)elements=($type(returns)=='element');}
return(elements)?new Elements(items):items;});}});Element.Prototype={$family:{name:'element'}};Element.Constructors=new Hash;var IFrame=new Native({name:'IFrame',generics:false,initialize:function(){var params=Array.link(arguments,{properties:Object.type,iframe:$defined});var props=params.properties||{};var iframe=document.id(params.iframe);var onload=props.onload||$empty;delete props.onload;props.id=props.name=$pick(props.id,props.name,iframe?(iframe.id||iframe.name):'IFrame_'+$time());iframe=new Element(iframe||'iframe',props);var onFrameLoad=function(){var host=$try(function(){return iframe.contentWindow.location.host;});if(!host||host==window.location.host){var win=new Window(iframe.contentWindow);new Document(iframe.contentWindow.document);$extend(win.Element.prototype,Element.Prototype);}
onload.call(iframe.contentWindow,iframe.contentWindow.document);};var contentWindow=$try(function(){return iframe.contentWindow;});((contentWindow&&contentWindow.document.body)||window.frames[props.id])?onFrameLoad():iframe.addListener('load',onFrameLoad);return iframe;}});var Elements=new Native({initialize:function(elements,options){options=$extend({ddup:true,cash:true},options);elements=elements||[];if(options.ddup||options.cash){var uniques={},returned=[];for(var i=0,l=elements.length;i<l;i++){var el=document.id(elements[i],!options.cash);if(options.ddup){if(uniques[el.uid])continue;uniques[el.uid]=true;}
if(el)returned.push(el);}
elements=returned;}
return(options.cash)?$extend(elements,this):elements;}});Elements.implement({filter:function(filter,bind){if(!filter)return this;return new Elements(Array.filter(this,(typeof filter=='string')?function(item){return item.match(filter);}:filter,bind));}});Document.implement({newElement:function(tag,props){if(Browser.Engine.trident&&props){['name','type','checked'].each(function(attribute){if(!props[attribute])return;tag+=' '+attribute+'="'+props[attribute]+'"';if(attribute!='checked')delete props[attribute];});tag='<'+tag+'>';}
return document.id(this.createElement(tag)).set(props);},newTextNode:function(text){return this.createTextNode(text);},getDocument:function(){return this;},getWindow:function(){return this.window;},id:(function(){var types={string:function(id,nocash,doc){id=doc.getElementById(id);return(id)?types.element(id,nocash):null;},element:function(el,nocash){$uid(el);if(!nocash&&!el.$family&&!(/^object|embed$/i).test(el.tagName)){var proto=Element.Prototype;for(var p in proto)el[p]=proto[p];};return el;},object:function(obj,nocash,doc){if(obj.toElement)return types.element(obj.toElement(doc),nocash);return null;}};types.textnode=types.whitespace=types.window=types.document=$arguments(0);return function(el,nocash,doc){if(el&&el.$family&&el.uid)return el;var type=$type(el);return(types[type])?types[type](el,nocash,doc||document):null;};})()});if(window.$==null)Window.implement({$:function(el,nc){return document.id(el,nc,this.document);}});Window.implement({$$:function(selector){if(arguments.length==1&&typeof selector=='string')return this.document.getElements(selector);var elements=[];var args=Array.flatten(arguments);for(var i=0,l=args.length;i<l;i++){var item=args[i];switch($type(item)){case'element':elements.push(item);break;case'string':elements.extend(this.document.getElements(item,true));}}
return new Elements(elements);},getDocument:function(){return this.document;},getWindow:function(){return this;}});Native.implement([Element,Document],{getElement:function(selector,nocash){return document.id(this.getElements(selector,true)[0]||null,nocash);},getElements:function(tags,nocash){tags=tags.split(',');var elements=[];var ddup=(tags.length>1);tags.each(function(tag){var partial=this.getElementsByTagName(tag.trim());(ddup)?elements.extend(partial):elements=partial;},this);return new Elements(elements,{ddup:ddup,cash:!nocash});}});(function(){var collected={},storage={};var props={input:'checked',option:'selected',textarea:(Browser.Engine.webkit&&Browser.Engine.version<420)?'innerHTML':'value'};var get=function(uid){return(storage[uid]||(storage[uid]={}));};var clean=function(item,retain){if(!item)return;var uid=item.uid;if(Browser.Engine.trident){if(item.clearAttributes){var clone=retain&&item.cloneNode(false);item.clearAttributes();if(clone)item.mergeAttributes(clone);}else if(item.removeEvents){item.removeEvents();}
if((/object/i).test(item.tagName)){for(var p in item){if(typeof item[p]=='function')item[p]=$empty;}
Element.dispose(item);}}
if(!uid)return;collected[uid]=storage[uid]=null;};var purge=function(){Hash.each(collected,clean);if(Browser.Engine.trident)$A(document.getElementsByTagName('object')).each(clean);if(window.CollectGarbage)CollectGarbage();collected=storage=null;};var walk=function(element,walk,start,match,all,nocash){var el=element[start||walk];var elements=[];while(el){if(el.nodeType==1&&(!match||Element.match(el,match))){if(!all)return document.id(el,nocash);elements.push(el);}
el=el[walk];}
return(all)?new Elements(elements,{ddup:false,cash:!nocash}):null;};var attributes={'html':'innerHTML','class':'className','for':'htmlFor','defaultValue':'defaultValue','text':(Browser.Engine.trident||(Browser.Engine.webkit&&Browser.Engine.version<420))?'innerText':'textContent'};var bools=['compact','nowrap','ismap','declare','noshade','checked','disabled','readonly','multiple','selected','noresize','defer'];var camels=['value','type','defaultValue','accessKey','cellPadding','cellSpacing','colSpan','frameBorder','maxLength','readOnly','rowSpan','tabIndex','useMap'];bools=bools.associate(bools);Hash.extend(attributes,bools);Hash.extend(attributes,camels.associate(camels.map(String.toLowerCase)));var inserters={before:function(context,element){if(element.parentNode)element.parentNode.insertBefore(context,element);},after:function(context,element){if(!element.parentNode)return;var next=element.nextSibling;(next)?element.parentNode.insertBefore(context,next):element.parentNode.appendChild(context);},bottom:function(context,element){element.appendChild(context);},top:function(context,element){var first=element.firstChild;(first)?element.insertBefore(context,first):element.appendChild(context);}};inserters.inside=inserters.bottom;Hash.each(inserters,function(inserter,where){where=where.capitalize();Element.implement('inject'+where,function(el){inserter(this,document.id(el,true));return this;});Element.implement('grab'+where,function(el){inserter(document.id(el,true),this);return this;});});Element.implement({set:function(prop,value){switch($type(prop)){case'object':for(var p in prop)this.set(p,prop[p]);break;case'string':var property=Element.Properties.get(prop);(property&&property.set)?property.set.apply(this,Array.slice(arguments,1)):this.setProperty(prop,value);}
return this;},get:function(prop){var property=Element.Properties.get(prop);return(property&&property.get)?property.get.apply(this,Array.slice(arguments,1)):this.getProperty(prop);},erase:function(prop){var property=Element.Properties.get(prop);(property&&property.erase)?property.erase.apply(this):this.removeProperty(prop);return this;},setProperty:function(attribute,value){var key=attributes[attribute];if(value==undefined)return this.removeProperty(attribute);if(key&&bools[attribute])value=!!value;(key)?this[key]=value:this.setAttribute(attribute,''+value);return this;},setProperties:function(attributes){for(var attribute in attributes)this.setProperty(attribute,attributes[attribute]);return this;},getProperty:function(attribute){var key=attributes[attribute];var value=(key)?this[key]:this.getAttribute(attribute,2);return(bools[attribute])?!!value:(key)?value:value||null;},getProperties:function(){var args=$A(arguments);return args.map(this.getProperty,this).associate(args);},removeProperty:function(attribute){var key=attributes[attribute];(key)?this[key]=(key&&bools[attribute])?false:'':this.removeAttribute(attribute);return this;},removeProperties:function(){Array.each(arguments,this.removeProperty,this);return this;},hasClass:function(className){return this.className.contains(className,' ');},addClass:function(className){if(!this.hasClass(className))this.className=(this.className+' '+className).clean();return this;},removeClass:function(className){this.className=this.className.replace(new RegExp('(^|\\s)'+className+'(?:\\s|$)'),'$1');return this;},toggleClass:function(className){return this.hasClass(className)?this.removeClass(className):this.addClass(className);},adopt:function(){Array.flatten(arguments).each(function(element){element=document.id(element,true);if(element)this.appendChild(element);},this);return this;},appendText:function(text,where){return this.grab(this.getDocument().newTextNode(text),where);},grab:function(el,where){inserters[where||'bottom'](document.id(el,true),this);return this;},inject:function(el,where){inserters[where||'bottom'](this,document.id(el,true));return this;},replaces:function(el){el=document.id(el,true);el.parentNode.replaceChild(this,el);return this;},wraps:function(el,where){el=document.id(el,true);return this.replaces(el).grab(el,where);},getPrevious:function(match,nocash){return walk(this,'previousSibling',null,match,false,nocash);},getAllPrevious:function(match,nocash){return walk(this,'previousSibling',null,match,true,nocash);},getNext:function(match,nocash){return walk(this,'nextSibling',null,match,false,nocash);},getAllNext:function(match,nocash){return walk(this,'nextSibling',null,match,true,nocash);},getFirst:function(match,nocash){return walk(this,'nextSibling','firstChild',match,false,nocash);},getLast:function(match,nocash){return walk(this,'previousSibling','lastChild',match,false,nocash);},getParent:function(match,nocash){return walk(this,'parentNode',null,match,false,nocash);},getParents:function(match,nocash){return walk(this,'parentNode',null,match,true,nocash);},getSiblings:function(match,nocash){return this.getParent().getChildren(match,nocash).erase(this);},getChildren:function(match,nocash){return walk(this,'nextSibling','firstChild',match,true,nocash);},getWindow:function(){return this.ownerDocument.window;},getDocument:function(){return this.ownerDocument;},getElementById:function(id,nocash){var el=this.ownerDocument.getElementById(id);if(!el)return null;for(var parent=el.parentNode;parent!=this;parent=parent.parentNode){if(!parent)return null;}
return document.id(el,nocash);},getSelected:function(){return new Elements($A(this.options).filter(function(option){return option.selected;}));},getComputedStyle:function(property){if(this.currentStyle)return this.currentStyle[property.camelCase()];var computed=this.getDocument().defaultView.getComputedStyle(this,null);return(computed)?computed.getPropertyValue([property.hyphenate()]):null;},toQueryString:function(){var queryString=[];this.getElements('input, select, textarea',true).each(function(el){if(!el.name||el.disabled||el.type=='submit'||el.type=='reset'||el.type=='file')return;var value=(el.tagName.toLowerCase()=='select')?Element.getSelected(el).map(function(opt){return opt.value;}):((el.type=='radio'||el.type=='checkbox')&&!el.checked)?null:el.value;$splat(value).each(function(val){if(typeof val!='undefined')queryString.push(el.name+'='+encodeURIComponent(val));});});return queryString.join('&');},clone:function(contents,keepid){contents=contents!==false;var clone=this.cloneNode(contents);var clean=function(node,element){if(!keepid)node.removeAttribute('id');if(Browser.Engine.trident){node.clearAttributes();node.mergeAttributes(element);node.removeAttribute('uid');if(node.options){var no=node.options,eo=element.options;for(var j=no.length;j--;)no[j].selected=eo[j].selected;}}
var prop=props[element.tagName.toLowerCase()];if(prop&&element[prop])node[prop]=element[prop];};if(contents){var ce=clone.getElementsByTagName('*'),te=this.getElementsByTagName('*');for(var i=ce.length;i--;)clean(ce[i],te[i]);}
clean(clone,this);return document.id(clone);},destroy:function(){Element.empty(this);Element.dispose(this);clean(this,true);return null;},empty:function(){$A(this.childNodes).each(function(node){Element.destroy(node);});return this;},dispose:function(){return(this.parentNode)?this.parentNode.removeChild(this):this;},hasChild:function(el){el=document.id(el,true);if(!el)return false;if(Browser.Engine.webkit&&Browser.Engine.version<420)return $A(this.getElementsByTagName(el.tagName)).contains(el);return(this.contains)?(this!=el&&this.contains(el)):!!(this.compareDocumentPosition(el)&16);},match:function(tag){return(!tag||(tag==this)||(Element.get(this,'tag')==tag));}});Native.implement([Element,Window,Document],{addListener:function(type,fn){if(type=='unload'){var old=fn,self=this;fn=function(){self.removeListener('unload',fn);old();};}else{collected[this.uid]=this;}
if(this.addEventListener)this.addEventListener(type,fn,false);else this.attachEvent('on'+type,fn);return this;},removeListener:function(type,fn){if(this.removeEventListener)this.removeEventListener(type,fn,false);else this.detachEvent('on'+type,fn);return this;},retrieve:function(property,dflt){var storage=get(this.uid),prop=storage[property];if(dflt!=undefined&&prop==undefined)prop=storage[property]=dflt;return $pick(prop);},store:function(property,value){var storage=get(this.uid);storage[property]=value;return this;},eliminate:function(property){var storage=get(this.uid);delete storage[property];return this;}});window.addListener('unload',purge);})();Element.Properties=new Hash;Element.Properties.style={set:function(style){this.style.cssText=style;},get:function(){return this.style.cssText;},erase:function(){this.style.cssText='';}};Element.Properties.tag={get:function(){return this.tagName.toLowerCase();}};Element.Properties.html=(function(){var wrapper=document.createElement('div');var translations={table:[1,'<table>','</table>'],select:[1,'<select>','</select>'],tbody:[2,'<table><tbody>','</tbody></table>'],tr:[3,'<table><tbody><tr>','</tr></tbody></table>']};translations.thead=translations.tfoot=translations.tbody;var html={set:function(){var html=Array.flatten(arguments).join('');var wrap=Browser.Engine.trident&&translations[this.get('tag')];if(wrap){var first=wrapper;first.innerHTML=wrap[1]+html+wrap[2];for(var i=wrap[0];i--;)first=first.firstChild;this.empty().adopt(first.childNodes);}else{this.innerHTML=html;}}};html.erase=html.set;return html;})();if(Browser.Engine.webkit&&Browser.Engine.version<420)Element.Properties.text={get:function(){if(this.innerText)return this.innerText;var temp=this.ownerDocument.newElement('div',{html:this.innerHTML}).inject(this.ownerDocument.body);var text=temp.innerText;temp.destroy();return text;}};Element.Properties.events={set:function(events){this.addEvents(events);}};Native.implement([Element,Window,Document],{addEvent:function(type,fn){var events=this.retrieve('events',{});events[type]=events[type]||{'keys':[],'values':[]};if(events[type].keys.contains(fn))return this;events[type].keys.push(fn);var realType=type,custom=Element.Events.get(type),condition=fn,self=this;if(custom){if(custom.onAdd)custom.onAdd.call(this,fn);if(custom.condition){condition=function(event){if(custom.condition.call(this,event))return fn.call(this,event);return true;};}
realType=custom.base||realType;}
var defn=function(){return fn.call(self);};var nativeEvent=Element.NativeEvents[realType];if(nativeEvent){if(nativeEvent==2){defn=function(event){event=new Event(event,self.getWindow());if(condition.call(self,event)===false)event.stop();};}
this.addListener(realType,defn);}
events[type].values.push(defn);return this;},removeEvent:function(type,fn){var events=this.retrieve('events');if(!events||!events[type])return this;var pos=events[type].keys.indexOf(fn);if(pos==-1)return this;events[type].keys.splice(pos,1);var value=events[type].values.splice(pos,1)[0];var custom=Element.Events.get(type);if(custom){if(custom.onRemove)custom.onRemove.call(this,fn);type=custom.base||type;}
return(Element.NativeEvents[type])?this.removeListener(type,value):this;},addEvents:function(events){for(var event in events)this.addEvent(event,events[event]);return this;},removeEvents:function(events){var type;if($type(events)=='object'){for(type in events)this.removeEvent(type,events[type]);return this;}
var attached=this.retrieve('events');if(!attached)return this;if(!events){for(type in attached)this.removeEvents(type);this.eliminate('events');}else if(attached[events]){while(attached[events].keys[0])this.removeEvent(events,attached[events].keys[0]);attached[events]=null;}
return this;},fireEvent:function(type,args,delay){var events=this.retrieve('events');if(!events||!events[type])return this;events[type].keys.each(function(fn){fn.create({'bind':this,'delay':delay,'arguments':args})();},this);return this;},cloneEvents:function(from,type){from=document.id(from);var fevents=from.retrieve('events');if(!fevents)return this;if(!type){for(var evType in fevents)this.cloneEvents(from,evType);}else if(fevents[type]){fevents[type].keys.each(function(fn){this.addEvent(type,fn);},this);}
return this;}});Element.NativeEvents={click:2,dblclick:2,mouseup:2,mousedown:2,contextmenu:2,mousewheel:2,DOMMouseScroll:2,mouseover:2,mouseout:2,mousemove:2,selectstart:2,selectend:2,keydown:2,keypress:2,keyup:2,focus:2,blur:2,change:2,reset:2,select:2,submit:2,load:1,unload:1,beforeunload:2,resize:1,move:1,DOMContentLoaded:1,readystatechange:1,error:1,abort:1,scroll:1};(function(){var $check=function(event){var related=event.relatedTarget;if(related==undefined)return true;if(related===false)return false;return($type(this)!='document'&&related!=this&&related.prefix!='xul'&&!this.hasChild(related));};Element.Events=new Hash({mouseenter:{base:'mouseover',condition:$check},mouseleave:{base:'mouseout',condition:$check},mousewheel:{base:(Browser.Engine.gecko)?'DOMMouseScroll':'mousewheel'}});})();Element.Properties.styles={set:function(styles){this.setStyles(styles);}};Element.Properties.opacity={set:function(opacity,novisibility){if(!novisibility){if(opacity==0){if(this.style.visibility!='hidden')this.style.visibility='hidden';}else{if(this.style.visibility!='visible')this.style.visibility='visible';}}
if(!this.currentStyle||!this.currentStyle.hasLayout)this.style.zoom=1;if(Browser.Engine.trident)this.style.filter=(opacity==1)?'':'alpha(opacity='+opacity*100+')';this.style.opacity=opacity;this.store('opacity',opacity);},get:function(){return this.retrieve('opacity',1);}};Element.implement({setOpacity:function(value){return this.set('opacity',value,true);},getOpacity:function(){return this.get('opacity');},setStyle:function(property,value){switch(property){case'opacity':return this.set('opacity',parseFloat(value));case'float':property=(Browser.Engine.trident)?'styleFloat':'cssFloat';}
property=property.camelCase();if($type(value)!='string'){var map=(Element.Styles.get(property)||'@').split(' ');value=$splat(value).map(function(val,i){if(!map[i])return'';return($type(val)=='number')?map[i].replace('@',Math.round(val)):val;}).join(' ');}else if(value==String(Number(value))){value=Math.round(value);}
this.style[property]=value;return this;},getStyle:function(property){switch(property){case'opacity':return this.get('opacity');case'float':property=(Browser.Engine.trident)?'styleFloat':'cssFloat';}
property=property.camelCase();var result=this.style[property];if(!$chk(result)){result=[];for(var style in Element.ShortStyles){if(property!=style)continue;for(var s in Element.ShortStyles[style])result.push(this.getStyle(s));return result.join(' ');}
result=this.getComputedStyle(property);}
if(result){result=String(result);var color=result.match(/rgba?\([\d\s,]+\)/);if(color)result=result.replace(color[0],color[0].rgbToHex());}
if(Browser.Engine.presto||(Browser.Engine.trident&&!$chk(parseInt(result,10)))){if(property.test(/^(height|width)$/)){var values=(property=='width')?['left','right']:['top','bottom'],size=0;values.each(function(value){size+=this.getStyle('border-'+value+'-width').toInt()+this.getStyle('padding-'+value).toInt();},this);return this['offset'+property.capitalize()]-size+'px';}
if((Browser.Engine.presto)&&String(result).test('px'))return result;if(property.test(/(border(.+)Width|margin|padding)/))return'0px';}
return result;},setStyles:function(styles){for(var style in styles)this.setStyle(style,styles[style]);return this;},getStyles:function(){var result={};Array.flatten(arguments).each(function(key){result[key]=this.getStyle(key);},this);return result;}});Element.Styles=new Hash({left:'@px',top:'@px',bottom:'@px',right:'@px',width:'@px',height:'@px',maxWidth:'@px',maxHeight:'@px',minWidth:'@px',minHeight:'@px',backgroundColor:'rgb(@, @, @)',backgroundPosition:'@px @px',color:'rgb(@, @, @)',fontSize:'@px',letterSpacing:'@px',lineHeight:'@px',clip:'rect(@px @px @px @px)',margin:'@px @px @px @px',padding:'@px @px @px @px',border:'@px @ rgb(@, @, @) @px @ rgb(@, @, @) @px @ rgb(@, @, @)',borderWidth:'@px @px @px @px',borderStyle:'@ @ @ @',borderColor:'rgb(@, @, @) rgb(@, @, @) rgb(@, @, @) rgb(@, @, @)',zIndex:'@','zoom':'@',fontWeight:'@',textIndent:'@px',opacity:'@'});Element.ShortStyles={margin:{},padding:{},border:{},borderWidth:{},borderStyle:{},borderColor:{}};['Top','Right','Bottom','Left'].each(function(direction){var Short=Element.ShortStyles;var All=Element.Styles;['margin','padding'].each(function(style){var sd=style+direction;Short[style][sd]=All[sd]='@px';});var bd='border'+direction;Short.border[bd]=All[bd]='@px @ rgb(@, @, @)';var bdw=bd+'Width',bds=bd+'Style',bdc=bd+'Color';Short[bd]={};Short.borderWidth[bdw]=Short[bd][bdw]=All[bdw]='@px';Short.borderStyle[bds]=Short[bd][bds]=All[bds]='@';Short.borderColor[bdc]=Short[bd][bdc]=All[bdc]='rgb(@, @, @)';});(function(){Element.implement({scrollTo:function(x,y){if(isBody(this)){this.getWindow().scrollTo(x,y);}else{this.scrollLeft=x;this.scrollTop=y;}
return this;},getSize:function(){if(isBody(this))return this.getWindow().getSize();return{x:this.offsetWidth,y:this.offsetHeight};},getScrollSize:function(){if(isBody(this))return this.getWindow().getScrollSize();return{x:this.scrollWidth,y:this.scrollHeight};},getScroll:function(){if(isBody(this))return this.getWindow().getScroll();return{x:this.scrollLeft,y:this.scrollTop};},getScrolls:function(){var element=this,position={x:0,y:0};while(element&&!isBody(element)){position.x+=element.scrollLeft;position.y+=element.scrollTop;element=element.parentNode;}
return position;},getOffsetParent:function(){var element=this;if(isBody(element))return null;if(!Browser.Engine.trident)return element.offsetParent;while((element=element.parentNode)&&!isBody(element)){if(styleString(element,'position')!='static')return element;}
return null;},getOffsets:function(){if(this.getBoundingClientRect){var bound=this.getBoundingClientRect(),html=document.id(this.getDocument().documentElement),htmlScroll=html.getScroll(),elemScrolls=this.getScrolls(),elemScroll=this.getScroll(),isFixed=(styleString(this,'position')=='fixed');return{x:bound.left.toInt()+elemScrolls.x-elemScroll.x+((isFixed)?0:htmlScroll.x)-html.clientLeft,y:bound.top.toInt()+elemScrolls.y-elemScroll.y+((isFixed)?0:htmlScroll.y)-html.clientTop};}
var element=this,position={x:0,y:0};if(isBody(this))return position;while(element&&!isBody(element)){position.x+=element.offsetLeft;position.y+=element.offsetTop;if(Browser.Engine.gecko){if(!borderBox(element)){position.x+=leftBorder(element);position.y+=topBorder(element);}
var parent=element.parentNode;if(parent&&styleString(parent,'overflow')!='visible'){position.x+=leftBorder(parent);position.y+=topBorder(parent);}}else if(element!=this&&Browser.Engine.webkit){position.x+=leftBorder(element);position.y+=topBorder(element);}
element=element.offsetParent;}
if(Browser.Engine.gecko&&!borderBox(this)){position.x-=leftBorder(this);position.y-=topBorder(this);}
return position;},getPosition:function(relative){if(isBody(this))return{x:0,y:0};var offset=this.getOffsets(),scroll=this.getScrolls();var position={x:offset.x-scroll.x,y:offset.y-scroll.y};var relativePosition=(relative&&(relative=document.id(relative)))?relative.getPosition():{x:0,y:0};return{x:position.x-relativePosition.x,y:position.y-relativePosition.y};},getCoordinates:function(element){if(isBody(this))return this.getWindow().getCoordinates();var position=this.getPosition(element),size=this.getSize();var obj={left:position.x,top:position.y,width:size.x,height:size.y};obj.right=obj.left+obj.width;obj.bottom=obj.top+obj.height;return obj;},computePosition:function(obj){return{left:obj.x-styleNumber(this,'margin-left'),top:obj.y-styleNumber(this,'margin-top')};},setPosition:function(obj){return this.setStyles(this.computePosition(obj));}});Native.implement([Document,Window],{getSize:function(){if(Browser.Engine.presto||Browser.Engine.webkit){var win=this.getWindow();return{x:win.innerWidth,y:win.innerHeight};}
var doc=getCompatElement(this);return{x:doc.clientWidth,y:doc.clientHeight};},getScroll:function(){var win=this.getWindow(),doc=getCompatElement(this);return{x:win.pageXOffset||doc.scrollLeft,y:win.pageYOffset||doc.scrollTop};},getScrollSize:function(){var doc=getCompatElement(this),min=this.getSize();return{x:Math.max(doc.scrollWidth,min.x),y:Math.max(doc.scrollHeight,min.y)};},getPosition:function(){return{x:0,y:0};},getCoordinates:function(){var size=this.getSize();return{top:0,left:0,bottom:size.y,right:size.x,height:size.y,width:size.x};}});var styleString=Element.getComputedStyle;function styleNumber(element,style){return styleString(element,style).toInt()||0;};function borderBox(element){return styleString(element,'-moz-box-sizing')=='border-box';};function topBorder(element){return styleNumber(element,'border-top-width');};function leftBorder(element){return styleNumber(element,'border-left-width');};function isBody(element){return(/^(?:body|html)$/i).test(element.tagName);};function getCompatElement(element){var doc=element.getDocument();return(!doc.compatMode||doc.compatMode=='CSS1Compat')?doc.html:doc.body;};})();Element.alias('setPosition','position');Native.implement([Window,Document,Element],{getHeight:function(){return this.getSize().y;},getWidth:function(){return this.getSize().x;},getScrollTop:function(){return this.getScroll().y;},getScrollLeft:function(){return this.getScroll().x;},getScrollHeight:function(){return this.getScrollSize().y;},getScrollWidth:function(){return this.getScrollSize().x;},getTop:function(){return this.getPosition().y;},getLeft:function(){return this.getPosition().x;}});Native.implement([Document,Element],{getElements:function(expression,nocash){expression=expression.split(',');var items,local={};for(var i=0,l=expression.length;i<l;i++){var selector=expression[i],elements=Selectors.Utils.search(this,selector,local);if(i!=0&&elements.item)elements=$A(elements);items=(i==0)?elements:(items.item)?$A(items).concat(elements):items.concat(elements);}
return new Elements(items,{ddup:(expression.length>1),cash:!nocash});}});Element.implement({match:function(selector){if(!selector||(selector==this))return true;var tagid=Selectors.Utils.parseTagAndID(selector);var tag=tagid[0],id=tagid[1];if(!Selectors.Filters.byID(this,id)||!Selectors.Filters.byTag(this,tag))return false;var parsed=Selectors.Utils.parseSelector(selector);return(parsed)?Selectors.Utils.filter(this,parsed,{}):true;}});var Selectors={Cache:{nth:{},parsed:{}}};Selectors.RegExps={id:(/#([\w-]+)/),tag:(/^(\w+|\*)/),quick:(/^(\w+|\*)$/),splitter:(/\s*([+>~\s])\s*([a-zA-Z#.*:\[])/g),combined:(/\.([\w-]+)|\[(\w+)(?:([!*^$~|]?=)(["']?)([^\4]*?)\4)?\]|:([\w-]+)(?:\(["']?(.*?)?["']?\)|$)/g)};Selectors.Utils={chk:function(item,uniques){if(!uniques)return true;var uid=$uid(item);if(!uniques[uid])return uniques[uid]=true;return false;},parseNthArgument:function(argument){if(Selectors.Cache.nth[argument])return Selectors.Cache.nth[argument];var parsed=argument.match(/^([+-]?\d*)?([a-z]+)?([+-]?\d*)?$/);if(!parsed)return false;var inta=parseInt(parsed[1],10);var a=(inta||inta===0)?inta:1;var special=parsed[2]||false;var b=parseInt(parsed[3],10)||0;if(a!=0){b--;while(b<1)b+=a;while(b>=a)b-=a;}else{a=b;special='index';}
switch(special){case'n':parsed={a:a,b:b,special:'n'};break;case'odd':parsed={a:2,b:0,special:'n'};break;case'even':parsed={a:2,b:1,special:'n'};break;case'first':parsed={a:0,special:'index'};break;case'last':parsed={special:'last-child'};break;case'only':parsed={special:'only-child'};break;default:parsed={a:(a-1),special:'index'};}
return Selectors.Cache.nth[argument]=parsed;},parseSelector:function(selector){if(Selectors.Cache.parsed[selector])return Selectors.Cache.parsed[selector];var m,parsed={classes:[],pseudos:[],attributes:[]};while((m=Selectors.RegExps.combined.exec(selector))){var cn=m[1],an=m[2],ao=m[3],av=m[5],pn=m[6],pa=m[7];if(cn){parsed.classes.push(cn);}else if(pn){var parser=Selectors.Pseudo.get(pn);if(parser)parsed.pseudos.push({parser:parser,argument:pa});else parsed.attributes.push({name:pn,operator:'=',value:pa});}else if(an){parsed.attributes.push({name:an,operator:ao,value:av});}}
if(!parsed.classes.length)delete parsed.classes;if(!parsed.attributes.length)delete parsed.attributes;if(!parsed.pseudos.length)delete parsed.pseudos;if(!parsed.classes&&!parsed.attributes&&!parsed.pseudos)parsed=null;return Selectors.Cache.parsed[selector]=parsed;},parseTagAndID:function(selector){var tag=selector.match(Selectors.RegExps.tag);var id=selector.match(Selectors.RegExps.id);return[(tag)?tag[1]:'*',(id)?id[1]:false];},filter:function(item,parsed,local){var i;if(parsed.classes){for(i=parsed.classes.length;i--;i){var cn=parsed.classes[i];if(!Selectors.Filters.byClass(item,cn))return false;}}
if(parsed.attributes){for(i=parsed.attributes.length;i--;i){var att=parsed.attributes[i];if(!Selectors.Filters.byAttribute(item,att.name,att.operator,att.value))return false;}}
if(parsed.pseudos){for(i=parsed.pseudos.length;i--;i){var psd=parsed.pseudos[i];if(!Selectors.Filters.byPseudo(item,psd.parser,psd.argument,local))return false;}}
return true;},getByTagAndID:function(ctx,tag,id){if(id){var item=(ctx.getElementById)?ctx.getElementById(id,true):Element.getElementById(ctx,id,true);return(item&&Selectors.Filters.byTag(item,tag))?[item]:[];}else{return ctx.getElementsByTagName(tag);}},search:function(self,expression,local){var splitters=[];var selectors=expression.trim().replace(Selectors.RegExps.splitter,function(m0,m1,m2){splitters.push(m1);return':)'+m2;}).split(':)');var items,filtered,item;for(var i=0,l=selectors.length;i<l;i++){var selector=selectors[i];if(i==0&&Selectors.RegExps.quick.test(selector)){items=self.getElementsByTagName(selector);continue;}
var splitter=splitters[i-1];var tagid=Selectors.Utils.parseTagAndID(selector);var tag=tagid[0],id=tagid[1];if(i==0){items=Selectors.Utils.getByTagAndID(self,tag,id);}else{var uniques={},found=[];for(var j=0,k=items.length;j<k;j++)found=Selectors.Getters[splitter](found,items[j],tag,id,uniques);items=found;}
var parsed=Selectors.Utils.parseSelector(selector);if(parsed){filtered=[];for(var m=0,n=items.length;m<n;m++){item=items[m];if(Selectors.Utils.filter(item,parsed,local))filtered.push(item);}
items=filtered;}}
return items;}};Selectors.Getters={' ':function(found,self,tag,id,uniques){var items=Selectors.Utils.getByTagAndID(self,tag,id);for(var i=0,l=items.length;i<l;i++){var item=items[i];if(Selectors.Utils.chk(item,uniques))found.push(item);}
return found;},'>':function(found,self,tag,id,uniques){var children=Selectors.Utils.getByTagAndID(self,tag,id);for(var i=0,l=children.length;i<l;i++){var child=children[i];if(child.parentNode==self&&Selectors.Utils.chk(child,uniques))found.push(child);}
return found;},'+':function(found,self,tag,id,uniques){while((self=self.nextSibling)){if(self.nodeType==1){if(Selectors.Utils.chk(self,uniques)&&Selectors.Filters.byTag(self,tag)&&Selectors.Filters.byID(self,id))found.push(self);break;}}
return found;},'~':function(found,self,tag,id,uniques){while((self=self.nextSibling)){if(self.nodeType==1){if(!Selectors.Utils.chk(self,uniques))break;if(Selectors.Filters.byTag(self,tag)&&Selectors.Filters.byID(self,id))found.push(self);}}
return found;}};Selectors.Filters={byTag:function(self,tag){return(tag=='*'||(self.tagName&&self.tagName.toLowerCase()==tag));},byID:function(self,id){return(!id||(self.id&&self.id==id));},byClass:function(self,klass){return(self.className&&self.className.contains&&self.className.contains(klass,' '));},byPseudo:function(self,parser,argument,local){return parser.call(self,argument,local);},byAttribute:function(self,name,operator,value){var result=Element.prototype.getProperty.call(self,name);if(!result)return(operator=='!=');if(!operator||value==undefined)return true;switch(operator){case'=':return(result==value);case'*=':return(result.contains(value));case'^=':return(result.substr(0,value.length)==value);case'$=':return(result.substr(result.length-value.length)==value);case'!=':return(result!=value);case'~=':return result.contains(value,' ');case'|=':return result.contains(value,'-');}
return false;}};Selectors.Pseudo=new Hash({checked:function(){return this.checked;},empty:function(){return!(this.innerText||this.textContent||'').length;},not:function(selector){return!Element.match(this,selector);},contains:function(text){return(this.innerText||this.textContent||'').contains(text);},'first-child':function(){return Selectors.Pseudo.index.call(this,0);},'last-child':function(){var element=this;while((element=element.nextSibling)){if(element.nodeType==1)return false;}
return true;},'only-child':function(){var prev=this;while((prev=prev.previousSibling)){if(prev.nodeType==1)return false;}
var next=this;while((next=next.nextSibling)){if(next.nodeType==1)return false;}
return true;},'nth-child':function(argument,local){argument=(argument==undefined)?'n':argument;var parsed=Selectors.Utils.parseNthArgument(argument);if(parsed.special!='n')return Selectors.Pseudo[parsed.special].call(this,parsed.a,local);var count=0;local.positions=local.positions||{};var uid=$uid(this);if(!local.positions[uid]){var self=this;while((self=self.previousSibling)){if(self.nodeType!=1)continue;count++;var position=local.positions[$uid(self)];if(position!=undefined){count=position+count;break;}}
local.positions[uid]=count;}
return(local.positions[uid]%parsed.a==parsed.b);},index:function(index){var element=this,count=0;while((element=element.previousSibling)){if(element.nodeType==1&&++count>index)return false;}
return(count==index);},even:function(argument,local){return Selectors.Pseudo['nth-child'].call(this,'2n+1',local);},odd:function(argument,local){return Selectors.Pseudo['nth-child'].call(this,'2n',local);},selected:function(){return this.selected;},enabled:function(){return(this.disabled===false);}});Element.Events.domready={onAdd:function(fn){if(Browser.loaded)fn.call(this);}};(function(){var domready=function(){if(Browser.loaded)return;Browser.loaded=true;window.fireEvent('domready');document.fireEvent('domready');};window.addEvent('load',domready);if(Browser.Engine.trident){var temp=document.createElement('div');(function(){($try(function(){temp.doScroll();return document.id(temp).inject(document.body).set('html','temp').dispose();}))?domready():arguments.callee.delay(50);})();}else if(Browser.Engine.webkit&&Browser.Engine.version<525){(function(){(['loaded','complete'].contains(document.readyState))?domready():arguments.callee.delay(50);})();}else{document.addEvent('DOMContentLoaded',domready);}})();var JSON=new Hash(this.JSON&&{stringify:JSON.stringify,parse:JSON.parse}).extend({$specialChars:{'\b':'\\b','\t':'\\t','\n':'\\n','\f':'\\f','\r':'\\r','"':'\\"','\\':'\\\\'},$replaceChars:function(chr){return JSON.$specialChars[chr]||'\\u00'+Math.floor(chr.charCodeAt()/16).toString(16)+(chr.charCodeAt()%16).toString(16);},encode:function(obj){switch($type(obj)){case'string':return'"'+obj.replace(/[\x00-\x1f\\"]/g,JSON.$replaceChars)+'"';case'array':return'['+String(obj.map(JSON.encode).clean())+']';case'object':case'hash':var string=[];Hash.each(obj,function(value,key){var json=JSON.encode(value);if(json)string.push(JSON.encode(key)+':'+json);});return'{'+string+'}';case'number':case'boolean':return String(obj);case false:return'null';}
return null;},decode:function(string,secure){if($type(string)!='string'||!string.length)return null;if(secure&&!(/^[,:{}\[\]0-9.\-+Eaeflnr-u \n\r\t]*$/).test(string.replace(/\\./g,'@').replace(/"[^"\\\n\r]*"/g,'')))return null;return eval('('+string+')');}});Native.implement([Hash,Array,String,Number],{toJSON:function(){return JSON.encode(this);}});var Cookie=new Class({Implements:Options,options:{path:false,domain:false,duration:false,secure:false,document:document},initialize:function(key,options){this.key=key;this.setOptions(options);},write:function(value){value=encodeURIComponent(value);if(this.options.domain)value+='; domain='+this.options.domain;if(this.options.path)value+='; path='+this.options.path;if(this.options.duration){var date=new Date();date.setTime(date.getTime()+this.options.duration*24*60*60*1000);value+='; expires='+date.toGMTString();}
if(this.options.secure)value+='; secure';this.options.document.cookie=this.key+'='+value;return this;},read:function(){var value=this.options.document.cookie.match('(?:^|;)\\s*'+this.key.escapeRegExp()+'=([^;]*)');return(value)?decodeURIComponent(value[1]):null;},dispose:function(){new Cookie(this.key,$merge(this.options,{duration:-1})).write('');return this;}});Cookie.write=function(key,value,options){return new Cookie(key,options).write(value);};Cookie.read=function(key){return new Cookie(key).read();};Cookie.dispose=function(key,options){return new Cookie(key,options).dispose();};var Swiff=new Class({Implements:[Options],options:{id:null,height:1,width:1,container:null,properties:{},params:{quality:'high',allowScriptAccess:'always',wMode:'transparent',swLiveConnect:true},callBacks:{},vars:{}},toElement:function(){return this.object;},initialize:function(path,options){this.instance='Swiff_'+$time();this.setOptions(options);options=this.options;var id=this.id=options.id||this.instance;var container=document.id(options.container);Swiff.CallBacks[this.instance]={};var params=options.params,vars=options.vars,callBacks=options.callBacks;var properties=$extend({height:options.height,width:options.width},options.properties);var self=this;for(var callBack in callBacks){Swiff.CallBacks[this.instance][callBack]=(function(option){return function(){return option.apply(self.object,arguments);};})(callBacks[callBack]);vars[callBack]='Swiff.CallBacks.'+this.instance+'.'+callBack;}
params.flashVars=Hash.toQueryString(vars);if(Browser.Engine.trident){properties.classid='clsid:D27CDB6E-AE6D-11cf-96B8-444553540000';params.movie=path;}else{properties.type='application/x-shockwave-flash';properties.data=path;}
var build='<object id="'+id+'"';for(var property in properties)build+=' '+property+'="'+properties[property]+'"';build+='>';for(var param in params){if(params[param])build+='<param name="'+param+'" value="'+params[param]+'" />';}
build+='</object>';this.object=((container)?container.empty():new Element('div')).set('html',build).firstChild;},replaces:function(element){element=document.id(element,true);element.parentNode.replaceChild(this.toElement(),element);return this;},inject:function(element){document.id(element,true).appendChild(this.toElement());return this;},remote:function(){return Swiff.remote.apply(Swiff,[this.toElement()].extend(arguments));}});Swiff.CallBacks={};Swiff.remote=function(obj,fn){var rs=obj.CallFunction('<invoke name="'+fn+'" returntype="javascript">'+__flash__argumentsToXML(arguments,2)+'</invoke>');return eval(rs);};var Fx=new Class({Implements:[Chain,Events,Options],options:{fps:50,unit:false,duration:500,link:'ignore'},initialize:function(options){this.subject=this.subject||this;this.setOptions(options);this.options.duration=Fx.Durations[this.options.duration]||this.options.duration.toInt();var wait=this.options.wait;if(wait===false)this.options.link='cancel';},getTransition:function(){return function(p){return-(Math.cos(Math.PI*p)-1)/2;};},step:function(){var time=$time();if(time<this.time+this.options.duration){var delta=this.transition((time-this.time)/this.options.duration);this.set(this.compute(this.from,this.to,delta));}else{this.set(this.compute(this.from,this.to,1));this.complete();}},set:function(now){return now;},compute:function(from,to,delta){return Fx.compute(from,to,delta);},check:function(){if(!this.timer)return true;switch(this.options.link){case'cancel':this.cancel();return true;case'chain':this.chain(this.caller.bind(this,arguments));return false;}
return false;},start:function(from,to){if(!this.check(from,to))return this;this.from=from;this.to=to;this.time=0;this.transition=this.getTransition();this.startTimer();this.onStart();return this;},complete:function(){if(this.stopTimer())this.onComplete();return this;},cancel:function(){if(this.stopTimer())this.onCancel();return this;},onStart:function(){this.fireEvent('start',this.subject);},onComplete:function(){this.fireEvent('complete',this.subject);if(!this.callChain())this.fireEvent('chainComplete',this.subject);},onCancel:function(){this.fireEvent('cancel',this.subject).clearChain();},pause:function(){this.stopTimer();return this;},resume:function(){this.startTimer();return this;},stopTimer:function(){if(!this.timer)return false;this.time=$time()-this.time;this.timer=$clear(this.timer);return true;},startTimer:function(){if(this.timer)return false;this.time=$time()-this.time;this.timer=this.step.periodical(Math.round(1000/this.options.fps),this);return true;}});Fx.compute=function(from,to,delta){return(to-from)*delta+from;};Fx.Durations={'short':250,'normal':500,'long':1000};Fx.CSS=new Class({Extends:Fx,prepare:function(element,property,values){values=$splat(values);var values1=values[1];if(!$chk(values1)){values[1]=values[0];values[0]=element.getStyle(property);}
var parsed=values.map(this.parse);return{from:parsed[0],to:parsed[1]};},parse:function(value){value=$lambda(value)();value=(typeof value=='string')?value.split(' '):$splat(value);return value.map(function(val){val=String(val);var found=false;Fx.CSS.Parsers.each(function(parser,key){if(found)return;var parsed=parser.parse(val);if($chk(parsed))found={value:parsed,parser:parser};});found=found||{value:val,parser:Fx.CSS.Parsers.String};return found;});},compute:function(from,to,delta){var computed=[];(Math.min(from.length,to.length)).times(function(i){computed.push({value:from[i].parser.compute(from[i].value,to[i].value,delta),parser:from[i].parser});});computed.$family={name:'fx:css:value'};return computed;},serve:function(value,unit){if($type(value)!='fx:css:value')value=this.parse(value);var returned=[];value.each(function(bit){returned=returned.concat(bit.parser.serve(bit.value,unit));});return returned;},render:function(element,property,value,unit){element.setStyle(property,this.serve(value,unit));},search:function(selector){if(Fx.CSS.Cache[selector])return Fx.CSS.Cache[selector];var to={};Array.each(document.styleSheets,function(sheet,j){var href=sheet.href;if(href&&href.contains('://')&&!href.contains(document.domain))return;var rules=sheet.rules||sheet.cssRules;Array.each(rules,function(rule,i){if(!rule.style)return;var selectorText=(rule.selectorText)?rule.selectorText.replace(/^\w+/,function(m){return m.toLowerCase();}):null;if(!selectorText||!selectorText.test('^'+selector+'$'))return;Element.Styles.each(function(value,style){if(!rule.style[style]||Element.ShortStyles[style])return;value=String(rule.style[style]);to[style]=(value.test(/^rgb/))?value.rgbToHex():value;});});});return Fx.CSS.Cache[selector]=to;}});Fx.CSS.Cache={};Fx.CSS.Parsers=new Hash({Color:{parse:function(value){if(value.match(/^#[0-9a-f]{3,6}$/i))return value.hexToRgb(true);return((value=value.match(/(\d+),\s*(\d+),\s*(\d+)/)))?[value[1],value[2],value[3]]:false;},compute:function(from,to,delta){return from.map(function(value,i){return Math.round(Fx.compute(from[i],to[i],delta));});},serve:function(value){return value.map(Number);}},Number:{parse:parseFloat,compute:Fx.compute,serve:function(value,unit){return(unit)?value+unit:value;}},String:{parse:$lambda(false),compute:$arguments(1),serve:$arguments(0)}});Fx.Tween=new Class({Extends:Fx.CSS,initialize:function(element,options){this.element=this.subject=document.id(element);this.parent(options);},set:function(property,now){if(arguments.length==1){now=property;property=this.property||this.options.property;}
this.render(this.element,property,now,this.options.unit);return this;},start:function(property,from,to){if(!this.check(property,from,to))return this;var args=Array.flatten(arguments);this.property=this.options.property||args.shift();var parsed=this.prepare(this.element,this.property,args);return this.parent(parsed.from,parsed.to);}});Element.Properties.tween={set:function(options){var tween=this.retrieve('tween');if(tween)tween.cancel();return this.eliminate('tween').store('tween:options',$extend({link:'cancel'},options));},get:function(options){if(options||!this.retrieve('tween')){if(options||!this.retrieve('tween:options'))this.set('tween',options);this.store('tween',new Fx.Tween(this,this.retrieve('tween:options')));}
return this.retrieve('tween');}};Element.implement({tween:function(property,from,to){this.get('tween').start(arguments);return this;},fade:function(how){var fade=this.get('tween'),o='opacity',toggle;how=$pick(how,'toggle');switch(how){case'in':fade.start(o,1);break;case'out':fade.start(o,0);break;case'show':fade.set(o,1);break;case'hide':fade.set(o,0);break;case'toggle':var flag=this.retrieve('fade:flag',this.get('opacity')==1);fade.start(o,(flag)?0:1);this.store('fade:flag',!flag);toggle=true;break;default:fade.start(o,arguments);}
if(!toggle)this.eliminate('fade:flag');return this;},highlight:function(start,end){if(!end){end=this.retrieve('highlight:original',this.getStyle('background-color'));end=(end=='transparent')?'#fff':end;}
var tween=this.get('tween');tween.start('background-color',start||'#ffff88',end).chain(function(){this.setStyle('background-color',this.retrieve('highlight:original'));tween.callChain();}.bind(this));return this;}});Fx.Morph=new Class({Extends:Fx.CSS,initialize:function(element,options){this.element=this.subject=document.id(element);this.parent(options);},set:function(now){if(typeof now=='string')now=this.search(now);for(var p in now)this.render(this.element,p,now[p],this.options.unit);return this;},compute:function(from,to,delta){var now={};for(var p in from)now[p]=this.parent(from[p],to[p],delta);return now;},start:function(properties){if(!this.check(properties))return this;if(typeof properties=='string')properties=this.search(properties);var from={},to={};for(var p in properties){var parsed=this.prepare(this.element,p,properties[p]);from[p]=parsed.from;to[p]=parsed.to;}
return this.parent(from,to);}});Element.Properties.morph={set:function(options){var morph=this.retrieve('morph');if(morph)morph.cancel();return this.eliminate('morph').store('morph:options',$extend({link:'cancel'},options));},get:function(options){if(options||!this.retrieve('morph')){if(options||!this.retrieve('morph:options'))this.set('morph',options);this.store('morph',new Fx.Morph(this,this.retrieve('morph:options')));}
return this.retrieve('morph');}};Element.implement({morph:function(props){this.get('morph').start(props);return this;}});Fx.implement({getTransition:function(){var trans=this.options.transition||Fx.Transitions.Sine.easeInOut;if(typeof trans=='string'){var data=trans.split(':');trans=Fx.Transitions;trans=trans[data[0]]||trans[data[0].capitalize()];if(data[1])trans=trans['ease'+data[1].capitalize()+(data[2]?data[2].capitalize():'')];}
return trans;}});Fx.Transition=function(transition,params){params=$splat(params);return $extend(transition,{easeIn:function(pos){return transition(pos,params);},easeOut:function(pos){return 1-transition(1-pos,params);},easeInOut:function(pos){return(pos<=0.5)?transition(2*pos,params)/2:(2-transition(2*(1-pos),params))/2;}});};Fx.Transitions=new Hash({linear:$arguments(0)});Fx.Transitions.extend=function(transitions){for(var transition in transitions)Fx.Transitions[transition]=new Fx.Transition(transitions[transition]);};Fx.Transitions.extend({Pow:function(p,x){return Math.pow(p,x[0]||6);},Expo:function(p){return Math.pow(2,8*(p-1));},Circ:function(p){return 1-Math.sin(Math.acos(p));},Sine:function(p){return 1-Math.sin((1-p)*Math.PI/2);},Back:function(p,x){x=x[0]||1.618;return Math.pow(p,2)*((x+1)*p-x);},Bounce:function(p){var value;for(var a=0,b=1;1;a+=b,b/=2){if(p>=(7-4*a)/11){value=b*b-Math.pow((11-6*a-11*p)/4,2);break;}}
return value;},Elastic:function(p,x){return Math.pow(2,10*--p)*Math.cos(20*p*Math.PI*(x[0]||1)/3);}});['Quad','Cubic','Quart','Quint'].each(function(transition,i){Fx.Transitions[transition]=new Fx.Transition(function(p){return Math.pow(p,[i+2]);});});var Request=new Class({Implements:[Chain,Events,Options],options:{url:'',data:'',headers:{'X-Requested-With':'XMLHttpRequest','Accept':'text/javascript, text/html, application/xml, text/xml, */*'},async:true,format:false,method:'post',link:'ignore',isSuccess:null,emulation:true,urlEncoded:true,encoding:'utf-8',evalScripts:false,evalResponse:false,noCache:false},initialize:function(options){this.xhr=new Browser.Request();this.setOptions(options);this.options.isSuccess=this.options.isSuccess||this.isSuccess;this.headers=new Hash(this.options.headers);},onStateChange:function(){if(this.xhr.readyState!=4||!this.running)return;this.running=false;this.status=0;$try(function(){this.status=this.xhr.status;}.bind(this));this.xhr.onreadystatechange=$empty;if(this.options.isSuccess.call(this,this.status)){this.response={text:this.xhr.responseText,xml:this.xhr.responseXML};this.success(this.response.text,this.response.xml);}else{this.response={text:null,xml:null};this.failure();}},isSuccess:function(){return((this.status>=200)&&(this.status<300));},processScripts:function(text){if(this.options.evalResponse||(/(ecma|java)script/).test(this.getHeader('Content-type')))return $exec(text);return text.stripScripts(this.options.evalScripts);},success:function(text,xml){this.onSuccess(this.processScripts(text),xml);},onSuccess:function(){this.fireEvent('complete',arguments).fireEvent('success',arguments).callChain();},failure:function(){this.onFailure();},onFailure:function(){this.fireEvent('complete').fireEvent('failure',this.xhr);},setHeader:function(name,value){this.headers.set(name,value);return this;},getHeader:function(name){return $try(function(){return this.xhr.getResponseHeader(name);}.bind(this));},check:function(){if(!this.running)return true;switch(this.options.link){case'cancel':this.cancel();return true;case'chain':this.chain(this.caller.bind(this,arguments));return false;}
return false;},send:function(options){if(!this.check(options))return this;this.running=true;var type=$type(options);if(type=='string'||type=='element')options={data:options};var old=this.options;options=$extend({data:old.data,url:old.url,method:old.method},options);var data=options.data,url=String(options.url),method=options.method.toLowerCase();switch($type(data)){case'element':data=document.id(data).toQueryString();break;case'object':case'hash':data=Hash.toQueryString(data);}
if(this.options.format){var format='format='+this.options.format;data=(data)?format+'&'+data:format;}
if(this.options.emulation&&!['get','post'].contains(method)){var _method='_method='+method;data=(data)?_method+'&'+data:_method;method='post';}
if(this.options.urlEncoded&&method=='post'){var encoding=(this.options.encoding)?'; charset='+this.options.encoding:'';this.headers.set('Content-type','application/x-www-form-urlencoded'+encoding);}
if(this.options.noCache){var noCache='noCache='+new Date().getTime();data=(data)?noCache+'&'+data:noCache;}
var trimPosition=url.lastIndexOf('/');if(trimPosition>-1&&(trimPosition=url.indexOf('#'))>-1)url=url.substr(0,trimPosition);if(data&&method=='get'){url=url+(url.contains('?')?'&':'?')+data;data=null;}
this.xhr.open(method.toUpperCase(),url,this.options.async);this.xhr.onreadystatechange=this.onStateChange.bind(this);this.headers.each(function(value,key){try{this.xhr.setRequestHeader(key,value);}catch(e){this.fireEvent('exception',[key,value]);}},this);this.fireEvent('request');this.xhr.send(data);if(!this.options.async)this.onStateChange();return this;},cancel:function(){if(!this.running)return this;this.running=false;this.xhr.abort();this.xhr.onreadystatechange=$empty;this.xhr=new Browser.Request();this.fireEvent('cancel');return this;}});(function(){var methods={};['get','post','put','delete','GET','POST','PUT','DELETE'].each(function(method){methods[method]=function(){var params=Array.link(arguments,{url:String.type,data:$defined});return this.send($extend(params,{method:method}));};});Request.implement(methods);})();Element.Properties.send={set:function(options){var send=this.retrieve('send');if(send)send.cancel();return this.eliminate('send').store('send:options',$extend({data:this,link:'cancel',method:this.get('method')||'post',url:this.get('action')},options));},get:function(options){if(options||!this.retrieve('send')){if(options||!this.retrieve('send:options'))this.set('send',options);this.store('send',new Request(this.retrieve('send:options')));}
return this.retrieve('send');}};Element.implement({send:function(url){var sender=this.get('send');sender.send({data:this,url:url||sender.options.url});return this;}});Request.HTML=new Class({Extends:Request,options:{update:false,append:false,evalScripts:true,filter:false},processHTML:function(text){var match=text.match(/<body[^>]*>([\s\S]*?)<\/body>/i);text=(match)?match[1]:text;var container=new Element('div');return $try(function(){var root='<root>'+text+'</root>',doc;if(Browser.Engine.trident){doc=new ActiveXObject('Microsoft.XMLDOM');doc.async=false;doc.loadXML(root);}else{doc=new DOMParser().parseFromString(root,'text/xml');}
root=doc.getElementsByTagName('root')[0];if(!root)return null;for(var i=0,k=root.childNodes.length;i<k;i++){var child=Element.clone(root.childNodes[i],true,true);if(child)container.grab(child);}
return container;})||container.set('html',text);},success:function(text){var options=this.options,response=this.response;response.html=text.stripScripts(function(script){response.javascript=script;});var temp=this.processHTML(response.html);response.tree=temp.childNodes;response.elements=temp.getElements('*');if(options.filter)response.tree=response.elements.filter(options.filter);if(options.update)document.id(options.update).empty().set('html',response.html);else if(options.append)document.id(options.append).adopt(temp.getChildren());if(options.evalScripts)$exec(response.javascript);this.onSuccess(response.tree,response.elements,response.html,response.javascript);}});Element.Properties.load={set:function(options){var load=this.retrieve('load');if(load)load.cancel();return this.eliminate('load').store('load:options',$extend({data:this,link:'cancel',update:this,method:'get'},options));},get:function(options){if(options||!this.retrieve('load')){if(options||!this.retrieve('load:options'))this.set('load',options);this.store('load',new Request.HTML(this.retrieve('load:options')));}
return this.retrieve('load');}};Element.implement({load:function(){this.get('load').send(Array.link(arguments,{data:Object.type,url:String.type}));return this;}});Request.JSON=new Class({Extends:Request,options:{secure:true},initialize:function(options){this.parent(options);this.headers.extend({'Accept':'application/json','X-Request':'JSON'});},success:function(text){this.response.json=JSON.decode(text,this.options.secure);this.onSuccess(this.response.json,text);}});
</script>
'''

DATEPICKER = R'''<script language="JavaScript">
/**
 * datepicker.js - MooTools Datepicker class
 * @version 1.16
 * 
 * by MonkeyPhysics.com
 *
 * Source/Documentation available at:
 * http://www.monkeyphysics.com/mootools/script/2/datepicker
 * 
 * --
 * 
 * Smoothly animating, very configurable and easy to install.
 * No Ajax, pure Javascript. 4 skins available out of the box.
 * 
 * --
 *
 * Some Rights Reserved
 * http://creativecommons.org/licenses/by-sa/3.0/
 * 
 */

var DatePicker = new Class({
	
	Implements: Options,
	
	// working date, which we will keep modifying to render the calendars
	d: '',
	
	// just so that we need not request it over and over
	today: '',
	
	// current user-choice in date object format
	choice: {}, 
	
	// size of body, used to animate the sliding
	bodysize: {}, 
	
	// to check availability of next/previous buttons
	limit: {}, 
	
	// element references:
	attachTo: null,	// selector for target inputs
	picker: null,	  // main datepicker container
	slider: null,	  // slider that contains both oldContents and newContents, used to animate between 2 different views
	oldContents: null, // used in animating from-view to new-view
	newContents: null, // used in animating from-view to new-view
	input: null,	   // original input element (used for input/output)
	visual: null,	  // visible input (used for rendering)
	
	options: { 
		pickerClass: 'datepicker',
		days: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
		months: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
		dayShort: 2,
		monthShort: 3,
		startDay: 1, // Sunday (0) through Saturday (6) - be aware that this may affect your layout, since the days on the right might have a different margin
		timePicker: false,
		timePickerOnly: false,
		yearPicker: true,
		yearsPerPage: 20,
		format: 'd-m-Y',
		allowEmpty: false,
		inputOutputFormat: 'U', // default to unix timestamp
		animationDuration: 400,
		useFadeInOut: !Browser.Engine.trident, // dont animate fade-in/fade-out for IE
		startView: 'month', // allowed values: {time, month, year, decades}
		positionOffset: { x: 0, y: 0 },
		minDate: null, // { date: '[date-string]', format: '[date-string-interpretation-format]' }
		maxDate: null, // same as minDate
		debug: false,
		toggleElements: null,
		
		// and some event hooks:
		onShow: $empty,   // triggered when the datepicker pops up
		onClose: $empty,  // triggered after the datepicker is closed (destroyed)
		onSelect: $empty  // triggered when a date is selected
	},


	initialize: function(attachTo, options) {
		this.attachTo = attachTo;
		this.setOptions(options).attach();
		if (this.options.timePickerOnly) {
			this.options.timePicker = true;
			this.options.startView = 'time';
		}
		this.formatMinMaxDates();
		document.addEvent('mousedown', this.close.bind(this));
	},
	
	formatMinMaxDates: function() {
		if (this.options.minDate && this.options.minDate.format) {
			this.options.minDate = this.unformat(this.options.minDate.date, this.options.minDate.format);
		}
		if (this.options.maxDate && this.options.maxDate.format) {
			this.options.maxDate = this.unformat(this.options.maxDate.date, this.options.maxDate.format);
			this.options.maxDate.setHours(23);
			this.options.maxDate.setMinutes(59);
			this.options.maxDate.setSeconds(59);
		}
	},
	
	attach: function() {
		// toggle the datepicker through a separate element?
		if ($chk(this.options.toggleElements)) {
			var togglers = $$(this.options.toggleElements);
			document.addEvents({
				'keydown': function(e) {
					if (e.key == "tab") {
						this.close(null, true);
					}
				}.bind(this)
			});
		};
		
		// attach functionality to the inputs		
		$$(this.attachTo).each(function(item, index) {
			
			// never double attach
			if (item.retrieve('datepicker')) return;
			
			// determine starting value(s)
			if ($chk(item.get('value'))) {
				
				var j=new Date();
				var gmt = -j.getTimezoneOffset()/60;

				var lessthan = 5 + gmt;

				var secs = 60 * 60 * lessthan;

				var newstamp = item.get('value')-secs;
				
				var init_clone_val = this.format(new Date(this.unformat(newstamp, this.options.inputOutputFormat)), this.options.format);
			} else if (!this.options.allowEmpty) {
				var init_clone_val = this.format(new Date(), this.options.format);
			} else {
				var init_clone_val = '';
			}
			
			// create clone
			var display = item.getStyle('display');
			var clone = item
			.setStyle('display', this.options.debug ? display : 'none')
			.store('datepicker', true) // to prevent double attachment...
			.clone()
			.store('datepicker', true) // ...even for the clone (!)
			.removeProperty('name')	// secure clean (form)submission
			.setStyle('display', display)
			.set('value', init_clone_val)
			.inject(item, 'after');
			
			// events
			if ($chk(this.options.toggleElements)) {
				togglers[index]
					.setStyle('cursor', 'pointer')
					.addEvents({
						'click': function(e) {
							this.onFocus(item, clone);
						}.bind(this)
					});
				clone.addEvents({
					'blur': function() {
						item.set('value', clone.get('value'));
					}
				});
			} else {
				clone.addEvents({
					'keydown': function(e) {
						if (this.options.allowEmpty && (e.key == "delete" || e.key == "backspace")) {
							item.set('value', '');
							e.target.set('value', '');
							this.close(null, true);
						} else if (e.key == "tab") {
							this.close(null, true);
						} else {
							e.stop();
						}
					}.bind(this),
					'focus': function(e) {
						this.onFocus(item, clone);
					}.bind(this)
				});
			}
		}.bind(this));
	},
	
	onFocus: function(original_input, visual_input) {
		var init_visual_date, d = visual_input.getCoordinates();
		
		if ($chk(original_input.get('value'))) {
			init_visual_date = this.unformat(original_input.get('value'), this.options.inputOutputFormat).valueOf();
		} else {
			init_visual_date = new Date();
			if ($chk(this.options.maxDate) && init_visual_date.valueOf() > this.options.maxDate.valueOf()) {
				init_visual_date = new Date(this.options.maxDate.valueOf());
			}
			if ($chk(this.options.minDate) && init_visual_date.valueOf() < this.options.minDate.valueOf()) {
				init_visual_date = new Date(this.options.minDate.valueOf());
			}
		}
		
		this.show({ left: d.left + this.options.positionOffset.x, top: d.top + d.height + this.options.positionOffset.y }, init_visual_date);
		this.input = original_input;
		this.visual = visual_input;
		this.options.onShow();
	},
	
	dateToObject: function(d) {
		
		return {
			year: d.getFullYear(),
			month: d.getMonth(),
			day: d.getDate(),
			hours: d.getHours(),
			minutes: d.getMinutes(),
			seconds: d.getSeconds()
		};
	},
	
	dateFromObject: function(values) {
		var d = new Date();
		d.setDate(1);
		['year', 'month', 'day', 'hours', 'minutes', 'seconds'].each(function(type) {
			var v = values[type];
			if (!$chk(v)) return;
			switch (type) {
				case 'day': d.setDate(v); break;
				case 'month': d.setMonth(v); break;
				case 'year': d.setFullYear(v); break;
				case 'hours': d.setHours(v); break;
				case 'minutes': d.setMinutes(v); break;
				case 'seconds': d.setSeconds(v); break;
			}
		});
		return d;
	},
	
	show: function(position, timestamp) {
		this.formatMinMaxDates();
		if ($chk(timestamp)) {
			this.d = new Date(timestamp);
		} else {
			this.d = new Date();
		}

		this.today = new Date();
		this.choice = this.dateToObject(this.d);
		this.mode = (this.options.startView == 'time' && !this.options.timePicker) ? 'month' : this.options.startView;
		this.render();
		this.picker.setStyles(position);
	},
	
	render: function(fx) {
		if (!$chk(this.picker)) {
			this.constructPicker();
		} else {
			// swap contents so we can fill the newContents again and animate
			var o = this.oldContents;
			this.oldContents = this.newContents;
			this.newContents = o;
			this.newContents.empty();
		}
		
		// remember current working date
		var startDate = new Date(this.d.getTime());
		
		// intially assume both left and right are allowed
		this.limit = { right: false, left: false };
		
		// render! booty!
		if (this.mode == 'decades') {
			this.renderDecades();
		} else if (this.mode == 'year') {
			this.renderYear();
		} else if (this.mode == 'time') {
			this.renderTime();
			this.limit = { right: true, left: true }; // no left/right in timeview
		} else {
			this.renderMonth();
		}
		
		this.picker.getElement('.previous').setStyle('visibility', this.limit.left ? 'hidden' : 'visible');
		this.picker.getElement('.next').setStyle('visibility', this.limit.right ? 'hidden' : 'visible');
		this.picker.getElement('.titleText').setStyle('cursor', this.allowZoomOut() ? 'pointer' : 'default');
		
		// restore working date
		this.d = startDate;
		
		// if ever the opacity is set to '0' it was only to have us fade it in here
		// refer to the constructPicker() function, which instantiates the picker at opacity 0 when fading is desired
		if (this.picker.getStyle('opacity') == 0) {
			this.picker.tween('opacity', 0, 1);
		}
		
		// animate
		if ($chk(fx)) this.fx(fx);
	},
	
	fx: function(fx) {
		if (fx == 'right') {
			this.oldContents.setStyles({ left: 0, opacity: 1 });
			this.newContents.setStyles({ left: this.bodysize.x, opacity: 1 });
			this.slider.setStyle('left', 0).tween('left', 0, -this.bodysize.x);
		} else if (fx == 'left') {
			this.oldContents.setStyles({ left: this.bodysize.x, opacity: 1 });
			this.newContents.setStyles({ left: 0, opacity: 1 });
			this.slider.setStyle('left', -this.bodysize.x).tween('left', -this.bodysize.x, 0);
		} else if (fx == 'fade') {
			this.slider.setStyle('left', 0);
			this.oldContents.setStyle('left', 0).set('tween', { duration: this.options.animationDuration / 2 }).tween('opacity', 1, 0);
			this.newContents.setStyles({ opacity: 0, left: 0}).set('tween', { duration: this.options.animationDuration }).tween('opacity', 0, 1);
		}
	},
	
	constructPicker: function() {
		this.picker = new Element('div', { 'class': this.options.pickerClass }).inject(document.body);
		if (this.options.useFadeInOut) {
			this.picker.setStyle('opacity', 0).set('tween', { duration: this.options.animationDuration });
		}
		
		var h = new Element('div', { 'class': 'header' }).inject(this.picker);
		var titlecontainer = new Element('div', { 'class': 'title' }).inject(h);
		new Element('div', { 'class': 'previous' }).addEvent('click', this.previous.bind(this)).set('text', 'Â«').inject(h);
		new Element('div', { 'class': 'next' }).addEvent('click', this.next.bind(this)).set('text', 'Â»').inject(h);
		new Element('div', { 'class': 'closeButton' }).addEvent('click', this.close.bindWithEvent(this, true)).set('text', 'x').inject(h);
		new Element('span', { 'class': 'titleText' }).addEvent('click', this.zoomOut.bind(this)).inject(titlecontainer);
		
		var b = new Element('div', { 'class': 'body' }).inject(this.picker);
		this.bodysize = b.getSize();
		this.slider = new Element('div', { styles: { position: 'absolute', top: 0, left: 0, width: 2 * this.bodysize.x, height: this.bodysize.y }})
					.set('tween', { duration: this.options.animationDuration, transition: Fx.Transitions.Quad.easeInOut }).inject(b);
		this.oldContents = new Element('div', { styles: { position: 'absolute', top: 0, left: this.bodysize.x, width: this.bodysize.x, height: this.bodysize.y }}).inject(this.slider);
		this.newContents = new Element('div', { styles: { position: 'absolute', top: 0, left: 0, width: this.bodysize.x, height: this.bodysize.y }}).inject(this.slider);
	},
	
	renderTime: function() {
		var container = new Element('div', { 'class': 'time' }).inject(this.newContents);
		
		if (this.options.timePickerOnly) {
			this.picker.getElement('.titleText').set('text', 'Select a time');
		} else {
			this.picker.getElement('.titleText').set('text', this.format(this.d, 'j M, Y'));
		}
		
		new Element('input', { type: 'text', 'class': 'hour' })
			.set('value', this.leadZero(this.d.getHours()))
			.addEvents({
				mousewheel: function(e) {
					var i = e.target, v = i.get('value').toInt();
					i.focus();
					if (e.wheel > 0) {
						v = (v < 23) ? v + 1 : 0;
					} else {
						v = (v > 0) ? v - 1 : 23;
					}
					i.set('value', this.leadZero(v));
					e.stop();
				}.bind(this)
			})
			.set('maxlength', 2)
			.inject(container);
			
		new Element('input', { type: 'text', 'class': 'minutes' })
			.set('value', this.leadZero(this.d.getMinutes()))
			.addEvents({
				mousewheel: function(e) {
					var i = e.target, v = i.get('value').toInt();
					i.focus();
					if (e.wheel > 0) {
						v = (v < 59) ? v + 1 : 0;
					} else {
						v = (v > 0) ? v - 1 : 59;
					}
					i.set('value', this.leadZero(v));
					e.stop();
				}.bind(this)
			})
			.set('maxlength', 2)
			.inject(container);
		
		new Element('div', { 'class': 'separator' }).set('text', ':').inject(container);
		
		new Element('input', { type: 'submit', value: 'OK', 'class': 'ok' })
			.addEvents({
				click: function(e) {
					e.stop();
					this.select($merge(this.dateToObject(this.d), { hours: this.picker.getElement('.hour').get('value').toInt(), minutes: this.picker.getElement('.minutes').get('value').toInt() }));
				}.bind(this)
			})
			.set('maxlength', 2)
			.inject(container);
	},
	
	renderMonth: function() {
		var month = this.d.getMonth();
		
		this.picker.getElement('.titleText').set('text', this.options.months[month] + ' ' + this.d.getFullYear());
		
		this.d.setDate(1);
		while (this.d.getDay() != this.options.startDay) {
			this.d.setDate(this.d.getDate() - 1);
		}
		
		var container = new Element('div', { 'class': 'days' }).inject(this.newContents);
		var titles = new Element('div', { 'class': 'titles' }).inject(container);
		var d, i, classes, e, weekcontainer;

		for (d = this.options.startDay; d < (this.options.startDay + 7); d++) {
			new Element('div', { 'class': 'title day day' + (d % 7) }).set('text', this.options.days[(d % 7)].substring(0,this.options.dayShort)).inject(titles);
		}
		
		var available = false;
		var t = this.today.toDateString();
		var currentChoice = this.dateFromObject(this.choice).toDateString();
		
		for (i = 0; i < 42; i++) {
			classes = [];
			classes.push('day');
			classes.push('day'+this.d.getDay());
			if (this.d.toDateString() == t) classes.push('today');
			if (this.d.toDateString() == currentChoice) classes.push('selected');
			if (this.d.getMonth() != month) classes.push('otherMonth');
			
			if (i % 7 == 0) {
				weekcontainer = new Element('div', { 'class': 'week week'+(Math.floor(i/7)) }).inject(container);
			}
			
			e = new Element('div', { 'class': classes.join(' ') }).set('text', this.d.getDate()).inject(weekcontainer);
			if (this.limited('date')) {
				e.addClass('unavailable');
				if (available) {
					this.limit.right = true;
				} else if (this.d.getMonth() == month) {
					this.limit.left = true;
				}
			} else {
				available = true;
				e.addEvent('click', function(e, d) {
					if (this.options.timePicker) {
						this.d.setDate(d.day);
						this.d.setMonth(d.month);
						this.mode = 'time';
						this.render('fade');
					} else {
						this.select(d);
					}
				}.bindWithEvent(this, { day: this.d.getDate(), month: this.d.getMonth(), year: this.d.getFullYear() }));
			}
			this.d.setDate(this.d.getDate() + 1);
		}
		if (!available) this.limit.right = true;
	},
	
	renderYear: function() {
		var month = this.today.getMonth();
		var thisyear = this.d.getFullYear() == this.today.getFullYear();
		var selectedyear = this.d.getFullYear() == this.choice.year;
		
		this.picker.getElement('.titleText').set('text', this.d.getFullYear());
		this.d.setMonth(0);
		
		var i, e;
		var available = false;
		var container = new Element('div', { 'class': 'months' }).inject(this.newContents);
		
		for (i = 0; i <= 11; i++) {
			e = new Element('div', { 'class': 'month month'+(i+1)+(i == month && thisyear ? ' today' : '')+(i == this.choice.month && selectedyear ? ' selected' : '') })
			.set('text', this.options.monthShort ? this.options.months[i].substring(0, this.options.monthShort) : this.options.months[i]).inject(container);
			
			if (this.limited('month')) {
				e.addClass('unavailable');
				if (available) {
					this.limit.right = true;
				} else {
					this.limit.left = true;
				}
			} else {
				available = true;
				e.addEvent('click', function(e, d) {
					this.d.setDate(1);
					this.d.setMonth(d);
					this.mode = 'month';
					this.render('fade');
				}.bindWithEvent(this, i));
			}
			this.d.setMonth(i);
		}
		if (!available) this.limit.right = true;
	},
	
	renderDecades: function() {
		// start neatly at interval (eg. 1980 instead of 1987)
		while (this.d.getFullYear() % this.options.yearsPerPage > 0) {
			this.d.setFullYear(this.d.getFullYear() - 1);
		}

		this.picker.getElement('.titleText').set('text', this.d.getFullYear() + '-' + (this.d.getFullYear() + this.options.yearsPerPage - 1));
		
		var i, y, e;
		var available = false;
		var container = new Element('div', { 'class': 'years' }).inject(this.newContents);
		
		if ($chk(this.options.minDate) && this.d.getFullYear() <= this.options.minDate.getFullYear()) {
			this.limit.left = true;
		}
		
		for (i = 0; i < this.options.yearsPerPage; i++) {
			y = this.d.getFullYear();
			e = new Element('div', { 'class': 'year year' + i + (y == this.today.getFullYear() ? ' today' : '') + (y == this.choice.year ? ' selected' : '') }).set('text', y).inject(container);
			
			if (this.limited('year')) {
				e.addClass('unavailable');
				if (available) {
					this.limit.right = true;
				} else {
					this.limit.left = true;
				}
			} else {
				available = true;
				e.addEvent('click', function(e, d) {
					this.d.setFullYear(d);
					this.mode = 'year';
					this.render('fade');
				}.bindWithEvent(this, y));
			}
			this.d.setFullYear(this.d.getFullYear() + 1);
		}
		if (!available) {
			this.limit.right = true;
		}
		if ($chk(this.options.maxDate) && this.d.getFullYear() >= this.options.maxDate.getFullYear()) {
			this.limit.right = true;
		}
	},
	
	limited: function(type) {
		var cs = $chk(this.options.minDate);
		var ce = $chk(this.options.maxDate);
		if (!cs && !ce) return false;
		
		switch (type) {
			case 'year':
				return (cs && this.d.getFullYear() < this.options.minDate.getFullYear()) || (ce && this.d.getFullYear() > this.options.maxDate.getFullYear());
				
			case 'month':
				// todo: there has got to be an easier way...?
				var ms = ('' + this.d.getFullYear() + this.leadZero(this.d.getMonth())).toInt();
				return cs && ms < ('' + this.options.minDate.getFullYear() + this.leadZero(this.options.minDate.getMonth())).toInt()
					|| ce && ms > ('' + this.options.maxDate.getFullYear() + this.leadZero(this.options.maxDate.getMonth())).toInt()
				
			case 'date':
				return (cs && this.d < this.options.minDate) || (ce && this.d > this.options.maxDate);
		}
	},
	
	allowZoomOut: function() {
		if (this.mode == 'time' && this.options.timePickerOnly) return false;
		if (this.mode == 'decades') return false;
		if (this.mode == 'year' && !this.options.yearPicker) return false;
		return true;
	},
	
	zoomOut: function() {
		if (!this.allowZoomOut()) return;
		if (this.mode == 'year') {
			this.mode = 'decades';
		} else if (this.mode == 'time') {
			this.mode = 'month';
		} else {
			this.mode = 'year';
		}
		this.render('fade');
	},
	
	previous: function() {
		if (this.mode == 'decades') {
			this.d.setFullYear(this.d.getFullYear() - this.options.yearsPerPage);
		} else if (this.mode == 'year') {
			this.d.setFullYear(this.d.getFullYear() - 1);
		} else if (this.mode == 'month') {
			this.d.setMonth(this.d.getMonth() - 1);
		}
		this.render('left');
	},
	
	next: function() {
		if (this.mode == 'decades') {
			this.d.setFullYear(this.d.getFullYear() + this.options.yearsPerPage);
		} else if (this.mode == 'year') {
			this.d.setFullYear(this.d.getFullYear() + 1);
		} else if (this.mode == 'month') {
			this.d.setMonth(this.d.getMonth() + 1);
		}
		this.render('right');
	},
	
	close: function(e, force) {
		if (!$(this.picker)) return;
		var clickOutside = ($chk(e) && e.target != this.picker && !this.picker.hasChild(e.target) && e.target != this.visual);
		if (force || clickOutside) {
			if (this.options.useFadeInOut) {
				this.picker.set('tween', { duration: this.options.animationDuration / 2, onComplete: this.destroy.bind(this) }).tween('opacity', 1, 0);
			} else {
				this.destroy();
			}
		}
	},
	
	destroy: function() {
		this.picker.destroy();
		this.picker = null;
		this.options.onClose();
	},
	
	select: function(values) {
		this.choice = $merge(this.choice, values);
		var d = this.dateFromObject(this.choice);
		this.input.set('value', this.format(d, this.options.inputOutputFormat));
		this.visual.set('value', this.format(d, this.options.format));
		this.options.onSelect(d);
		this.close(null, true);
	},
	
	leadZero: function(v) {
		return v < 10 ? '0'+v : v;
	},
	
	format: function(t, format) {
		var f = '';

		var h = t.getHours();
		var m = t.getMonth();

		for (var i = 0; i < format.length; i++) {
			switch(format.charAt(i)) {
				case '\\': i++; f+= format.charAt(i); break;
				case 'y': f += (100 + t.getYear() + '').substring(1); break
				case 'Y': f += t.getFullYear(); break;
				case 'm': f += this.leadZero(m + 1); break;
				case 'n': f += (m + 1); break;
				case 'M': f += this.options.months[m].substring(0,this.options.monthShort); break;
				case 'F': f += this.options.months[m]; break;
				case 'd': f += this.leadZero(t.getDate()); break;
				case 'j': f += t.getDate(); break;
				case 'D': f += this.options.days[t.getDay()].substring(0,this.options.dayShort); break;
				case 'l': f += this.options.days[t.getDay()]; break;
				case 'G': f += h; break;
				case 'H': f += this.leadZero(h); break;
				case 'g': f += (h % 12 ? h % 12 : 12); break;
				case 'h': f += this.leadZero(h % 12 ? h % 12 : 12); break;
				case 'a': f += (h > 11 ? 'pm' : 'am'); break;
				case 'A': f += (h > 11 ? 'PM' : 'AM'); break;
				case 'i': f += this.leadZero(t.getMinutes()); break;
				case 's': f += this.leadZero(t.getSeconds()); break;
				case 'U': f += Math.floor(t.valueOf() / 1000); break;
				default:  f += format.charAt(i);
			}
		}
		return f;
	},
	
	unformat: function(t, format) {
		var d = new Date();
		var a = {};
		var c, m;
		t = t.toString();
		
		for (var i = 0; i < format.length; i++) {
			c = format.charAt(i);
			switch(c) {
				case '\\': r = null; i++; break;
				case 'y': r = '[0-9]{2}'; break;
				case 'Y': r = '[0-9]{4}'; break;
				case 'm': r = '0[1-9]|1[012]'; break;
				case 'n': r = '[1-9]|1[012]'; break;
				case 'M': r = '[A-Za-z]{'+this.options.monthShort+'}'; break;
				case 'F': r = '[A-Za-z]+'; break;
				case 'd': r = '0[1-9]|[12][0-9]|3[01]'; break;
				case 'j': r = '[1-9]|[12][0-9]|3[01]'; break;
				case 'D': r = '[A-Za-z]{'+this.options.dayShort+'}'; break;
				case 'l': r = '[A-Za-z]+'; break;
				case 'G': 
				case 'H': 
				case 'g': 
				case 'h': r = '[0-9]{1,2}'; break;
				case 'a': r = '(am|pm)'; break;
				case 'A': r = '(AM|PM)'; break;
				case 'i': 
				case 's': r = '[012345][0-9]'; break;
				case 'U': r = '-?[0-9]+$'; break;
				default:  r = null;
			}
			
			if ($chk(r)) {
				m = t.match('^'+r);
				if ($chk(m)) {
					a[c] = m[0];
					t = t.substring(a[c].length);
				} else {
					if (this.options.debug) alert("Fatal Error in DatePicker\n\nUnexpected format at: '"+t+"' expected format character '"+c+"' (pattern '"+r+"')");
					return d;
				}
			} else {
				t = t.substring(1);
			}
		}
		
		for (c in a) {
			var v = a[c];
			switch(c) {
				case 'y': d.setFullYear(v < 30 ? 2000 + v.toInt() : 1900 + v.toInt()); break; // assume between 1930 - 2029
				case 'Y': d.setFullYear(v); break;
				case 'm':
				case 'n': d.setMonth(v - 1); break;
				// FALL THROUGH NOTICE! "M" has no break, because "v" now is the full month (eg. 'February'), which will work with the next format "F":
				case 'M': v = this.options.months.filter(function(item, index) { return item.substring(0,this.options.monthShort) == v }.bind(this))[0];
				case 'F': d.setMonth(this.options.months.indexOf(v)); break;
				case 'd':
				case 'j': d.setDate(v); break;
				case 'G': 
				case 'H': d.setHours(v); break;
				case 'g': 
				case 'h': if (a['a'] == 'pm' || a['A'] == 'PM') { d.setHours(v == 12 ? 0 : v.toInt() + 12); } else { d.setHours(v); } break;
				case 'i': d.setMinutes(v); break;
				case 's': d.setSeconds(v); break;
				case 'U': d = new Date(v.toInt() * 1000);
			}
		};
		
		return d;
	}
});
</script>
'''

def on_aws():
	"""Return whether running as AWS Lambda"""
	return "LAMBDA_TASK_ROOT" in os.environ

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
			result[int(l[0])] = l[3]
	return result

def extractData(datasetstr):
	return re.findall("set value='([^']*)", datasetstr)

def normalizeVmax(vmax):
	if vmax <= 5: return 5
	l = math.log(vmax, 10)
	e = int(l)
	f = l - e
	pow10 = int(math.pow(10,e))
	if f < 0.30103: return 2*pow10
	if f < 0.69897: return 5*pow10
	return 10*pow10

def normalizePminmax(pmin, pmax):
	if pmin == pmax:
		if (pmin == 0):
			return (0, 5)
		n = math.log(pmin, 10)
		e = int(n)
		f = n - e
		pow10e = pow(10,e)
		c = round(pmin/pow10e)*pow10e
		return(c-pow10e, c+pow10e)
	diff = normalizeVmax(pmax - pmin)
	newmin = int(pmin/diff) * diff
	newmax = (int(pmax/diff)+1) * diff
	return (newmin, newmax)
	
def volumeAxis(vmax):
	tx = SVG_WIDTH-5
	ty = TOP_MARGIN + GRAPH_HEIGHT/2
	result = f"<text x={tx} y={ty} text-anchor=middle class='volume' "
	result = result + f" transform='rotate(-90 {tx},{ty})'>Volume</text>"
	ybase = TOP_MARGIN + GRAPH_HEIGHT
	tx = SIDE_MARGIN + GRAPH_WIDTH + 3
	for i in range(6):
		lbl = int(vmax*i/5)
		ty = ybase - GRAPH_HEIGHT*i/5 + 3
		result = result + f"<text x={tx} y={ty} class='volume'>{lbl:,}</text>"
	return result

def priceAxis(pmin, pmax):
	tx = 8
	ty = TOP_MARGIN + GRAPH_HEIGHT/2
	result = f"<text x={tx} y={ty} text-anchor=middle class='price' "
	result = result + f" transform='rotate(-90 {tx},{ty})'>Price</text>"
	ybase = TOP_MARGIN + GRAPH_HEIGHT
	tx = SIDE_MARGIN - 3
	step = (pmax - pmin)/5
	for i in range(6):
		lbl = int(pmin + step*i)
		ty = ybase - GRAPH_HEIGHT*i/5 + 3
		result = result + f"<text x={tx} y={ty} text-anchor=end class='price'>"
		result = result + f"{lbl:,}</text>"
	return result

def rect(x, y, width, height, style, title):
	result = f"<rect x='{x}' y='{y}' width='{width}' height='{height}'"
	result = result + f" style='{style}'>"
	if title != "":
		result = result + "<title>" + title + "</title>"
	return result + "</rect>\n"

def horizontalLine(x1, x2, y, stroke):
	result = f"<line x1={x1} y1={y} x2={x2} y2={y} "
	result = result + f"style='stroke: {stroke}' />"
	return result
	
def category(x, y, text):
	y2 = y + 3 + TOP_MARGIN
	result = f"<text x='{x}' y='{y2}' text-anchor='end' class='dates' "
	result = result + f"transform='rotate(-90 {x},{y2})'>{text}</text>\n"
	return result

def volumebar(x, y, width, volume, scale):
	x2 = x - (width/2.0)
	height = float(volume) * scale
	y2 = y - height
	result = f"<rect x='{x2}' y='{y2}' width='{width}' height='{height}' "
	result = result + " style='fill: #c0c0ff; stroke: #8080ff; stroke-width: 1px'>"
	result = result + f"<title>Volume: {volume}</title>"
	result = result + "</rect>\n"
	return result

def pricePoint(p, wid, x, y):
	wid2 = wid/4
	result = f"<circle cx={x} cy={y} r={wid2} style='fill:#c00000; stroke:black'>"
	result = result + f"<title>Avg Price: {p}</title></circle>\n"
	return result

def graphPrices2(tbl, pmax, pmin, startprice):
	result = "<polyline fill='none' stroke='black' points='"
	wid = GRAPH_WIDTH*1.0 / len(tbl)
	pr1 = SIDE_MARGIN + wid/2.0
	price = startprice
	for i in range(len(tbl)):
		p = float(tbl[i][2])	# 0 if no transactions
		if p < 99: 
			p = price
		#print(f"p={p} price={price}")
		x = pr1 + wid*i
		y = TOP_MARGIN + GRAPH_HEIGHT * ((pmax-p)/(pmax-pmin))
		if y <= GRAPH_BOTTOM: 
			result = result + f"{x},{y} "
		price = p
		#print(f"price for next round is {price}")
	#print(result)
	result = result + "'/>\n"
	for i in range(len(tbl)):
		if tbl[i][1] > 0:
			p = round(float(tbl[i][2]))
			result = result + pricePoint(p, wid, pr1+wid*i, 
										 TOP_MARGIN + GRAPH_HEIGHT*((pmax-p)/(pmax-pmin)))
	return result

def generateChart2(startDate, endDate, tbl, maxvol, maxprice, minprice, startprice):
	result = f"<svg viewbox='0 0 {SVG_WIDTH} {SVG_HEIGHT}' style='width:400pt'>"
	result = result + "<style>\n"
	result = result + "  .norm { font: bold 8px sans-serif; fill: black; }\n"
	result = result + "  .volume { font: bold 8px sans-serif; fill: blue; }\n"
	result = result + "  .price { font: bold 8px sans-serif; fill: red; }\n"
	result = result + "  .dates { font: bold 8px sans-serif; fill: green; }\n"
	result = result + "</style>\n"
	result = result + rect(SIDE_MARGIN, TOP_MARGIN, GRAPH_WIDTH, GRAPH_HEIGHT,
						   'fill: white; stroke-width: 1px; stroke: black;', '')
	for i in range(4):
		result = result + horizontalLine(SIDE_MARGIN, SIDE_MARGIN+GRAPH_WIDTH,
										 GRAPH_BOTTOM-(GRAPH_HEIGHT*(i+1)/5),
										 '#e0e0e0')
	catwidth = GRAPH_WIDTH *1.0 / len(tbl)
	cat1x = SIDE_MARGIN + catwidth/2.0
	for i in range(len(tbl)):
		result = result + category(cat1x + i*catwidth - catwidth/4, GRAPH_HEIGHT, 
								   (tbl[i][0]+TIMESHIFT).strftime("%Y %b %-d, %-H:%MZ"))
	result = result + category(cat1x + 24*catwidth - catwidth/4, GRAPH_HEIGHT, 
								   (endDate+TIMESHIFT).strftime("%Y %b %-d, %-H:%MZ"))
	result = result + volumeAxis(maxvol);
	if startprice < minprice: minprice = startprice
	if startprice > maxprice: maxprice = startprice
	minprice, maxprice = normalizePminmax(minprice, maxprice)
	result = result + priceAxis(minprice, maxprice);
	for i in range(len(tbl)):
		result = result + volumebar(cat1x + i*catwidth, GRAPH_BOTTOM,
									catwidth, tbl[i][1], 
									GRAPH_HEIGHT/maxvol)
	result = result + graphPrices2(tbl, maxprice, minprice, startprice)
	result = result + "</svg>"
	return result


# Get data from KoL directly instead of relying on Coldfront
def fetchEconXactions(itemid, startDate, endDate):
	startstamp = startDate.strftime('%Y%m%d%H%M%S')
	endstamp = endDate.strftime('%Y%m%d%H%M%S')
	url = ECON_URL + "?startstamp=" + startstamp + "&endstamp=" + endstamp 
	url = url + "&items=" + itemid + "&source=1"	# 1 means mall only
	econ = request.urlopen(url)
	b = econ.read()
	b = b.decode("utf-8", "ignore")
	xactions = [ ]
	for xn in b.split("\n"):
		if xn.startswith("m,"):
			xactions.append(xn)
	return xactions

def fetchKoLMallTransactions(itemid, startDate, endDate):
	# This was needed when we saved a copy of the mall transactions, but it's
	# no longer needed since that was more than 2 years ago
	xactions = [ ]
	"""
	dynamodb = boto3.resource('dynamodb', region_name='us-east-2')
	table = dynamodb.Table('KoLMallTransactions')
	startstamp = round(startDate.timestamp())
	endstamp = round(endDate.timestamp())
	response = table.query(
				KeyConditionExpression =
					Key('id').eq(int(itemid))
					& Key('ts').between(startstamp, endstamp)
				)
	for i in response['Items']:
		q = i['q']
		tot = i['tot']
		dt = datetime.fromtimestamp(int(i['ts']), tz=timezone.utc)
		dt = dt.strftime('%Y-%m-%d %H:%M:%S')
		xactions.append(f'm,,,{itemid},{q},{tot},{dt}')
	"""
	return xactions

def fetchXactions(itemid, startDate, endDate):
	#return fetchEconXactions(itemid, startDate, endDate)
	return fetchKoLMallTransactions(itemid, startDate, endDate)
	
# Find the last price of the item before our timespan of interest
def priceGoingIn(itemid, startDate):
	price = 0
	span = timedelta(hours=6)
	while price == 0:
		endDate = startDate
		startDate = endDate - span
		xactions = fetchXactions(itemid, startDate, endDate)
		if len(xactions) > 0:
			lastXaction = xactions[len(xactions)-1]
			parts = lastXaction.split(",")
			price = int(parts[5]) / int(parts[4])
		else:
			span = span * 2
			endDate = startDate
			if endDate < BEGINNING_OF_ECON:
				break	# we've gone too far
			startDate = endDate - span
	return price

# Translate array of text into array suitable for graphing
def econXactionsToGraphTable(data, startDate, endDate):
	result = [ ]
	dt = startDate
	incr = (endDate - startDate) / 24   # graph will have 24 columns
	while dt < endDate:
		result.append( [dt, 0, 0] )
		dt = dt + incr
	i = 0
	limit = 23
	for xn in data:
		details = xn.split(",")
		dt = datetime.strptime(details[6] + " +0000", "%Y-%m-%d %H:%M:%S %z")
		while i < limit and dt > result[i+1][0]:
			i = i + 1
		result[i][1] += int(details[4])
		result[i][2] += int(details[5])
	# Set prices to their average, and compute summary data along the way
	lastprice = 0
	volume = 0
	for i in range(len(result)):
		if result[i][1] > 0:
			result[i][2] = round(result[i][2] / result[i][1])
			lastprice = result[i][2]
			volume += result[i][1]
	return (result, volume, lastprice)

#
def graphDataToGraphTable(graphdata, startDate, endDate):
	datasets = re.findall("<dataset (.*?)</dataset>", graphdata)
	prices = extractData(datasets[0])
	volumes = extractData(datasets[1])
	#dates = re.findall("category name='([^']*)", graphdata)
	#Let's try using our calculated dates instead
	dt = startDate
	delta = (endDate - startDate) / (len(volumes) - 1)
	result = [ ]
	volume = 0
	startprice = round(float(prices[0]))
	lastprice = startprice
	for i in range(len(volumes) - 1):
		vol = int(volumes[i+1])
		# 6/24/2020: ECON DATA CUT OFF - ignore this "if"
		if False and dt > KOL_MARKETPLACE_OUTAGE: # Ignore old data after 
			vol = 0
		if vol == 0:
			price = 0
		else:
			price = round(float(prices[i+1]))
		result.append( [ dt, vol, price ] );
		volume = volume + vol
		if price >= 100:
			lastprice = price
		dt = dt + delta
	return (result, volume, lastprice, startprice)

# Go through the transactions (must be in order) and add them to the appropriate bucket
# in tbl
def fillInMissingData(tbl, xactions):
	limit = len(tbl) - 1
	lastprice = 0
	for i in range(len(tbl)):
		if tbl[i][2] > 100:
			lastprice = tbl[i][2]
	i = 0
	for xn in xactions:
		details = xn.split(",")
		dt = datetime.strptime(details[6] + " +0000", "%Y-%m-%d %H:%M:%S %z")
		while i < limit and dt > tbl[i+1][0]:
			i = i + 1
		oldvol = tbl[i][1]
		oldprice = tbl[i][2]
		newvol = int(details[4])
		newaggprice = int(details[5])
		tbl[i][1] += newvol
		tbl[i][2] = round((oldvol*oldprice + newaggprice) / (oldvol + newvol))
		lastprice = newaggprice / newvol
	volume = 0
	for i in range(len(tbl)):
		volume = volume + tbl[i][1]
	return (tbl, volume, lastprice)	

	
def lastPriceChange(xactions):
	if len(xactions) < 2:
		return 0
	xaction1 = xactions[len(xactions)-2].split(",")
	xaction2 = xactions[len(xactions)-1].split(",")
	return round( int(xaction2[5])/int(xaction2[4]) - int(xaction1[5])/int(xaction1[4]) )

def transactionLayer(xactions):
	height = 49 + 12*len(xactions)
	result = f'<DIV id=layer1 style="visibility:hidden;height:{height}px" >'
	for xaction in xactions:
		parts = xaction.split(",")
		singlePrice = int(parts[5]) / int(parts[4])
		result = result + parts[4] + " @ " + str(singlePrice) + ", " + parts[6] + "<br>\n"
	result = result + '<p><p><span id="close"><a href="javascript:setVisible(\'layer1\')">CLOSE</a></span>'
	result = result + '<br></DIV>\n'
	return result
	
def generateTrend(value):
	if value > 0:
		color = 'green'
		trend = 'greenup'
	elif value < 0:
		color = 'red'
		trend = 'reddown'
	else:
		color = 'black'
		trend = 'nochange'
	value = round(value)
	return f'<img src=http://{WIKILOC}/newmarket/newmarket/{trend}.gif> <font color={color}>{value:,}</font>'
	
#########################################################################
def prepareResponse(event, context):
	global state
	# Retrieve parameters
	state = "processing parameters"
	params = event['queryStringParameters']
	if params is None: params = { }
	# At the very least, we must have itemid and timespan
	if 'itemid' not in params or params['itemid'] == '':
		params['itemid'] = '194'	# Mr. A
	if 'timespan' not in params or params['timespan'] == '':
		span = '0'	# use specified starttime and endtime
	else:
		span = params['timespan']   # use period of time ending now
	# Compute endDate (rounded to previous half-hour)
	# Use specified time if provided and not overridden by a timespan
	# Else use Now
	if 'endtime' in params and params['endtime'] != '' and span == '0':
		endDate = datetime.fromtimestamp(int(params['endtime']), tz=timezone.utc)
	else:
		endDate = datetime.now(timezone.utc)
	m = endDate.minute
	if m >= 30:
		m = m - 30
	endDate = endDate - timedelta(seconds=endDate.second, minutes=m)
	# Compute startDate (defaulting to 1 day before endDate, rounded to previous
	# half-hour)
	if 'starttime' in params and params['starttime'] != '':
		startDate = datetime.fromtimestamp(int(params['starttime']), tz=timezone.utc)
		m = startDate.minute
		if m >= 30:
			m = m - 30
		startDate = startDate - timedelta(seconds=startDate.second, minutes=m)
	else:
		startDate = endDate - timedelta(hours=24)
	# startDate is either what we were given, or based on endDate and requested 
	# time span
	if span == '0':
		pass	# just use starttime and endtime we were given
	elif span == '1':
		startDate = endDate - timedelta(days=1)
	elif span == '2':
		startDate = endDate - timedelta(days=7)
	elif span == '3':
		startDate = endDate - timedelta(days=30)
	elif span == '4':
		startDate = BEGINNING_OF_HISTORY
	elif span == '5':
		startDate = endDate - timedelta(hours=12)
	elif span == '6':
		startDate = endDate - timedelta(days=2)
	elif span == '7':
		startDate = endDate - timedelta(days=14)
	# Invoke source graph page
	url = SOURCE
	delim = "?"
	for p in params:
		url = url + delim + p + "=" + params[p].replace(' ', '+') # Q&D urlencode
		delim = "&"
	#print("URL to open on Coldfront: " + url)
	state = "reading the Marketplace graph page"
	#noverify = ssl.SSLContext()
	f = request.urlopen(url) # Remove context=... when cert good
	b = f.read()
	b = b.decode("utf-8", "ignore")
	#print("Coldfront page received")
	# If not a valid ID, just return that text
	if (b.find('not a valid item ID') >= 0):
		return b
	# If span is All History ('4'), get startDate from prevstart parameter
	if span != '':
		startre = re.compile('name=prevstart value=([0-9]*)')
		startexp = startre.search(b)
		prevstart = startexp.group(1)
		prevts = datetime.fromtimestamp(int(prevstart), tz=timezone.utc)
		prevts = prevts - timedelta(hours=8)	# correct time
		#prevdate = prevts.strftime('%Y-%m-%d %H:%M:%S')
		#b = b.replace('Timespan:', 'Timespan ' + prevdate + ':')
		startDate = prevts
	# Set our display style
	state = "transforming the Marketplace graph page"
	b = re.sub('<link [^>]*marketstyle.css[^>]*>', STYLE, b)
	# Replace original links to source with ours
	rcon = event['requestContext']
	thisPage = "https://" + rcon['domainName'] + rcon['path']
	b = b.replace(SOURCE, thisPage)
	b = b.replace('greenup.gif', SOURCE_IMG+'greenup.gif')
	b = b.replace('reddown.gif', SOURCE_IMG+'reddown.gif')
	b = b.replace('leftarrow.gif', SOURCE_IMG+'leftarrow.gif')
	b = b.replace('rightarrow.gif', SOURCE_IMG+'rightarrow.gif')
	b = b.replace('nochange.gif', SOURCE_IMG+'nochange.gif')
	b = b.replace('translist.php', SOURCE_IMG+'translist.php')
	b = b.replace('/newmarket/itemgraph.php', rcon['path'])
	# Tried to replace out-of-line Javascript with inline - no luck
	b = b.replace(OLD_DATESTYLE, DATESTYLE)
	b = b.replace(OLD_MOOTOOLS, MOOTOOLS)
	b = b.replace(OLD_DATEPICKER, DATEPICKER)
	# It's not "all history", it's just 2 years
	b = b.replace("View all history", "View last 2 years")
	# Below is because the Reload Chart button gives us a page that does not have
	# the <graph> elements where we get our data.  Let's force a full reload.
	b = b.replace('name=happy', 'name=unhappy')
	# Fetch <graph> tag and extract data
	graphre = re.compile('<graph ([^>]*)>(.*)</graph>')
	graphxml = graphre.search(b)
	graphattrs = graphxml.group(1)
	#vmax = float(re.search("PYAxisMaxValue='([^']*)", graphattrs).group(1))
	#vmax = normalizeVmax(vmax)
	#pmax = float(re.search("SYAxisMaxValue='([^']*)", graphattrs).group(1))
	#pmin = float(re.search("SYAxisMinValue='([^']*)", graphattrs).group(1))
	graphdata = graphxml.group(2)
	#cmatches = re.findall("category name='([^']*)", graphdata)
	#for m in cmatches:
	#	print(m)
	# Get what data we can from KoL Marketplace's graph
	tbl, volume, lastprice, startprice = graphDataToGraphTable(graphdata, startDate, endDate)
	# Take additional steps if timespan includes when Marketplace failed
	# 6/24/2020: ECON DATA SUPPLY CUT OFF, use 2.0 data
	if False and endDate > KOL_MARKETPLACE_OUTAGE:
		itemid = params['itemid']
		if startDate < KOL_MARKETPLACE_OUTAGE:
			xactions = fetchXactions(itemid, KOL_MARKETPLACE_OUTAGE, endDate)
		else:
			xactions = fetchXactions(itemid, startDate, endDate)
		tbl, volume, lastprice = fillInMissingData(tbl, xactions)
		#if startDate >= KOL_MARKETPLACE_OUTAGE:
		#	econstartprice = priceGoingIn(itemid, startDate)
		#	if econstartprice > 99:
		#		startprice = econstartprice
		b = re.sub('CURRENT AVG PRICE: <font color=dodgerblue>[0-9.,]* meat',
				   f'CURRENT AVG PRICE: <font color=dodgerblue>{lastprice:,} meat',
				   b)
		b = re.sub('BOUGHT THIS TIMESPAN: <font color=dodgerblue>[0-9,]*',
				   f'BOUGHT THIS TIMESPAN: <font color=dodgerblue>{volume:,}',
				   b)
		changehtml = generateTrend(lastPriceChange(xactions))
		b = re.sub('Latest Price Change: <img [^>]*> <font color=[^>]*>[-,0-9.]*</font>',
				   f'Latest Price Change: {changehtml}', b)
		trendhtml = generateTrend(lastprice - startprice)
		b = re.sub('Timespan Price Trend: <img [^>]*> <font color=[^>]*>[-,0-9.]*</font>',
				   f'Timespan Price Trend: {trendhtml}', b)
		b = re.sub('<DIV id=layer1 .*</DIV>', transactionLayer(xactions), b, flags=re.DOTALL)
	# Determine axes and generate chart
	pmax = startprice
	pmin = startprice
	vmax = 0
	for i in range(len(tbl)):
		p = tbl[i][2]
		if p >= 100:
			if pmax < p: pmax = p
			if p < pmin: pmin = p
		v = tbl[i][1]
		if vmax < v : vmax = v
	vmax = normalizeVmax(vmax)
	b = b.replace('Chart.', generateChart2(startDate, endDate, tbl,
										   vmax, pmax, pmin, startprice))
	b = b.replace('Full Transaction List</a> ]',
				  'Full Transaction List</a> ]<br/><br/>'
				  + 'Page adapted for HTML5 by Aventuristo (#3028125)')
	# Correct the item name, if necessary
	korektoj = corrected_options()
	i = int(params['itemid'])
	if i in korektoj:
		goodname = korektoj[i]
		good_name = goodname.replace(' ', '_')
		lnk = re.compile('thekolwiki/index.php/[^ ]* target=.wiki.>.*?</a>')
		b = lnk.sub(f'thekolwiki/index.php/{good_name} target="wiki">{goodname}</a>', b)
	return b


def respond(err, res=None):
	return {
		'statusCode': '400' if err else '200',
		'body': err.message if err else res,
		'headers': {
			'Content-Type': 'text/html',
		},
	}

state = "I was screwing around with the page"

def exceptionInfo(trace, event):
	result = trace.replace("\n", "<br/>")
	print(trace)
	params = event['queryStringParameters']
	if params is None: 
		result = result + "== No parameters ==<br/>"
	else:
		result = result + "== Parameters ==<br/>"
		for p in params:
			v = params[p]
			result = result + f"{p}: {v}</br>"
	return result

timeoutResponse = '''
<html><head></head>
<body><h1>Sorry</h1>
<p>The page timed out while {}.  Please try reloading the page.
<p>- Aventuristo
</body></html>
'''

class MyTimeout(BaseException):
	pass

def timeout_handler(_signal, _frame):
	raise MyTimeout("Time exceeded")
	
def lambda_handler(event, context):
	'''Demonstrates a simple HTTP endpoint using API Gateway. You have full
	access to the request and response payload, including headers and
	status code.

	This visits a KoL Marketplace search page and relays its content to the caller.
	'''
	logger.info("## HANDLE LAMBDA")
	if 'source' in event and event['source'] == 'aws.events':
		return respond(None, 'Ping acknowledged')
	
	operation = event['httpMethod']
	if operation == 'GET':
		html = ""
		try:
			signal.signal(signal.SIGALRM, timeout_handler)
			when = math.floor(context.get_remaining_time_in_millis() / 1000) - 1
			signal.alarm(when)
			html = prepareResponse(event, context)
		except MyTimeout as e:
			logger.info("## TIMEOUT HANDLED")
			html = timeoutResponse.format(state)
		except Exception as e:
			logger.info("## OTHER EXCEPTION " + traceback.format_exc())
			html = exceptionInfo(traceback.format_exc(), event)
		finally:
			signal.alarm(0)
			return respond(None, html)
	else:
		return respond(ValueError('Unsupported method "{}"'.format(operation)))


# Code for local testing - remove from AWS version
class FakeContext:
	def get_remaining_time_in_millis(self):
		return 300000

if not on_aws():
	import sys
	import urllib.parse
	my_event = { }
	my_event['httpMethod'] = 'GET'
	my_event['queryStringParameters'] = { }
	if len(sys.argv) > 1: 
		# command line - just care about itemid
		my_event['queryStringParameters']['itemid'] = sys.argv[1]
		my_event['queryStringParameters']['timespan'] = '1'
		my_event['queryStringParameters']['noanim'] = '1'
	else:
		# web cgi
		method = os.environ['REQUEST_METHOD']
		if method == 'GET':
			qs = urllib.parse.parse_qs(os.environ['QUERY_STRING'])
		for q in qs:
			my_event['queryStringParameters'][q] = qs[q][0]
	my_event['requestContext'] = { }
	my_event['requestContext']['domainName'] = 'fedora2'
	my_event['requestContext']['path'] = '/right.here/'
	response = lambda_handler(my_event, FakeContext())
	print(f'Content-Type: {response["headers"]["Content-Type"]}')
	print()
	print(response['body'])
	

