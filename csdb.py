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

import htmllib, formatter, urllib, urlparse, HTMLParser, htmlentitydefs
from BeautifulSoup import BeautifulSoup

from tools64 import unpack
from urlgetter import URLGetter

baseUrl = 'http://csdb.dk'
no_clobber = False
oneFilers = ['C64 256b Intro', 'C64 Music', 'C64 Graphics', 'C64 4K Intro', 'C64 Intro']

packArcs = []
possiblePack = []


def is_collection(x):
    return os.path.basename(x) in packArcs or 'releases' in x.lower() or 'graphics' in x.lower()


def prefer_download(x):
    p = 0
    if is_collection(x):
        p = 1
    elif 'work' in x.lower():
        p = 2
    return p


def longest_common_substring(s1, s2):
    m = [[0] * (1 + len(s2)) for i in xrange(1 + len(s1))]
    longest, x_longest = 0, 0
    for x in xrange(1, 1 + len(s1)):
        for y in xrange(1, 1 + len(s2)):
            if s1[x - 1] == s2[y - 1]:
                m[x][y] = m[x - 1][y - 1] + 1
                if m[x][y] > longest:
                    longest = m[x][y]
                    x_longest = x
            else:
                m[x][y] = 0
    return s1[x_longest - longest: x_longest]


