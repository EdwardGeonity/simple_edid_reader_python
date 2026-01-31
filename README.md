EDID Base Block (128B) Detailed Decoder

A small Python 3 tool that performs a full, byte-accurate decode of the EDID Base Block (first 128 bytes).

Features

Parses and explains all 128 bytes (0x00–0x7F) with offset / hex / bits / meaning

Human-readable sections: vendor/product info, video input, gamma, feature flags, chromaticity, timings, descriptors

Detailed decoding of Detailed Timing Descriptor (DTD)

Proper handling of manufacturer-specific descriptors (e.g. tag 0x00..0x0F) with raw payload dump

Validates EDID checksum

Output

The tool generates a .txt report next to the input file using the same base name:

edid.bin → edid.txt

Usage
python3 edid_base_128_to_txt_en.py edid.bin


Or run without arguments and enter the filename when prompted:

python3 edid_base_128_to_txt_en.py

Notes

This decoder targets the base EDID block only (128 bytes). If your EDID contains CTA/DisplayID extensions, those are stored in additional blocks (not parsed here).
