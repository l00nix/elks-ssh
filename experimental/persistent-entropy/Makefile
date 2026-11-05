# MIT. Experimental persistent-state daemon; never the normal server build.
override PROGRAM = dropbear
override OBJDIR = $(if $(PERSIST_OBJDIR),$(PERSIST_OBJDIR),obj-elks/persistent)
override OUTPUT = $(if $(PERSIST_OUTPUT),$(PERSIST_OUTPUT),dropbear-persistent)
ifneq ($(filter 1,$(TEST_ENTROPY) $(SERIAL_QEMU)),)
$(error Assisted entropy cannot be combined with persistent entropy)
endif
include Makefile.elks
CPPFLAGS += -DELKSSH_PERSISTENT_ENTROPY -DHAVE_GETRANDOM -DGRND_NONBLOCK=1 \
            -Dgetrandom=elkssh_dropbear_getrandom \
            -include experimental/persistent-entropy/dropbear-source.h
BR = feasibility/vendor/bearssl
BRFLAGS = -DBR_NO_ARITH_SHIFT=1 -I$(BR)/inc -I$(BR)/src
BR_OBJS = $(addprefix $(OBJDIR)/,br-hmac_drbg.o br-hmac.o br-sha2small.o br-dec32be.o br-enc32be.o)
$(PROGRAM_OBJS) $(LTC_OBJS): experimental/persistent-entropy/Makefile experimental/persistent-entropy/dropbear-source.h
EXTRA_OBJS += $(OBJDIR)/persistent-entropy.o $(OBJDIR)/persistent-source.o $(BR_OBJS)
$(OUTPUT): $(OBJDIR)/persistent-entropy.o $(OBJDIR)/persistent-source.o $(BR_OBJS)
$(OBJDIR)/persistent-entropy.o: experimental/persistent-entropy/entropy.c experimental/persistent-entropy/entropy.h
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(BRFLAGS) -c $< -o $@
$(OBJDIR)/persistent-source.o: experimental/persistent-entropy/dropbear-source.c experimental/persistent-entropy/dropbear-source.h experimental/persistent-entropy/entropy.h
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@
$(OBJDIR)/br-hmac_drbg.o: $(BR)/src/rand/hmac_drbg.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(BRFLAGS) -c $< -o $@
$(OBJDIR)/br-hmac.o: $(BR)/src/mac/hmac.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(BRFLAGS) -c $< -o $@
$(OBJDIR)/br-sha2small.o: $(BR)/src/hash/sha2small.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(BRFLAGS) -c $< -o $@
$(OBJDIR)/br-dec32be.o: $(BR)/src/codec/dec32be.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(BRFLAGS) -c $< -o $@
$(OBJDIR)/br-enc32be.o: $(BR)/src/codec/enc32be.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(BRFLAGS) -c $< -o $@
