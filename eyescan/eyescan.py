import ftd2xx
import argparse
import pathlib
from instructions import START_COMMAND, END_COMMAND, BYPASS_COMMAND, COMMANDS, RESET_STATE_COMMAND, ws_char, ws_cfg, ws_core, TestPattern

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

FTDI_SYNC_BITBANG_MODE = 0x04
BITBANG_OUTPUT_BIT = 2


def jtag_write_read(dev, data):
    c = dev.write(bytes(data))
    return dev.read(c)


def encode_bitbang_dr(data):
    trstb = "".join(['00'] * 12 + ['00'
                                   for _ in range(len(data) - 1)] + ['0'] * 27)
    tms = "".join(['00'] * 9 + ['1100'] + ['00'
                                           for _ in range(len(data) - 1)] +
                  ["00111100000000000000000000000"])
    tdo = "".join(['00'] * 12 + ['00'
                                 for _ in range(len(data) - 1)] + ['0'] * 27)
    tdi = "".join(['00'] * 12 + [i + i for i in data] + ['0'] * 27)
    tclk = "".join(['00'] * 5 + ['01'] * 7 + ['01' for _ in range(len(data))] +
                   ['01'] * 12 + ['0'])

    high_signal = "1" * len(trstb)
    return [
        int("".join(i), 2) for i in zip(high_signal, high_signal, high_signal,
                                        trstb, tms, tdo, tdi, tclk)
    ]


def encode_bitbang_ir(data):
    trstb = "".join(['00'] * 13 + ['00'
                                   for _ in range(len(data) - 1)] + ['0'] * 27)
    tms = "".join(['00'] * 9 + ['11110000'] +
                  ['00' for _ in range(len(data) - 1)] +
                  ["111100000000000000000000000"])
    tdo = "".join(['00'] * 13 + ['00'
                                 for _ in range(len(data) - 1)] + ['0'] * 27)
    tdi = "".join(['00'] * 13 + [i + i for i in data] + ['0'] * 25)
    tclk = "".join(['00'] * 5 + ['01'] * 8 + ['01' for _ in range(len(data))] +
                   ['01'] * 12 + ['0'])

    high_signal = "1" * len(trstb)
    return [
        int("".join(i), 2) for i in zip(high_signal, high_signal, high_signal,
                                        trstb, tms, tdo, tdi, tclk)
    ]


def select_command(dev, daisy_chain_device_number, daisy_chain_device_count,
                   command):
    jtag_write_read(
        dev,
        encode_bitbang_ir(
            BYPASS_COMMAND *
            (daisy_chain_device_count - daisy_chain_device_number) +
            START_COMMAND + BYPASS_COMMAND * (daisy_chain_device_number - 1)))
    jtag_write_read(
        dev,
        encode_bitbang_dr(command + "0" * (daisy_chain_device_number - 1)))
    jtag_write_read(
        dev,
        encode_bitbang_ir(
            BYPASS_COMMAND *
            (daisy_chain_device_count - daisy_chain_device_number) +
            RESET_STATE_COMMAND + BYPASS_COMMAND *
            (daisy_chain_device_number - 1)))
    jtag_write_read(
        dev,
        encode_bitbang_ir(
            BYPASS_COMMAND *
            (daisy_chain_device_count - daisy_chain_device_number) +
            END_COMMAND + BYPASS_COMMAND * (daisy_chain_device_number - 1)))


def decode_bitbang(data):
    d = [bin(i)[2:] for i in data]
    decoded_data = ["".join(i) for i in zip(*d)]
    return decoded_data


def read_back_from_char(dev,
                        daisy_chain_device_number,
                        daisy_chain_device_count,
                        voltage_off,
                        phase_off,
                        bit_select,
                        is_r0=True):
    bits = ws_char(phase_off,
                   bit_select,
                   voltage_off,
                   es=0b0001,
                   esword=255,
                   voltage_offset_override=True).to_binary()[::-1]
    encoded_data = encode_bitbang_dr(
        "0" * (daisy_chain_device_count - daisy_chain_device_number) + bits +
        "0" * (daisy_chain_device_number - 1) + ("" if is_r0 else "0"))
    readback = jtag_write_read(dev, encoded_data)
    TMS_BIT = 3
    readback_decoded = decode_bitbang(readback)
    readback_decoded = readback_decoded[
        -BITBANG_OUTPUT_BIT -
        1][readback_decoded[-TMS_BIT - 1].index("11") +
           6:readback_decoded[-TMS_BIT - 1].index("1111") + 2]
    readback_decoded = readback_decoded[::2][::-1][daisy_chain_device_number -
                                                   1:][0 if is_r0 else 2:]
    return int(readback_decoded[2:14][::-1],
               2), int(readback_decoded[50:62][::-1],
                       2), int(readback_decoded[98:110][::-1],
                               2), int(readback_decoded[146:158][::-1], 2)


def setup_device(dev, ftdi_bitmask, ftdi_baudrate):
    dev.resetDevice()
    dev.setBitMode(ftdi_bitmask, FTDI_SYNC_BITBANG_MODE)
    dev.setBaudRate(ftdi_baudrate)
    queue_status = dev.getQueueStatus()
    if queue_status > 0:
        dev.read(queue_status)


