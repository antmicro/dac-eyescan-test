import ftd2xx
from instructions import START_COMMAND, END_COMMAND, COMMANDS, ws_char, ws_cfg, ws_core

# See https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/73/2625.DAC38J84-RX-Tests-_2D00_-Version-1p1.pdf

# INSTRUCTIONS:
# https://www.ti.com/lit/ds/symlink/dac38j82.pdf?ts=1763026988732&ref_url=https%253A%252F%252Fwww.ti.com%252Fproduct%252FDAC38J82 (page 47)
# INSTRUCTION OPCODE DESCRIPTION
# ws_bypass 0x00 Bypass. Selects a 1-bit bypass data register. Use when accessing other macros on the same IEEE1500 scan chain.
# ws_cfg 0x35 Configuration. Write protection options for other instructions.
# ws_core 0x30 Core. Fields also accessible via dedicated core-side ports.
# ws_tuning 0x31 Tuning. Fields for fine tuning macro performance.
# ws_debug 0x32 Debug. Fields for advanced control, manufacturing test, silicon characterization and debug
# ws_unshadowed 0x34 Unshadowed. Fields for silicon characterization.
# ws_char 0x33 Char. Fields used for eye scan.

BITS_NUM = 1

def jtag_write_read(dev, data):
    c = dev.write(bytes(data))
    return dev.read(c)

def encode_bitbang(data):
     trstb = ['11'] * 12 + ['11' for _ in range(len(data)-1)] + ['1'] * 27
     tms =   ['00'] * 9 + ['1100'] + ['00' for _ in range(len(data)-1)] + ["00111100000000000000000000000"]
     tdo =   ['00'] * 12 + ['00' for _ in range(len(data)-1)] + ['0'] * 27
     tdi =   ['00'] * 12 + [i + i for i in data] + ['0'] * 27
     tclk =  ['00'] * 5 + ['01'] * 7 + ['01' for _ in range(len(data))] + ['01'] * 12 + ['0']

     return [int("".join(i),2) for i in zip("".join(trstb), "".join(tms), "".join(tdo), "".join(tdi), "".join(tclk))]

def encode_bitbang_dr(data):
     trstb = ['11'] * 13 + ['11' for _ in range(len(data)-1)] + ['1'] * 27
     tms =   ['00'] * 9 + ['11110000'] + ['00' for _ in range(len(data)-1)] + ["111100000000000000000000000"]
     tdo =   ['00'] * 13 + ['00' for _ in range(len(data)-1)] + ['0'] * 27
     tdi =   ['00'] * 13 + [i + i for i in data] + ['0'] * 25
     tclk =  ['00'] * 5 + ['01'] * 8 + ['01' for _ in range(len(data))] + ['01'] * 12 + ['0']

     return [int("".join(i),2) for i in zip("".join(trstb), "".join(tms), "".join(tdo), "".join(tdi), "".join(tclk))]

def select_command(dev, command):
    jtag_write_read(dev, encode_bitbang_dr(START_COMMAND))
    jtag_write_read(dev, encode_bitbang(command))
    jtag_write_read(dev, encode_bitbang_dr(END_COMMAND))

def decode_bitbang(data):
    d = [bin(i)[2:] for i in data]
    decoded_data = ["".join(i) for i in zip(*d)]
    return decoded_data

def read_back_from_char(dev, voltage_off, phase_off, bit_select, is_r0=True):
    bits = ws_char(phase_off, bit_select, voltage_off).to_binary()[::-1]
    encoded_data = encode_bitbang(bits + ("" if is_r0 else "0"))
    readback = jtag_write_read(dev, encoded_data)
    readback_decoded = decode_bitbang(readback)[2][27 if is_r0 else 25:][::2][:194][::-1]
    return int(readback_decoded[2:14], 2), int(readback_decoded[50:62], 2), int(readback_decoded[98:110], 2), int(readback_decoded[146:158], 2)


with ftd2xx.open(0) as dev:
    dev.resetDevice()
    queue_status = dev.getQueueStatus()
    if queue_status > 0:
        dev.read(queue_status)

    for receiver_block in range(2):
        # Setup config and core inputs
        select_command(dev, COMMANDS[receiver_block]["SELECT_CFG"])
        jtag_write_read(dev, encode_bitbang(ws_cfg().to_binary()[::-1] + ("0" if receiver_block == 1 else "")))
        select_command(dev, COMMANDS[receiver_block]["SELECT_CFG"])
        jtag_write_read(dev, encode_bitbang(ws_cfg(core_we_head=True, core_we=True, char_we=True, core_we_tail=True).to_binary()[::-1] + ("0" if receiver_block == 1 else "")))
        select_command(dev, COMMANDS[receiver_block]["SELECT_CORE_INPUTS"])
        jtag_write_read(dev, encode_bitbang(ws_core(enpll=True, mpy=20, enrx=True, buswidth=2, term=1, eq=1, enoc=True, cfg_ovr=True).to_binary()[::-1] + ("0" if receiver_block == 1 else "")))

        # Amplitude readout
        for voltage in range(31, -33, -1):
            for bit_select in range(BITS_NUM):
                select_command(dev, COMMANDS[receiver_block]["SELECT_READBACK"])
                read_back_from_char(dev, voltage & 0xff, 0, bit_select, receiver_block == 0)
                for phase in range(15, -17, -1):
                    amplitudes = read_back_from_char(dev, voltage & 0xff, phase & 0xff, bit_select, receiver_block == 0)
                    for lane, amp in enumerate(amplitudes):
                        print(f"{lane + 4 * receiver_block}\t{bit_select}\t{voltage}\t{phase}\t{amp}")


