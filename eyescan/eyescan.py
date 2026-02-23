from pyftdi.jtag import JtagEngine
from pyftdi.bits import BitSequence
import argparse
import pathlib
from instructions import IEEE_1500_IR_COMMAND, IEEE_1500_DR_COMMAND, BYPASS_COMMAND, COMMANDS, RESET_STATE_COMMAND, ws_char, ws_cfg, ws_core, TestPattern

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

JTAG_CLK_FREQ = 1E5


def select_command(jtag: JtagEngine, daisy_chain_device_number: int,
                   daisy_chain_device_count: int, command: str):
    jtag.write_ir(
        BitSequence(BYPASS_COMMAND *
                    (daisy_chain_device_count - daisy_chain_device_number) +
                    IEEE_1500_IR_COMMAND + BYPASS_COMMAND *
                    (daisy_chain_device_number - 1),
                    msb=False))
    jtag.write_dr(
        BitSequence(command + "0" * (daisy_chain_device_number - 1),
                    msb=False))
    jtag.write_ir(
        BitSequence(BYPASS_COMMAND *
                    (daisy_chain_device_count - daisy_chain_device_number) +
                    RESET_STATE_COMMAND + BYPASS_COMMAND *
                    (daisy_chain_device_number - 1),
                    msb=False))
    jtag.write_ir(
        BitSequence(BYPASS_COMMAND *
                    (daisy_chain_device_count - daisy_chain_device_number) +
                    IEEE_1500_DR_COMMAND + BYPASS_COMMAND *
                    (daisy_chain_device_number - 1),
                    msb=False))


def read_back_from_char(jtag: JtagEngine,
                        daisy_chain_device_number: int,
                        daisy_chain_device_count: int,
                        voltage_off: int,
                        phase_off: int,
                        bit_select: int,
                        is_r0=True):
    bits = ws_char(phase_off,
                   bit_select,
                   voltage_off,
                   es=0b0001,
                   esword=255,
                   voltage_offset_override=True).to_binary()[::-1]
    encoded_data = BitSequence(
        "0" * (daisy_chain_device_count - daisy_chain_device_number) + bits +
        "0" * (daisy_chain_device_number - 1) + ("" if is_r0 else "0"),
        msb=False)
    jtag.change_state('shift_dr')
    readback = jtag.shift_and_update_register(encoded_data)
    jtag.go_idle()
    readback_decoded = str(readback).replace(" ", "")
    readback_decoded = readback_decoded.split(":")[1]
    readback_decoded = readback_decoded[::-1][daisy_chain_device_number -
                                              1:][::-1][0 if is_r0 else 2:]
    return int(readback_decoded[2:14][::-1],
               2), int(readback_decoded[50:62][::-1],
                       2), int(readback_decoded[98:110][::-1],
                               2), int(readback_decoded[146:158][::-1], 2)


def configure_receiver_block(jtag: JtagEngine, daisy_chain_device_number: int,
                             daisy_chain_device_count: int,
                             receiver_block: int, test_pattern: TestPattern):
    select_command(jtag, daisy_chain_device_number, daisy_chain_device_count,
                   COMMANDS[receiver_block]["SELECT_CFG"])
    jtag.write_dr(
        BitSequence(ws_cfg().to_binary()[::-1] + "0" *
                    (daisy_chain_device_number - 1) +
                    ("0" if receiver_block == 1 else ""),
                    msb=False))
    select_command(jtag, daisy_chain_device_number, daisy_chain_device_count,
                   COMMANDS[receiver_block]["SELECT_CFG"])
    jtag.write_dr(
        BitSequence(ws_cfg(
            core_we_head=True, core_we=True, char_we=True,
            core_we_tail=True).to_binary()[::-1] + "0" *
                    (daisy_chain_device_number - 1) +
                    ("0" if receiver_block == 1 else ""),
                    msb=False))
    select_command(jtag, daisy_chain_device_number, daisy_chain_device_count,
                   COMMANDS[receiver_block]["SELECT_CORE_INPUTS"])
    jtag.write_dr(
        BitSequence(ws_core(enpll=True,
                            mpy=5,
                            enrx=True,
                            buswidth=2,
                            term=1,
                            eq=1,
                            enoc=True,
                            cfg_ovr=True,
                            testpatt=test_pattern).to_binary()[::-1] + "0" *
                    (daisy_chain_device_number - 1) +
                    ("0" if receiver_block == 1 else ""),
                    msb=False))


def readout_receiver_block(jtag: JtagEngine, daisy_chain_device_number: int,
                           daisy_chain_device_count: int, bit_number: int,
                           receiver_block: int):
    for voltage in range(31, -33, -1):
        for bit_select in range(bit_number):
            select_command(jtag, daisy_chain_device_number,
                           daisy_chain_device_count,
                           COMMANDS[receiver_block]["SELECT_READBACK"])
            read_back_from_char(jtag, daisy_chain_device_number,
                                daisy_chain_device_count, voltage & 0xff, 0,
                                bit_select, receiver_block == 0)
            for phase in range(15, -17, -1):
                amplitudes = read_back_from_char(jtag,
                                                 daisy_chain_device_number,
                                                 daisy_chain_device_count,
                                                 voltage & 0xff, phase & 0xff,
                                                 bit_select,
                                                 receiver_block == 0)
                for lane, amp in enumerate(amplitudes):
                    yield (lane + 4 * receiver_block, bit_select, voltage,
                           phase, amp)


def perform_eyescan(pyftdi_url: str, daisy_chain_device_number: int,
                    daisy_chain_device_count: int,
                    output_path: str | pathlib.Path, bit_number: int,
                    test_pattern: TestPattern):
    try:
        jtag = JtagEngine(frequency=JTAG_CLK_FREQ)
        jtag.configure(pyftdi_url)
        jtag.reset(hw_reset=True, tap_reset=True)
        with open(output_path, "w") as file:
            for receiver_block in range(2):
                configure_receiver_block(jtag, daisy_chain_device_number,
                                         daisy_chain_device_count,
                                         receiver_block, test_pattern)
                for lane, bit, voltage, phase, amplitude in readout_receiver_block(
                        jtag, daisy_chain_device_number,
                        daisy_chain_device_count, bit_number, receiver_block):
                    file.write(
                        f"{lane}\t{bit}\t{voltage}\t{phase}\t{amplitude}\n")
    finally:
        jtag.close()
        del jtag


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
    parser.add_argument('-b',
                        '--bit-number',
                        type=int,
                        default=20,
                        help="how many bits to check")
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
    parser.add_argument('-u',
                        '--pyftdi-url',
                        type=str,
                        default='ftdi:///1',
                        help="pyftdi connection URL")

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
    perform_eyescan(pyftdi_url=args.pyftdi_url,
                    daisy_chain_device_number=args.daisy_chain_number,
                    daisy_chain_device_count=args.daisy_chain_count,
                    output_path=args.output,
                    bit_number=args.bit_number,
                    test_pattern=args.test_pattern)


if __name__ == "__main__":
    main()