def configure_receiver_block(dev, daisy_chain_device_number,
                             daisy_chain_device_count, receiver_block,
                             test_pattern):
    select_command(dev, daisy_chain_device_number, daisy_chain_device_count,
                   COMMANDS[receiver_block]["SELECT_CFG"])
    jtag_write_read(
        dev,
        encode_bitbang_dr(ws_cfg().to_binary()[::-1] + "0" *
                          (daisy_chain_device_number - 1) +
                          ("0" if receiver_block == 1 else "")))
    select_command(dev, daisy_chain_device_number, daisy_chain_device_count,
                   COMMANDS[receiver_block]["SELECT_CFG"])
    jtag_write_read(
        dev,
        encode_bitbang_dr(
            ws_cfg(core_we_head=True,
                   core_we=True,
                   char_we=True,
                   core_we_tail=True).to_binary()[::-1] + "0" *
            (daisy_chain_device_number - 1) +
            ("0" if receiver_block == 1 else "")))
    select_command(dev, daisy_chain_device_number, daisy_chain_device_count,
                   COMMANDS[receiver_block]["SELECT_CORE_INPUTS"])
    jtag_write_read(
        dev,
        encode_bitbang_dr(
            ws_core(enpll=True,
                    mpy=5,
                    enrx=True,
                    buswidth=2,
                    term=1,
                    eq=1,
                    enoc=True,
                    cfg_ovr=True,
                    testpatt=test_pattern).to_binary()[::-1] + "0" *
            (daisy_chain_device_number - 1) +
            ("0" if receiver_block == 1 else "")))


def readout_receiver_block(dev, daisy_chain_device_number,
                           daisy_chain_device_count, bit_number,
                           receiver_block):
    for voltage in range(31, -33, -1):
        for bit_select in range(bit_number):
            select_command(dev, daisy_chain_device_number,
                           daisy_chain_device_count,
                           COMMANDS[receiver_block]["SELECT_READBACK"])
            read_back_from_char(dev, daisy_chain_device_number,
                                daisy_chain_device_count, voltage & 0xff, 0,
                                bit_select, receiver_block == 0)
            for phase in range(15, -17, -1):
                amplitudes = read_back_from_char(dev,
                                                 daisy_chain_device_number,
                                                 daisy_chain_device_count,
                                                 voltage & 0xff, phase & 0xff,
                                                 bit_select,
                                                 receiver_block == 0)
                for lane, amp in enumerate(amplitudes):
                    yield (lane + 4 * receiver_block, bit_select, voltage,
                           phase, amp)


def perform_eyescan(ftdi_dev, ftdi_bitmask, ftdi_baudrate,
                    daisy_chain_device_number, daisy_chain_device_count,
                    output_path, bit_number, test_pattern):
    with ftd2xx.open(ftdi_dev) as dev:
        setup_device(dev, ftdi_bitmask, ftdi_baudrate)
        with open(output_path, "w") as file:
            for receiver_block in range(2):
                configure_receiver_block(dev, daisy_chain_device_number,
                                         daisy_chain_device_count,
                                         receiver_block, test_pattern)
                for lane, bit, voltage, phase, amplitude in readout_receiver_block(
                        dev, daisy_chain_device_number,
                        daisy_chain_device_count, bit_number, receiver_block):
                    file.write(
                        f"{lane}\t{bit}\t{voltage}\t{phase}\t{amplitude}\n")


def parse_args():
    parser = argparse.ArgumentParser(
        prog='eyescan',
        description='TI DAC Eyescan test',
        epilog=
        'A script to connect to the DAC38J8x using JTAG and perform eyescan test'
    )
    parser.add_argument('-o',
                        '--output',
                        required=True,
                        type=pathlib.Path,
                        help="output file path")
    parser.add_argument('-d',
                        '--device',
                        type=int,
                        default=0,
                        help="FTDI device number")
    parser.add_argument('-b',
                        '--bit-number',
                        type=int,
                        default=20,
                        help="how many bits to check")
    parser.add_argument('-m',
                        '--ftdi-bitmask',
                        type=lambda x: int(x, 0),
                        default=0b1000_1011,
                        help="FTDI bitmask")
    parser.add_argument('-r',
                        '--ftdi-baudrate',
                        type=int,
                        default=115200,
                        help="FTDI baudrate")
    parser.add_argument('-c',
                        '--daisy-chain-count',
                        type=int,
                        default=1,
                        help="how many devices in JTAG daisy-chain")
    parser.add_argument('-n',
                        '--daisy-chain-number',
                        type=int,
                        default=1,
                        help="which device from JTAG daisy-chain to read")

    def parse_test_pattern(pattern):
        try:
            return TestPattern[pattern]
        except KeyError:
            raise argparse.ArgumentTypeError(
                f"{pattern} is not a valid test pattern ({[str(i) for i in TestPattern]})"
            )

    parser.add_argument('-p',
                        '--test-pattern',
                        type=parse_test_pattern,
                        choices=list(TestPattern),
                        default=TestPattern.PRBS_7_BIT,
                        help="eyescan test pattern")

    return parser.parse_args()


def main():
    args = parse_args()
    perform_eyescan(ftdi_dev=args.device,
                    ftdi_bitmask=args.ftdi_bitmask,
                    ftdi_baudrate=args.ftdi_baudrate,
                    daisy_chain_device_number=args.daisy_chain_number,
                    daisy_chain_device_count=args.daisy_chain_count,
                    output_path=args.output,
                    bit_number=args.bit_number,
                    test_pattern=args.test_pattern)


if __name__ == "__main__":
    main()
