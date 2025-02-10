from pathlib import Path

from utils import temp_dir
from tools64 import unpack, Release

def test_unpack():
    td = Path("testdata")
    with temp_dir() as out:
        unpack(td / "with_lnx.zip", out)
        assert (out / "CHARLATA.d64").exists()
    with temp_dir() as out:
        unpack(td / "with_lnx.zip", out, d64_to_prg=True)
        assert (out / "charlatan.beyond.prg").exists()
    with temp_dir() as out:
        unpack(td / "with_zip.rar", out)
        assert (out / "ad.d64").exists()
    with temp_dir() as out:
        unpack(td / "skaaneland.zip", out)
        assert (out / "Skaaneland [Side 1].d64").exists()
        assert (out / "Skaaneland [Side 2].d64").exists()
    with temp_dir() as out:
        unpack(td / "SPACEACA.T64.gz", out)
        assert (out / "SPACEACA.T64").exists()

def test_format():
    rel = Release(title="Cowboys", group="Cats", place=3)
    rel2 = Release(title="Cowboys", group="Cats", place=-1, year=1984)
    assert rel.format("{event}{{year}}") == ""
    assert rel.format("{{place:02}. }") == "03. "
    assert rel2.format("{{place:02}. }{title}{ ({year})}") == "Cowboys (1984)"
    assert rel.format("{{place:02}. }{title}{ ({year})}") == "03. Cowboys"
    assert rel.format("{{place:02}. }{title} {qyear}") == "03. Cowboys XXXX"
    t = "{event}/{compo}/{{place:02}. }{group} - {title}"
    assert rel.format(t) == "//03. Cats - Cowboys"
    assert rel2.format(t) == "//Cats - Cowboys"
