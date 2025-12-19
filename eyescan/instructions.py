def prepare_bits(data, length):
    return format(data, f'#0{length+2}b')[2:][::-1]


START_COMMAND = prepare_bits(0x6D, 8)
END_COMMAND = prepare_bits(0x9B, 8)
BYPASS_COMMAND = prepare_bits(0xff, 8)
COMMANDS = [
    # R0 opcodes
    {
        'SELECT_CFG': prepare_bits(0x3500, 24),
        'SELECT_CORE_INPUTS': prepare_bits(0x3000, 24),
        'SELECT_READBACK': prepare_bits(0x3300, 24)
    },
    # R1 opcodes
    {
        'SELECT_CFG': prepare_bits(0x35, 24),
        'SELECT_CORE_INPUTS': prepare_bits(0x30, 24),
        'SELECT_READBACK': prepare_bits(0x33, 24)
    }
]


def format_field(value, length):
    return format(value, f'#0{length + 2}b')[-length:][::-1]


class ws_char:

    def __init__(self,
                 phase_offset,
                 bit_select,
                 voltage_offset,
                 testfail=False,
                 ecount=False,
                 esword=False,
                 es=False,
                 voltage_offset_override=False,
                 scan_len=False,
                 scan_run=False,
                 scan_done=False):
        self.phase_offset = format_field(phase_offset, 7)
        self.bit_select = format_field(bit_select, 5)
        self.voltage_offset = format_field(voltage_offset, 6)
        self.testfail = format_field(testfail, 1)
        self.ecount = format_field(ecount, 12)
        self.esword = format_field(esword, 8)
        self.es = format_field(es, 4)
        self.voltage_offset_override = format_field(voltage_offset_override, 1)
        self.scan_len = format_field(scan_len, 2)
        self.scan_run = format_field(scan_run, 1)
        self.scan_done = format_field(scan_done, 1)

    def to_binary(self):
        body = (self.testfail + self.ecount + self.esword + self.es +
                self.phase_offset + self.bit_select + self.voltage_offset +
                self.voltage_offset_override + self.scan_len + self.scan_run +
                self.scan_done) * 4
        return "0" + "0" + body + "0"


class ws_cfg:

    def __init__(self,
                 core_we_head=False,
                 core_we=False,
                 tuning_we=False,
                 debug_we=False,
                 char_we=False,
                 unshadowed_we=False,
                 core_we_tail=False,
                 tuning_we_tail=False,
                 debug_we_tail=False):
        self.core_we_head = format_field(core_we_head, 1)
        self.core_we = format_field(core_we, 1)
        self.tuning_we = format_field(tuning_we, 1)
        self.debug_we = format_field(debug_we, 1)
        self.char_we = format_field(char_we, 1)
        self.unshadowed_we = format_field(unshadowed_we, 1)
        self.core_we_tail = format_field(core_we_tail, 1)
        self.tuning_we_tail = format_field(tuning_we_tail, 1)
        self.debug_we_tail = format_field(debug_we_tail, 1)

    def to_binary(self):
        body = (self.core_we + self.tuning_we + self.debug_we + self.char_we +
                self.unshadowed_we) * 4
        return "0" + "0" + self.core_we_head + body + self.core_we_tail + self.tuning_we_tail + self.debug_we_tail + "0"


class ws_core:

    def __init__(self,
                 enpll=False,
                 mpy=0,
                 vrange=False,
                 endivclk=False,
                 lb=0,
                 enrx=False,
                 sleeprx=False,
                 buswidth=0,
                 rate=0,
                 invpair=False,
                 term=0,
                 align=0,
                 los=0,
                 cdr=0,
                 eq=0,
                 eqhld=False,
                 enoc=False,
                 loopback=0,
                 bsinrxp=False,
                 bsinrxn=False,
                 testpatt=0,
                 testfail=False,
                 losdtct_rl=False,
                 bsrxp=False,
                 bsrxn=False,
                 ocip=False,
                 eqover=False,
                 equnder=False,
                 losdtct_st=False,
                 sync=False,
                 clkbyp=0,
                 sleeppll=False,
                 lock=False,
                 bsinitclk=False,
                 enbstx=False,
                 enbsrx=False,
                 enbspt=False,
                 nearlock=False,
                 unlock=False,
                 cfg_ovr=False):
        self.enpll = format_field(enpll, 1)
        self.mpy = format_field(mpy, 8)
        self.vrange = format_field(vrange, 1)
        self.endivclk = format_field(endivclk, 1)
        self.lb = format_field(lb, 2)
        self.enrx = format_field(enrx, 1)
        self.sleeprx = format_field(sleeprx, 1)
        self.buswidth = format_field(buswidth, 3)
        self.rate = format_field(rate, 2)
        self.invpair = format_field(invpair, 1)
        self.term = format_field(term, 3)
        self.align = format_field(align, 2)
        self.los = format_field(los, 3)
        self.cdr = format_field(cdr, 3)
        self.eq = format_field(eq, 3)
        self.eqhld = format_field(eqhld, 1)
        self.enoc = format_field(enoc, 1)
        self.loopback = format_field(loopback, 2)
        self.bsinrxp = format_field(bsinrxp, 1)
        self.bsinrxn = format_field(bsinrxn, 1)
        self.reserved1 = format_field(False, 1)
        self.testpatt = format_field(testpatt, 3)
        self.testfail = format_field(testfail, 1)
        self.losdtct_rl = format_field(losdtct_rl, 1)
        self.bsrxp = format_field(bsrxp, 1)
        self.bsrxn = format_field(bsrxn, 1)
        self.ocip = format_field(ocip, 1)
        self.eqover = format_field(eqover, 1)
        self.equnder = format_field(equnder, 1)
        self.losdtct_st = format_field(losdtct_st, 1)
        self.sync = format_field(sync, 1)
        self.clkbyp = format_field(clkbyp, 2)
        self.sleeppll = format_field(sleeppll, 1)
        self.reserved2 = format_field(False, 1)
        self.lock = format_field(lock, 1)
        self.bsinitclk = format_field(bsinitclk, 1)
        self.enbstx = format_field(enbstx, 1)
        self.enbsrx = format_field(enbsrx, 1)
        self.enbspt = format_field(enbspt, 1)
        self.reserved3 = format_field(False, 1)
        self.nearlock = format_field(nearlock, 1)
        self.unlock = format_field(unlock, 1)
        self.cfg_ovr = format_field(cfg_ovr, 1)

    def to_binary(self):
        body = (self.enrx + self.sleeprx + self.buswidth + self.rate +
                self.invpair + self.term + self.align + self.los + self.cdr +
                self.eq + self.eqhld + self.enoc + self.loopback +
                self.bsinrxp + self.bsinrxn + self.reserved1 + self.testpatt +
                self.testfail + self.losdtct_rl + self.bsrxp + self.bsrxn +
                self.ocip + self.eqover + self.equnder + self.losdtct_st +
                self.sync + "0") * 4
        return "0" + "0" + self.enpll + self.mpy + self.vrange + self.endivclk + self.lb + body + self.clkbyp + self.sleeppll + self.reserved2 + self.lock + self.bsinitclk + self.enbstx + self.enbsrx + self.enbspt + self.reserved3 + self.nearlock + self.unlock + self.cfg_ovr + "0"
