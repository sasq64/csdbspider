## csdbspider

Tool do collect, download, convert and name C64 releases from CSDb

### Requirements

Uses BeautifulSoup to parse HTML files;

`pip3 install beautifulsoup4`

For unpacking and repacking; `unrar`, `lha`, `7z`, and `tar`/`gz`

(Get them through your package manager)

For C64 format conversion; `cbmconvert` and `zip2disk`

You can get the source code here; https://github.com/sasq64/cbmconvert

### Usage

For instance;

`./csdb.py -l toplist -m 99 -t "Top/{rank:02}. {group} - {title}{ ({year})}"`

* You can collect releases from toplists, groups or events.

* After collection releases can be filtered by type, year & rating

* Downloads for a release will be tried in order, and will be unpacked and converted to PRG or D64 if possible.

* Metadata is fetched through CSDbs webservice, and will be cached. Also, metadata
for many popular releases and groups is precached in this repo to offload CSDb.

* Downloads are also cached, so once you downloaded a particular set of releases, you can change the template and run again and it should finish quickly without downloading (almost) anything.