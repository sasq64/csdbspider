

cbmconvert.dir:
	git clone https://github.com/sasq64/cbmconvert.git cbmconvert.dir

build/cbmconvert: cbmconvert.dir
	mkdir -p build
	cmake -S cbmconvert.dir -B build
	make -j -C build

install:
	cp build/cbmconvert build/zip2disk /usr/local/bin

all: build/cbmconvert

