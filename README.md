# TI DAC Eyescan test

Copyright (c) 2025 [Antmicro](https://www.antmicro.com)

Contains scripts to connect to the DAC38J8x using JTAG and perform eyescan test.

## Install

1. Download the repository

```
git clone https://github.com/antmicro/dac-eyescan-test.git
```

2. Setup virtual environment and install requirements

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

1. Connect the DAC38J8x to the host using FTDI
2. Power the DAC38J8x board
3. Run the test

```bash
python eyescan.py
```

### List available FTDI interfaces

By default, the script picks the first available FTDI interface.
`--pyftdi-url` can be used to select a specific FTDI interface.
To list all available interfaces, run the following command in the active virtual environment:

```sh
(.venv) $ ftdi_urls.py
Available interfaces:
    ftdi://ftdi:232h:210299BF3425/1  (Digilent USB Device)
```

You can then pass the preferred url to `--pyftdi-url`.
