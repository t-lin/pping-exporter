# Passive Ping Exporter
An extension of _pping_ (https://github.com/pollere/pping) to turn it into a Prometheus Exporter, enabling Prometheus and other clients to scrape & store the passive ping measurements.

**Tested in Ubuntu 20.04 with g++ 9.3.0 on x86-64 CPU.**

## Installing Prerequisites & Compiling
Required apt packages:
```bash
sudo apt-get install make cmake golang libpcap-dev
```

_pping-exporter_ depends on two other libraries: _easy-prom-client-c_ and _libtins_.
Both have been added as submodules and will need to be built first. The full compilation process is as follows:
```bash
git clone https://github.com/t-lin/pping-exporter.git
cd pping-exporter
git submodule init && git submodule update

# Compile easy-prom-client-c
cd easy-prom-client-c && make && cd ..

# Compile libtins
cd libtins && git submodule init && git submodule update
echo "set(CMAKE_POSITION_INDEPENDENT_CODE ON)" >> cmake/libtinsConfig.cmake.in
mkdir build && cd build && cmake ../ -DLIBTINS_ENABLE_CXX11=1
make && sudo make install && sudo ldconfig && cd ../..

# Compile pping-exporter (the binary will be placed in the current directory)
make
```

## New Flags
The following are new flags beyond _pping_'s existing flags:
 - `-a` or `--listen` to change the scrape endpoint (i.e. the listening address/port).
	 - Default listening endpoint is `0.0.0.0:9876`.
 - `-L` or `--localSubnet` to specify (in CIDR notation) local IP subnets to ignore. This flag can be specified multiple times.
	 - **Note:** If the `-l` or `--showLocal` flag is enabled, then this flag is ignored.