class Release:
    typeLetters = {'One-File': 'o', 'Game': 'e', 'Graphics Coll': 'G', 'Graphic': 'g', 'Demo': 'd', 'Dentro': 'd',
                   'Intro': 'i', 'intro': 'i', 'Crack': 'c', 'Music Coll': 'M', 'Music': 'm', 'Diskmag': 's',
                   'Invit': 'v', 'Tool': 't', 'Misc': 'x'}

    def __init__(self, id, name='?', group='?', type='?', date='?', dls=[]):
        self.id = int(id)
        self.name = name
        self.group = group
        self.date = date
        self.type = type
        self.artist = '?'
        self.vote = '?'
        self.downloads = dls
        self.rating = ''
        self.creator = group
        self.loaded = False
        self.place = self.place2 = '?'
        self.compo = '?'
        self.party = '?'
        self.update()

    def __repr__(self):
        name = self.name.encode('ascii', 'ignore')
        return "[" + str(self.id) + "] " + name + " (" + self.type + ")"

    def update(self):

        m = re.compile('.*(\d\d\d\d)').match(self.date)
        if m:
            self.year = m.group(1)
        else:
            self.year = '????'

        self.tletter = '?'
        for t in Release.typeLetters:
            if self.type.find(t) >= 0:
                self.tletter = Release.typeLetters[t]
                break

        self.dict = {}
        for d in self.__dict__:
            self.dict[d] = fixname(unicode(self.__dict__[d]), False)

    def load(self):
        doc = URLGetter(baseUrl + '/release/?id=%s' % (self.id)).getsoup()
        if not doc:
            return
        start = doc.find(text=re.compile('MAIN CONTENT')).parent

        anyword = re.compile('\w+')
        name = '?'
        # gid = -1
        group = '?'
        type = '?'
        rdate = '?'
        artist = None
        downloads = None
        vote = None
        score = None
        compo = '?'
        party = '?'
        place2 = place = '?'

        print "Loading release"

        try:
            name = start.find('font').string
            release_by = start.find(text=re.compile('Release.*by'))
            # ag = release_by.findNext('a')
            # gid = int(re.compile('id=(\w+)').findall(ag.attrs[0][1])[0])
            group = release_by.findNext(text=anyword)
        except:
            pass

        try:
            vote = start.find(text=re.compile('.*votes.*'))
            if vote:
                # &nbsp; 7.7/10 (62 votes) &nbsp;
                m = re.match('[^\d]*([\d\.]+)', vote)
                score = m.group(1)
                if len(score) == 1:
                    score = score + '.0'
        except:
            pass

        try:
            credits = start.find(text=re.compile('Credits :'))
            gfx = credits.findNext(text=re.compile('Graphics'))
            artist = gfx.findNext('a').string
        except:
            pass

        try:
            type = start.find(text=re.compile('Type')).findNext(text=anyword)
            rdate = start.find(text=re.compile('Release.*ate')).findNext(text=anyword)
        except:
            pass
        try:
            downloads = start.find(text=re.compile('Download')).findNext('table').findAll(text=re.compile('tp://'))
        except:
            pass
        # print "'%s' by '%s' (%d), Release date '%s'" % (name, group, gid, rdate)
        try:
            rstart = start.find(text=re.compile('Released At'))
            party = rstart.findNext(text=anyword)
            compo = type
        except:
            pass

        try:
            astart = start.find(text=re.compile('Achievements'))
            print astart
            where = astart.findNext(text=anyword)
            if where:
                compo, party = where.split(' at ')
                print party
                place = where.next[where.next.find('#') + 1:]
                print place
        except:
            pass

        creator = group
        cstart = start.find(text=re.compile('Credits'))
        musicBy = codeBy = graphicsBy = None
        try:
            codeBy = cstart.findNext(text='Code').next.next.findNext(text=anyword)
        except:
            pass
        try:
            musicBy = cstart.findNext(text='Music').next.next.findNext(text=anyword)
        except:
            pass
        try:
            graphicsBy = cstart.findNext(text='Graphics').next.next.findNext(text=anyword)
        except:
            pass

        if type == 'C64 Music':
            creator = musicBy
        elif type == 'C64 Graphics':
            creator = graphicsBy

        print downloads

        if not artist:
            print "ARTIST < " + group
            artist = group

        if name != '?':
            self.name = fixhtml(name)
        if artist and artist != '?':
            self.artist = fixhtml(artist)
        if group != '?':
            self.group = fixhtml(group)
        if type != '?':
            self.type = fixhtml(type)
        if rdate != '?':
            self.date = fixhtml(rdate)
        if downloads:
            self.downloads = downloads
        if score:
            self.score = score
        if compo != '?':
            self.compo = fixhtml(compo)
            print self.compo
        if party != '?':
            self.party = fixhtml(party)
        if place != '?':
            self.place = int(place)
            self.place2 = "%02d" % self.place
        if creator:
            self.creator = fixhtml(creator)
        self.loaded = True
        self.update()

    def getdict(self):
        return self.dict

    def makename(self, templ):
        st = string.Template(templ)
        s = st.safe_substitute(self.getdict())
        s = re.sub('{\W*\?+\W*}', '', s)
        return s.replace('{', '').replace('}', '')

    def download_from_url(self, url, targetdir, to_d64=False, to_prg=False):
        # print "Original URL %s" % url
        url = url.rstrip(';')

        u = URLGetter(url)
        # print "Reading from url '%s'" % u.geturl()
        contents = u.read()
        # print "Got %d bytes" % len(contents)
        fname = fixname(os.path.basename(u.geturl()))

        # if self.type in oneFilers :
        #	to_prg = True

        pickOne = False
        print "ARCHIVE " + fname
        if fname in packArcs or 'releases' in fname.lower() or 'graphics' in fname.lower():
            pickOne = True
            to_prg = True

        # if to_prg == Auto :
        #	if self.type in oneFilers :
        #		to_prg = Always
        #	else :
        #		to_prg = Never

        if u.geturl().find('intros.c64.org') >= 0:
            fname = 'intro.prg'
        print "FNAME: " + fname

        filter = None
        # if to_prg and self.name and self.name != '?' :
        # filter = fixname(self.name).lower()

        try:
            path = tempfile.mkdtemp()
            fullname = path + '/' + fname.lstrip('-')
            f = open(fullname, 'w')
            f.write(contents)
            f.close()
            print "Handling file '%s' to '%s'" % (fullname, targetdir)
            if to_d64 and to_prg:
                if 'oicgm'.find(self.tletter) >= 0:
                    unpack(fullname, targetdir, False, True, filter)
                else:
                    unpack(fullname, targetdir, filter)
            else:
                unpack(fullname, targetdir, to_d64, to_prg, filter)
        # except :
        #	print "FAILED to unpack file"
        finally:
            shutil.rmtree(path)

        count = 0
        res = os.listdir(targetdir)

        best = None
        maxl = 0
        for r in res:
            rs = os.path.splitext(r)
            ext = rs[1].upper()
            base = rs[0].lower()

            if ext == '.PRG' or ext == '.D64' or ext == '.TAP' or ext == ".CRT" or ext == ".G64":
                count += 1
            if ext == ".PRG" and pickOne:
                base = re.sub(r'[^\w]', '', base)
                name = re.sub(r'[^\w]', '', self.name.lower())
                creator = re.sub(r'[^\w]', '', self.creator.lower())
                n = longest_common_substring(name, base)
                c = longest_common_substring(creator, base)
                l = len(n) + len(c)
                if l > maxl:
                    if best:
                        os.remove(targetdir + '/' + best)
                    best = r
                    maxl = l
                else:
                    os.remove(targetdir + '/' + r)
        if best:
            print "Matched %s with %s" % (self.name, best)

        if count == 0:
            print "Download did not contain any C64 files."
            for r in res:
                os.remove(targetdir + '/' + r)
            raise IOError
            return
        elif count > 4 and not pickOne and (fname not in possiblePack):
            print "Directory '%s' contains %d files" % (targetdir, count)
            possiblePack.append(fname)

    def download(self, to_d64=False, to_prg=False, templ='DEMOS/$group/$name {- $year} {($type)}'):

        targetdir = self.makename(templ)
        targetdir = targetdir.replace('?', '')

        res = []
        try:
            res = os.listdir(targetdir)
        except exceptions.OSError:
            pass

        if no_clobber and len(res) > 0:
            print "Leaving non-enpty directory alone"
            return

        success = False

        downloads = sorted(self.downloads, key=prefer_download)

        while not success:
            for url in downloads:
                try:
                    self.download_from_url(url, targetdir, to_d64, to_prg)
                    success = True
                    break
                except Exception, e:
                    print e
                    print "Download failed"
                    continue

            if not self.loaded and not success:
                self.load()
                continue
            else:
                break


