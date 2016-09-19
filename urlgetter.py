#!/usr/bin/python

import sys
import struct
import string
import socket
import re
import os
import subprocess
import shutil
import tempfile
import socket
import optparse
import exceptions
import copy
from select import *
from threading import *

from utils import *

import zipfile

import htmllib, formatter, urllib, urlparse, HTMLParser, htmlentitydefs
from BeautifulSoup import BeautifulSoup

from tools64 import unpack

class URLGetter :
	def __init__(self, url):
		
		self.contents = None
		
		self.realu = url
		
		self.uname = urllib.quote(url, '')

		x = urlparse.urlsplit(url)
		url = urlparse.urlunsplit((x[0], x[1], urllib.quote(x[2]), x[3], x[4]))
		self.url = url
		
		try :
			f = open('urlcache/' + self.uname, 'r')
			self.realu = f.readline().strip()
			self.contents = f.read(32*1024*1024)
			f.close()
			print "Using cached result"
			return
		except :
			pass
		
		socket.setdefaulttimeout(5)

		try :
			self.url = urllib.urlopen(url)
		except :
			print "Failed to get file"
			return
		
		newu = self.url.geturl()
		print '"%s" vs "%s"' % (url, newu)
		if newu != url :
			self.realu = newu
			x = urlparse.urlsplit(newu)
			u2 = urlparse.urlunsplit((x[0], x[1], urllib.quote(x[2]), x[3], x[4]))
			print "Reopening %s" % (u2)
			try :
				self.url = urllib.urlopen(u2)
			except :
				print "Failed to get file"
		
	def read(self):		
		if not self.contents :
			self.contents = self.url.read(64*1024*1024)
			try :
				os.mkdir('urlcache')
			except :
				pass
			f = open('urlcache/' + self.uname, 'w')
			f.write(self.realu + '\n')
			f.write(self.contents)
			f.close()
		return self.contents
	
	def geturl(self):
		return self.realu
	
	def getsoup(self):
		if not self.contents :
			self.read()
		return BeautifulSoup(self.contents)
