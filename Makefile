# should only need to change LIBTINS to the libtins install prefix
# (typically /usr/local unless overridden when tins built)
LIBTINS = $(HOME)/libtins
EASYPROM = easy-prom-client-c
CPPFLAGS += -I$(LIBTINS)/include -I$(EASYPROM)
LDFLAGS += -L$(LIBTINS)/lib -L$(EASYPROM) -ltins -lpcap -lpthread -lpromclient
CXXFLAGS += -std=c++14 -O3 -Wall
EXENAME = pping-exporter

.PHONY: debug clean

$(EXENAME): pping-exporter.cpp $(EASYPROM)/libpromclient.a
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $(EXENAME) $< $(LDFLAGS)

$(EASYPROM)/libpromclient.a: $(EASYPROM)/promClient.h $(EASYPROM)/promClient.go
	make -C $(EASYPROM) lib

debug: CXXFLAGS += -g
debug: $(EXENAME)

clean:
	rm -f $(EXENAME)