class Group:
    def __init__(self, id, name, tla, rels):
        self.id = id
        self.name = name
        self.tla = tla
        self.releases = rels


class CSDBSpider:
    def __init__(self):
        pass

    @staticmethod
    def getReleases(url, max=-1, full=False):
        "Find all releases on a given URL"
        if url[:4] != 'http':
            url = baseUrl + '/' + url
        rels = []
        doc = URLGetter(url).getsoup()

        start = doc.find(text=re.compile('MAIN CONTENT')).parent
        if start:
            doc = start

        relp = re.compile('/release/\?id=(\d+)')
        alist = doc.findAll('a', href=relp)
        # print alist
        for a in alist:
            # print a.contents
            for at in a.attrs:
                # print at
                if at[0] == 'href':
                    m = relp.match(at[1])
                    if a.contents:
                        r = Release(int(m.group(1)), a.contents[0])
                    else:
                        r = Release(int(m.group(1)))
                    if full:
                        r.load()
                    rels.append(r)
            if max > 0 and len(rels) >= max:
                break
        return rels

    @staticmethod
    def findGroups(name):
        groups = []
        print '"%s"' % (name)
        doc = URLGetter(baseUrl + '/search/?seinsel=groups&search=%s' % (name)).getsoup()
        # doc = BeautifulSoup(urllib.urlopen('http://noname.c64.org/csdb/search/?seinsel=groups&search=%s' % name))
        try:
            res = doc.ol.findAll('a')
        except:
            print 'Direct result, figuring out ID'
            r = re.compile('/group/\?id=(\d+).*votes')
            x = doc.find(href=r)
            id = int(r.findall(x.attrs[0][1])[0])
            return [(id, name)]

        for r in res:
            id = int(re.compile('id=(\w+)').findall(r.attrs[0][1])[0])
            name = r.string
            groups.append((id, name))
        return groups

    @staticmethod
    def findReleases(name):
        return CSDBSpider.getReleases(baseUrl + "/search/?seinsel=releases&search=" + name + "&all=1")

    @staticmethod
    def getGroup(id):
        doc = URLGetter(baseUrl + '/group/?id=%s' % (id)).getsoup()
        start = doc.find(text=re.compile('MAIN CONTENT')).parent
        group = start.find('font')
        name = fixhtml(group.string.strip())
        t = re.compile('\((.*)\)').findall(group.next.next)
        tla = ''
        if t:
            tla = t[0]
        reltab = doc.body.find(text=re.compile('Releases')).findNext('table')
        alist = reltab.findAll('tr')
        releases = []
        url = ''
        for tr in alist:

            # print tr

            rname = '???????'
            rid = -1
            url = ''
            event = ''
            year = '?'
            type = '?'

            try:
                f = tr.findAll('font')
                year = f[1].string.strip()
                if len(f) >= 3:
                    type = fixhtml(f[2].string).strip()
            except:
                pass

            t = tr.find('a', href=re.compile('/release/\?'))
            if t:
                rname = fixhtml(t.string).strip()

                print rname

                try:
                    rid = int(re.compile('id=(\w+)').findall(t.attrs[0][1])[0])
                except:
                    print "Could not parse ID"
                    pass

            tds = tr.findAll('td')
            year = tds[2].font.string
            type = tds[3].font.string

            if type.startswith('&nbsp;'):
                type = type[6:]

            print "       " + type

            if type == 'Crack':
                print "Skipping Crack " + rname
                continue

            t = tr.find('a', href=re.compile('/release/download'))
            if t:
                url = baseUrl + t.attrs[0][1]
                url = url.strip()
            print url
            releases.append(Release(rid, rname, name, type, year, [url]))

        return Group(id, name, tla, releases)


