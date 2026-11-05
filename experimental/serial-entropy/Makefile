# MIT. Isolated assisted server, never the normal or legacy QEMU build.
SERIAL_BAUD ?= 1200
override PROGRAM = dropbear
override OBJDIR = obj-elks/serial-$(if $(filter 1,$(SERIAL_QEMU)),qemu,hardware)-$(SERIAL_BAUD)
override OUTPUT = $(if $(filter 1,$(SERIAL_QEMU)),dropbear-serial-qemu,dropbear-serial)
ifeq ($(SERIAL_DIAGNOSTICS),1)
override OBJDIR = obj-elks/serial-diagnostic-$(if $(filter 1,$(SERIAL_QEMU)),qemu,hardware)-$(SERIAL_BAUD)
override OUTPUT = $(if $(filter 1,$(SERIAL_QEMU)),dropbear-serial-diagnostic-qemu,dropbear-serial-diagnostic)
endif
ifneq ($(filter 1,$(TEST_ENTROPY)),)
$(error Legacy TEST_ENTROPY cannot be combined with serial entropy)
endif
include Makefile.elks
CPPFLAGS += -DELKSSH_SERIAL_ENTROPY -DHAVE_GETRANDOM -DGRND_NONBLOCK=1 \
            -Dgetrandom=elkssh_serial_getrandom -include experimental/serial-entropy/entropy.h \
            -DELKSSH_ENTROPY_BAUD=B$(SERIAL_BAUD)
ifeq ($(SERIAL_DIAGNOSTICS),1)
CPPFLAGS += -DELKSSH_ENTROPY_DIAGNOSTIC
endif
EXTRA_OBJS += $(OBJDIR)/serial-entropy.o
$(OUTPUT): $(OBJDIR)/serial-entropy.o
$(OBJDIR)/serial-entropy.o: experimental/serial-entropy/entropy.c experimental/serial-entropy/entropy.h experimental/serial-entropy/Makefile
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(CPPFLAGS) \
	    -DELKSSH_ENTROPY_DEVICE=\"$(if $(filter 1,$(SERIAL_QEMU)),/dev/ttyS1,/dev/ttyS0)\" -c $< -o $@
