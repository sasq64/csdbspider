from utils import flatten_dir, remove_in, temp_dir

def test_flatten_dir():
    with temp_dir() as p:
        p.mkdir(exist_ok=True)
        remove_in(p)

        (p / "a").mkdir()
        (p / "b").mkdir()
        (p / "c").mkdir()
        (p / "a" / "f1").write_text("one")
        (p / "b" / "f1").write_text("one-b")
        (p / "c" / "f2").write_text("two")
        (p / "d" / "e").mkdir(parents=True)
        (p / "d" / "e" / "f3").write_text("three")

        flatten_dir(p)
        assert (p / "f1").is_file()
        assert (p / "f2").is_file()
        assert (p / "f3").is_file()
        assert not (p / "d").exists()
        assert not (p / "a").exists()
        assert not (p / "b").exists()

