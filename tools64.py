#!/usr/bin/python

import sys
import string
import re
import os
import glob
import subprocess
import shutil
import tempfile
import socket
import optparse
import exceptions
import copy
from threading import *

import urllib
from utils import dospath,fat32names,fixname

import zipfile

is_win = False

def unpack(archive, targetdir, to_d64 = False, to_prg = False, filter = None):
	"Generic unpack for archives containing c64 programs"

	try :
		os.makedirs(targetdir)
	except :
		pass

	res = os.listdir(targetdir)
	for r in res :
		os.remove(targetdir + '/' + r)

	realname = archive

	if is_win :
		archive = dospath(archive)
		targetdir = dospath(targetdir)

	ext = os.path.splitext(archive)[1].upper()

	while True :

		print archive

		if ext == '.GZ' :
			if subprocess.call(['gunzip', archive]) :
				# Sometimes gzip files aren't.
				os.rename(archive, archive[:-3])
			archive = archive[:-3]
			realname = realname[:-3]
			ext = os.path.splitext(archive)[1].upper()

		if ext == '.ZIP' :
			subprocess.call(['unzip', '-n', '-j', archive, '-d', targetdir])
		elif ext == '.RAR' :
			subprocess.call(['unrar', 'e', '-o-', '-y', archive], cwd=targetdir)
		elif ext == '.TAR' :
			subprocess.call(['tar', '-xf', archive, targetdir + '/'])
		elif ext == '.LHA' or archive[-4:].upper() == '.LZH' :
			subprocess.call(['lha', 'x', archive], cwd = targetdir)
		else :			
			f = open(archive, 'r')
			header = f.read(8)
			if header[:4] == 'PK\x03\x04' or header[:4] == 'PK\x05\x06' :
				print "Looks like a zipfile"
				ext = '.ZIP'
				continue
			elif header[:4] == 'Rar!' :
				print "Looks like a RAR file"
				ext = '.RAR'
				continue
			else :
				print archive
				n = fixname(urllib.unquote(os.path.basename(realname)))
				print 'Copying unknown file to %s' % (n)
				shutil.copyfile(archive, targetdir + '/' + n)
		break;
	
	res = os.listdir(targetdir)
	for r in res :
		if r[:2] == '1!' :
			subprocess.call(['zip2disk', r[2:]], cwd=targetdir)
			for f in glob.glob("%s/?!%s" % (targetdir, r[2:])) :
				os.remove(f)
			#for i in xrange(6) :
			#	os.remove('%s/%d!%s' % (targetdir, i+1, r[2:]))
		elif r[-3:].upper() == 'T64' :
			subprocess.call(['cbmconvert', '-t', r], cwd=targetdir)
			os.remove(targetdir + '/' + r)
		elif r[-3:].upper() == 'LNX' :
			n = os.path.splitext(fixname(urllib.unquote(os.path.basename(realname))))[0] + '.d64'
			subprocess.call(['cbmconvert', '-D4', n, '-l', r], cwd=targetdir)
			os.remove(targetdir + '/' + r)			
		elif r[-3:].upper() == 'P00' :
			f = open(targetdir + '/' + r, 'r')
			x = f.read(65536)
			f.close()
			
			f = open(targetdir + '/' + r[:-3] + 'prg', 'w')
			f.write(x[0x1a:])
			f.close()
			#subprocess.call(['cbmconvert', r], cwd=targetdir)
			os.remove(targetdir + '/' + r)
		else :
			pass

	d64 = None
	if to_prg :
		res = os.listdir(targetdir)
		d64 = None
		for r in res :
			if r[-4:].upper() == '.D64' :
				rc = subprocess.call(['cbmconvert', '-N', '-d', r], cwd=targetdir)
				if rc != 0 :
					print "### CBMCONVERT RETURNED %d" % (rc,)
				foundprog = False
				for r2 in os.listdir(targetdir) :
					if r2[-4:].upper() == '.DEL' or r2[-4:].upper() == '.USR':
						os.remove(targetdir + '/' + r2)
					elif r2[-4:].upper() == '.PRG' :
						foundprog = True
				if foundprog :
					os.remove(targetdir + '/' + r)
			
	elif to_d64 :
		res = os.listdir(targetdir)
		progs = []
		for r in res :
			if r[-4:].upper() == '.PRG' :
				progs.append(r)
		if progs :
			n = os.path.splitext(fixname(urllib.unquote(os.path.basename(realname))))[0] + '.d64'
			print "Putting" + str(progs) + "into " + n
			subprocess.call(['cbmconvert', '-n','-D4', n] + progs, cwd=targetdir)
			for p in progs :
				os.remove(targetdir + '/' + p)

	if filter :
		res = os.listdir(targetdir)
		fsplit = filter.split()
		maxhits = 0
		bestr = None
		for r in res :
			rl = r.lower()
			rsplit = os.path.splitext(rl)
			print "Considering %s with ext %s" % (rl, rsplit[1])
			if rsplit[1] == '.prg' :
				hits = 0
				for f in fsplit :
					if rl.find(f) >= 0 :
						hits+=1
				if hits > maxhits :
					bestr = r
					maxhits = hits
		if bestr :
			print "Filtered out all except " + bestr
			for r in res :
				if r != bestr :
					os.remove(targetdir + '/' + r)

	res = os.listdir(targetdir)
	for r in res :
		dname = os.path.splitext(r)
		ext = dname[1].upper()
		if ext == '.PRG' or ext == '.D64' or ext == '.T64' or ext == '.DIZ' or ext == '.TXT' or ext == '.REU' or ext == ".G64" or ext == ".CRT" or ext == ".TAP" :
			pass
		elif ext == '.SEQ' :
			os.rename(targetdir + '/' + r, targetdir + '/' + dname[0] + '.prg')
		else :
			sz = os.path.getsize(targetdir + '/' + r)
			if sz == 174848 :
				os.rename(targetdir + '/' + r, targetdir + '/' + dname[0] + '.d64')
			else :
				print "Checking if %s is a PRG" % (r,)
				f = open(targetdir + '/' + r)
				x = f.read(2)
				if x == '\x01\x08' :
					os.rename(targetdir + '/' + r, targetdir + '/' + r + '.prg')
				else :
					os.remove(targetdir + '/' + r)

	fat32names(targetdir)

