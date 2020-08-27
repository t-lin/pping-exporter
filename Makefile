# should only need to change LIBTINS to the libtins install prefix
# (typically /usr/local unless overridden when tins built)
LIBTINS = $(HOME)/libtins
EASYPROM = easy-prom-client-c
CPPFLAGS += -I$(LIBTINS)/include -I$(EASYPROM)
LDFLAGS += -L$(LIBTINS)/lib -L$(EASYPROM) -ltins -lpcap -lpthread -lpromclient
CXXFLAGS += -std=c++14 -O3 -Wall
EXENAME = pping-exporter

.PHONY: debug clean

$(EXENAME): pping-exporter.cpp
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $(EXENAME) $< $(LDFLAGS)

debug: CXXFLAGS += -g
debug: $(EXENAME)

clean:
	rm -f $(EXENAME)
