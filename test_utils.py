from utils import flatten_dir, remove_in, temp_dir, collect, alpha_subdir

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


def test_collect():
    """Test collect function for grouping files into series"""
    with temp_dir() as p:
        p.mkdir(exist_ok=True)
        remove_in(p)
        
        # Create test files that should be collected
        (p / "Magazine01 (Publisher A).adf").write_text("one")
        (p / "Magazine02 (Publisher A).adf").write_text("two")
        (p / "Magazine03 (Publisher A).adf").write_text("three")
        (p / "Magazine04 (Publisher A).adf").write_text("four")
        (p / "Magazine05 (Publisher A).adf").write_text("five")
        
        # Create some files that shouldn't be collected (below min_files)
        (p / "Other01 (Publisher B).adf").write_text("other1")
        (p / "Other02 (Publisher B).adf").write_text("other2")
        
        # Create target directory (collect creates under "target")
        (p / "target").mkdir(exist_ok=True)
        
        # Change to test directory to run collect
        import os
        orig_cwd = os.getcwd()
        os.chdir(p)
        
        try:
            collect(p, min_files=5)
            
            # Check that Magazine files were collected
            assert (p / "target" / "Magazine (Publisher A)").is_dir()
            assert (p / "target" / "Magazine (Publisher A)" / "Magazine01 (Publisher A).adf").is_file()
            assert (p / "target" / "Magazine (Publisher A)" / "Magazine05 (Publisher A).adf").is_file()
            
            # Check that Other files were NOT collected (below min_files)
            assert (p / "Other01 (Publisher B).adf").is_file()
            assert (p / "Other02 (Publisher B).adf").is_file()
            
        finally:
            os.chdir(orig_cwd)


def test_alpha_subdir():
    """Test alpha_subdir function for organizing files by first letter"""
    with temp_dir() as p:
        p.mkdir(exist_ok=True)
        remove_in(p)
        
        # Create test files
        (p / "Apple.txt").write_text("apple")
        (p / "Banana.txt").write_text("banana")
        (p / "Cherry.txt").write_text("cherry")
        (p / "Apricot.txt").write_text("apricot")
        (p / "Blueberry.txt").write_text("blueberry")
        
        # Create a file that should be ignored (single character)
        (p / "Z").write_text("z")
        
        # Create a file that should be ignored (starts with dash)
        (p / "-test.txt").write_text("test")
        
        alpha_subdir(p)
        
        # Check that files were moved to appropriate subdirectories
        assert (p / "A" / "Apple.txt").is_file()
        assert (p / "A" / "Apricot.txt").is_file()
        assert (p / "B" / "Banana.txt").is_file()
        assert (p / "B" / "Blueberry.txt").is_file()
        assert (p / "C" / "Cherry.txt").is_file()
        
        # Check that ignored files stayed in place
        assert (p / "Z").is_file()
        assert (p / "-test.txt").is_file()
        
        # Check that original files are gone
        assert not (p / "Apple.txt").exists()
        assert not (p / "Banana.txt").exists()

