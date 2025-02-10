from pathlib import Path
from bs4 import BeautifulSoup
from csdb import search_soup

def test_search():
    t = Path("testdata/oxyron.html").read_text()
    soup = BeautifulSoup(t, "html.parser")
    result = search_soup(soup)
    assert len(result) == 1 and result[0] == 7
    t = Path("testdata/crackers.html").read_text()
    soup = BeautifulSoup(t, "html.parser")
    result = search_soup(soup)
    assert len(result) > 10