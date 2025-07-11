from utils import flatten_dir, remove_in, temp_dir, collect, alpha_subdir, reorganize

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


def test_reorganize():
    """Test reorganize function for balancing directory sizes"""
    with temp_dir() as p:
        p.mkdir(exist_ok=True)
        remove_in(p)
        
        # Create directories with different file counts
        
        # Directory A with too many files (exceeds max_files=5)
        (p / "A").mkdir()
        for i in range(8):
            (p / "A" / f"file{i:02d}.txt").write_text(f"content{i}")
        
        # Directory B with normal amount of files
        (p / "B").mkdir()
        for i in range(3):
            (p / "B" / f"file{i:02d}.txt").write_text(f"content{i}")
        
        # Directory C with too few files (below min_files=2)
        (p / "C").mkdir()
        (p / "C" / "fileC.txt").write_text("content_c")
        
        # Directory D with too few files (below min_files=2)
        (p / "D").mkdir()
        (p / "D" / "fileD.txt").write_text("content_d")
        
        # Test reorganize with max_files=5, min_files=2
        reorganize(p, max_files=5, min_files=2)
        
        # Check that directory A was split into multiple directories
        assert (p / "A0").is_dir()
        assert (p / "A1").is_dir()
        assert not (p / "A").exists()  # Original A should be removed
        
        # Check file distribution in split directories
        a0_files = list((p / "A0").iterdir())
        a1_files = list((p / "A1").iterdir())
        assert len(a0_files) <= 5
        assert len(a1_files) <= 5
        assert len(a0_files) + len(a1_files) == 8  # Total files preserved
        
        # Check that B directory remained unchanged (within limits)
        assert (p / "B").is_dir()
        assert len(list((p / "B").iterdir())) == 3
        
        # Check that C and D were merged into CD (both had too few files)
        # Note: The function processes directories in alphabetical order and merges
        # small directories at the end if there are multiple
        assert (p / "CD").is_dir()
        assert not (p / "C").exists()
        assert not (p / "D").exists()
        cd_files = list((p / "CD").iterdir())
        # Should have files from both C and D
        assert len(cd_files) == 2  # Both fileC.txt and fileD.txt
        file_names = {f.name for f in cd_files}
        assert "fileC.txt" in file_names
        assert "fileD.txt" in file_names


def test_reorganize_edge_cases():
    """Test reorganize function edge cases"""
    with temp_dir() as p:
        p.mkdir(exist_ok=True)
        remove_in(p)
        
        # Test with single small directory (should remain unchanged)
        (p / "A").mkdir()
        (p / "A" / "file1.txt").write_text("content1")
        
        reorganize(p, max_files=10, min_files=5)
        
        # Single small directory should remain as is
        assert (p / "A").is_dir()
        assert len(list((p / "A").iterdir())) == 1