# Main operation
# Derive a set of webpages from where to find all release links
# List or download them
# Can be - set of groups webpages
# Top demos page
# 
def main(argv):
    global no_clobber
    global packArcs

    for f in open('packarcs.txt').readlines():
        f = f.strip()
        if len(f) > 1 and f[0] != '#' and f[0] != ';':
            packArcs.append(f)

    csdb = CSDBSpider()
    rel = None
    group = None
    # while True:
    # line = raw_input('>')
    # line = argv

    p = optparse.OptionParser(
        usage="usage: %prog [options] <command> [args...]\n\nCommands:\n findgrp <groupname> = Search for a group by name\n list = List releases (with filtering) for a groupid\n findrel = Find releases")
    p.add_option("-D", "--download",
                 action="store_true", dest="download", default=False,
                 help="Download matching releases")
    p.add_option("-m", "--max",
                 type="int", dest="max", action="store", default=10,
                 help="Max number of releases")
    p.add_option("-g", "--group",
                 type="int", dest="groupid", action="append",
                 help="Set the Demo group ID to use")
    p.add_option("-d", "--to-d64",
                 action="store_true", dest="to_d64", default=False,
                 help="Convert all formats to D64 (disk images)")
    p.add_option("-p", "--to-prg",
                 action="store_true", dest="to_prg", default=False,
                 help="Convert all formats to disk PRG files")
    p.add_option("-N", "--no-clobber",
                 action="store_true", dest="no_clobber", default=False,
                 help="Dont write files to non-empty directories")
    p.add_option("-T", "--template",
                 type="string", dest="template", default='DEMOS/%group/%name{ - %year}{ (%type)}',
                 help="Template for output files")

    p.add_option("-G", "--redo-groups",
                 action="store_true", dest="redo_groups", default=False,
                 help="Add all previously cached groups to the grouplist")

    p.add_option("-F", "--filter", dest="filter", default='A', help=
    '''Filter out only certain types of productions - each letter in the given argument represents one type of release; 'd' = demo, 'o' = one-file demo / dentro, 'i' = intro, 'v' = invitro, 'e' = game, 'c' = crack 'm' = music, 'g' = graphics, 'M' = music collection, 'G' = graphics collection, 't' = tool, 's' = diskmag, 'x' = misc. 'A' = All!''')

    opts, arguments = p.parse_args()
    opts.template = opts.template.replace('%', '$')

    if not len(arguments):
        print "Try `csdb --help` for more information\n\nExample:\n> csdb find horizon\n> csdb list -g 2315 -F doiv\n> csdb dl -g 2315 -F io"

    no_clobber = opts.no_clobber

    #	print opts
    #	print arguments

    if opts.redo_groups:
        if not opts.groupid:
            opts.groupid = []

        b2 = urllib.urlencode(baseUrl)
        print b2
        gr = re.compile(b2 + '%2Fgroup%2F%3Fid%3D(\d+)')

        res = os.listdir('urlcache')
        for r in res:
            m = gr.match(r)
            if m:
                opts.groupid.append(int(m.group(1)))

    print opts.groupid
    what = opts.filter

    rels = []

    # l = argv #line.split()
    l = arguments;
    if len(l) >= 1:
        if l[0] == 'findgrp':
            groups = csdb.findGroups(l[1])
            if groups:
                for g in groups:
                    print '(%d) %s' % g
            else:
                print "Could not find any groups"
        elif l[0] == 'group':
            if not len(opts.groupid):
                print "You must specify a groupid!"
                return
            for gid in opts.groupid:
                # try :
                group = csdb.getGroup(gid)
                if group:
                    print 'Trying to download releases from %s' % group.name
                    print "\n"
                    group.releases.sort(lambda x, y: x.year > y.year)
                    rels.extend(group.releases)
                # print rels

        elif l[0] == 'findrel':
            print "Searching for %s" % l[1]
            rels = CSDBSpider.findReleases(l[1])

        elif l[0] == 'toplist':
            print "Getting Release info for the Top %d" % opts.max
            rels = CSDBSpider.getReleases(baseUrl + '/toplist.php?type=release&subtype=(1%2C2)', opts.max, True)

        elif l[0] == 'topgames':
            print "Getting Release info for the Top %d" % opts.max
            rels = CSDBSpider.getReleases(baseUrl + '/toplist.php?type=release&subtype=%2811%29', opts.max, True)

        elif l[0] == 'topcracks':
            print "Getting Release info for the Top %d" % opts.max
            rels = CSDBSpider.getReleases(baseUrl + '/toplist.php?type=release&subtype=%2820%29', opts.max, True)

        elif l[0] == 'topprev':
            print "Getting Release info for the Top %d" % opts.max
            rels = CSDBSpider.getReleases(baseUrl + '/toplist.php?type=release&subtype=%2819%29', opts.max, True)
        elif l[0] == 'topgfx':
            print "Getting Release info for the Top %d" % opts.max
            rels = CSDBSpider.getReleases(baseUrl + '/toplist.php?type=release&subtype=%289%29', opts.max, True)
        elif l[0] == 'easyflash':
            rels = CSDBSpider.getReleases(baseUrl + '/search/?seinsel=releases&search=%5Beasyflash%5D&all=1', opts.max,
                                          True)
        elif l[0] == 'event':

            events = []
            if l[1] == 'theparty':
                events = [54, 53, 32, 18, 10, 25, 24, 3, 6, 7, 29, 514]
            elif l[1] == 'datastorm':
                events = [1577, 1681, 1846, 2001, 2158]
            elif l[1] == 'breakpoint':
                events = [453, 634, 884, 1038, 1210, 1358, 1501, 1613]
            elif l[1] == 'edison':
                events = [1788, 1935, 2046, 2225, 2385, 2506]
            elif l[1] == 'lcp':
                events = [52, 62, 41, 348, 487, 756, 931, 1506, 1693, 1422]
            elif l[1] == 'bfp':
                events = [1050, 1225, 2092]
            elif l[1] == 'x':
                events = [30, 76, 26, 211, 39, 31, 700, 966, 1362, 1610, 1708, 2082]
            elif l[1] == 'gubbdata':
                events = [1928, 2075, 2316, 2453]
            elif l[1] == 'assembly':
                events = [117, 123, 127, 173, 175, 185, 194, 47, 256, 51, 346, 606, 784, 929, 1100, 1315, 1454, 1564,
                          1662, 1840, 1950, 2393]
            elif l[1] == 'mekka':
                events = [59, 131, 104, 28, 8, 250]
            elif l[1] == 'floppy':
                events = [43, 27, 251, 448, 709, 878]
            else:
                events = [int(l[1])]

            rels = []
            for evt in events:
                rels = rels + CSDBSpider.getReleases(baseUrl + '/event/?id=' + str(evt), opts.max, True)

        if rels:

            if what != 'A':
                for r in rels:
                    r.load()
                rels = [r for r in rels if what.find(r.tletter) >= 0]

            if opts.download:
                print "\nDownloading releases"
            else:
                print "\nListing releases"
            i = 1
            for r in rels:
                if r:
                    r.i = "%d" % i
                    r.i2 = "%02d" % i
                    r.i3 = "%03d" % i
                    print r
                    if opts.download:
                        r.update()
                        r.download(opts.to_d64, opts.to_prg, templ=opts.template)
                    i += 1
                else:
                    print "None release ?!"

            if possiblePack:
                print "### Possible packs"
                for p in possiblePack:
                    print p


if __name__ == "__main__":
    main(sys.argv[1:])
