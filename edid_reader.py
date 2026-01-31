#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import struct
from typing import List, Tuple, Dict

# ============================================================
# Helpers
# ============================================================

def hx(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)

def bits8(v: int) -> str:
    return "".join("1" if (v >> (7 - i)) & 1 else "0" for i in range(8))

def u16le(b: bytes) -> int:
    return struct.unpack("<H", b)[0]

def u32le(b: bytes) -> int:
    return struct.unpack("<I", b)[0]

def safe_ascii(b: bytes) -> str:
    # EDID strings: often padded with spaces and end with 0x0A
    s = b.decode("ascii", errors="ignore")
    s = s.replace("\x00", "")
    return s.strip(" \r\n\t")

def checksum_valid(block: bytes) -> bool:
    return (sum(block) & 0xFF) == 0

def decode_manufacturer_id(word_be: bytes) -> str:
    # Manufacturer ID is 2 bytes big-endian with 3 letters packed in 5-bit fields
    w = (word_be[0] << 8) | word_be[1]
    c1 = chr(((w >> 10) & 0x1F) + 64)
    c2 = chr(((w >> 5) & 0x1F) + 64)
    c3 = chr((w & 0x1F) + 64)
    return f"{c1}{c2}{c3}"

# ============================================================
# Byte map labels (EDID 1.4 Base Block)
# ============================================================

def base_byte_labels() -> Dict[int, str]:
    labels = {}

    # Header
    for i in range(0x00, 0x08):
        labels[i] = "EDID Header"

    # Vendor & Product
    labels[0x08] = "Manufacturer ID (byte 0, BE)"
    labels[0x09] = "Manufacturer ID (byte 1, BE)"
    labels[0x0A] = "Product Code (LSB, LE)"
    labels[0x0B] = "Product Code (MSB, LE)"
    labels[0x0C] = "Serial Number (byte0, LE)"
    labels[0x0D] = "Serial Number (byte1, LE)"
    labels[0x0E] = "Serial Number (byte2, LE)"
    labels[0x0F] = "Serial Number (byte3, LE)"

    labels[0x10] = "Week of Manufacture"
    labels[0x11] = "Year of Manufacture (1990 + value)"

    labels[0x12] = "EDID Version"
    labels[0x13] = "EDID Revision"

    # Basic Display Parameters
    labels[0x14] = "Video Input Definition"
    labels[0x15] = "Max Horizontal Image Size (cm)"
    labels[0x16] = "Max Vertical Image Size (cm)"
    labels[0x17] = "Display Gamma"
    labels[0x18] = "Feature Support"

    # Chromaticity
    labels[0x19] = "Chromaticity LSBs (Rx,Ry,Gx,Gy)"
    labels[0x1A] = "Chromaticity LSBs (Bx,By,Wx,Wy)"
    labels[0x1B] = "Red x MSB"
    labels[0x1C] = "Red y MSB"
    labels[0x1D] = "Green x MSB"
    labels[0x1E] = "Green y MSB"
    labels[0x1F] = "Blue x MSB"
    labels[0x20] = "Blue y MSB"
    labels[0x21] = "White x MSB"
    labels[0x22] = "White y MSB"

    # Timings
    labels[0x23] = "Established Timings (byte 1)"
    labels[0x24] = "Established Timings (byte 2)"
    labels[0x25] = "Established Timings (byte 3)"

    # Standard timings (8 entries x2 bytes)
    for i in range(8):
        labels[0x26 + i*2] = f"Standard Timing #{i+1} (X resolution)"
        labels[0x27 + i*2] = f"Standard Timing #{i+1} (Aspect/Refresh)"

    # Descriptors
    for i in range(4):
        base = 0x36 + i*18
        for j in range(18):
            labels[base + j] = f"Descriptor #{i+1} byte {j}"

    labels[0x7E] = "Extension Block Count"
    labels[0x7F] = "Checksum"
    return labels

# ============================================================
# Field decoders
# ============================================================

def decode_video_input_definition(v: int) -> List[str]:
    out = []
    out.append(f"Raw: 0x{v:02X} (bits {bits8(v)})")

    if v & 0x80:
        out.append("Type: DIGITAL (bit7=1)")
        depth = (v >> 4) & 0x07
        depth_map = {
            0: "Undefined",
            1: "6 bits per primary color",
            2: "8 bits per primary color",
            3: "10 bits per primary color",
            4: "12 bits per primary color",
            5: "14 bits per primary color",
            6: "16 bits per primary color",
            7: "Reserved",
        }
        out.append(f"Color bit depth (bits6..4): {depth} -> {depth_map.get(depth,'?')}")

        iface = v & 0x0F
        iface_map = {
            0x0: "Undefined",
            0x1: "DVI",
            0x2: "HDMI-a",
            0x3: "HDMI-b",
            0x4: "MDDI",
            0x5: "DisplayPort",
        }
        out.append(f"Digital interface (bits3..0): 0x{iface:X} -> {iface_map.get(iface,'Other/Reserved')}")
    else:
        out.append("Type: ANALOG (bit7=0)")
        sync_level = (v >> 5) & 0x03
        setup = (v >> 3) & 0x03
        out.append(f"Sync signal level (bits6..5): {sync_level}")
        out.append(f"Video setup (bits4..3): {setup}")
        out.append(f"Separate sync supported (bit2): {'Yes' if v & 0x04 else 'No'}")
        out.append(f"Composite sync supported (bit1): {'Yes' if v & 0x02 else 'No'}")
        out.append(f"Sync-on-green supported (bit0): {'Yes' if v & 0x01 else 'No'}")
    return out

def decode_gamma(g: int) -> str:
    if g == 0xFF:
        return "Gamma: defined by display (0xFF)"
    return f"Gamma: {((g + 100) / 100.0):.2f} (raw {g})"

def decode_feature_support(f: int) -> List[str]:
    out = []
    out.append(f"Raw: 0x{f:02X} (bits {bits8(f)})")
    out.append(f"Standby (bit7): {'ON' if f & 0x80 else 'OFF'}")
    out.append(f"Suspend (bit6): {'ON' if f & 0x40 else 'OFF'}")
    out.append(f"Active Off / Very Low Power (bit5): {'ON' if f & 0x20 else 'OFF'}")

    color_type = (f >> 3) & 0x03
    color_map = {
        0: "Monochrome / Grayscale",
        1: "RGB Color",
        2: "Non-RGB Color",
        3: "Undefined",
    }
    out.append(f"Color Type (bits4..3): {color_type} -> {color_map.get(color_type,'?')}")
    out.append(f"sRGB default (bit2): {'ON' if f & 0x04 else 'OFF'}")
    out.append(f"Preferred Timing Mode (bit1): {'ON' if f & 0x02 else 'OFF'}")
    out.append(f"Continuous Frequency (bit0): {'ON' if f & 0x01 else 'OFF'}")
    return out

def decode_chromaticity(edid: bytes) -> List[str]:
    # EDID chromaticity:
    # 0x19 contains LSB bits for Rx,Ry,Gx,Gy (2 bits each)
    # 0x1A contains LSB bits for Bx,By,Wx,Wy (2 bits each)
    # MSBs are bytes 0x1B..0x22 (8 bits each), total 10-bit values
    b19 = edid[0x19]
    b1a = edid[0x1A]

    rx_l = (b19 >> 6) & 0x03
    ry_l = (b19 >> 4) & 0x03
    gx_l = (b19 >> 2) & 0x03
    gy_l = (b19 >> 0) & 0x03

    bx_l = (b1a >> 6) & 0x03
    by_l = (b1a >> 4) & 0x03
    wx_l = (b1a >> 2) & 0x03
    wy_l = (b1a >> 0) & 0x03

    rx = (edid[0x1B] << 2) | rx_l
    ry = (edid[0x1C] << 2) | ry_l
    gx = (edid[0x1D] << 2) | gx_l
    gy = (edid[0x1E] << 2) | gy_l
    bx = (edid[0x1F] << 2) | bx_l
    by = (edid[0x20] << 2) | by_l
    wx = (edid[0x21] << 2) | wx_l
    wy = (edid[0x22] << 2) | wy_l

    out = []
    out.append(f"LSB pack @0x19: 0x{b19:02X} (bits {bits8(b19)})")
    out.append(f"LSB pack @0x1A: 0x{b1a:02X} (bits {bits8(b1a)})")
    out.append(f"Red   x={rx}/1024={rx/1024:.4f}  y={ry}/1024={ry/1024:.4f}")
    out.append(f"Green x={gx}/1024={gx/1024:.4f}  y={gy}/1024={gy/1024:.4f}")
    out.append(f"Blue  x={bx}/1024={bx/1024:.4f}  y={by}/1024={by/1024:.4f}")
    out.append(f"White x={wx}/1024={wx/1024:.4f}  y={wy}/1024={wy/1024:.4f}")
    return out

def decode_established_timings(b0: int, b1: int, b2: int) -> List[str]:
    out = []
    out.append(f"Raw bytes: {b0:02X} {b1:02X} {b2:02X}")

    # byte 0 (0x23)
    if b0 & 0x80: out.append("720x400 @ 70Hz")
    if b0 & 0x40: out.append("720x400 @ 88Hz")
    if b0 & 0x20: out.append("640x480 @ 60Hz")
    if b0 & 0x10: out.append("640x480 @ 67Hz")
    if b0 & 0x08: out.append("640x480 @ 72Hz")
    if b0 & 0x04: out.append("640x480 @ 75Hz")
    if b0 & 0x02: out.append("800x600 @ 56Hz")
    if b0 & 0x01: out.append("800x600 @ 60Hz")

    # byte 1 (0x24)
    if b1 & 0x80: out.append("1280x1024 @ 75Hz")
    if b1 & 0x40: out.append("1024x768 @ 75Hz")
    if b1 & 0x20: out.append("1024x768 @ 72Hz")
    if b1 & 0x10: out.append("1024x768 @ 60Hz")
    if b1 & 0x08: out.append("1024x768 @ 87Hz (Interlaced)")
    if b1 & 0x04: out.append("832x624 @ 75Hz")
    if b1 & 0x02: out.append("800x600 @ 75Hz")
    if b1 & 0x01: out.append("800x600 @ 72Hz")

    # byte 2 (0x25)
    if b2 & 0x01: out.append("1152x870 @ 75Hz")

    if len(out) == 1:
        out.append("(none)")
    return out

def decode_standard_timing(b1: int, b2: int) -> str:
    if b1 == 0x01 and b2 == 0x01:
        return "unused (01 01)"
    h = (b1 + 31) * 8
    aspect = (b2 >> 6) & 0x03
    rr = (b2 & 0x3F) + 60
    aspect_str = ["16:10", "4:3", "5:4", "16:9"][aspect]
    # compute v from aspect
    if aspect == 0:
        v = int(round(h * 10 / 16))
    elif aspect == 1:
        v = int(round(h * 3 / 4))
    elif aspect == 2:
        v = int(round(h * 4 / 5))
    else:
        v = int(round(h * 9 / 16))
    return f"{h}x{v} @ {rr}Hz (aspect {aspect_str}) raw=({b1:02X} {b2:02X})"

# ============================================================
# Descriptor decoding
# ============================================================

def decode_dtd(d: bytes) -> List[str]:
    # Detailed Timing Descriptor (18 bytes)
    out = []
    raw_pix = u16le(d[0:2])
    pixclk_hz = raw_pix * 10_000  # 10 kHz units
    out.append(f"Pixel Clock: {pixclk_hz/1e6:.3f} MHz (raw {raw_pix} * 10 kHz)")

    h_active = d[2] | ((d[4] & 0xF0) << 4)
    h_blank  = d[3] | ((d[4] & 0x0F) << 8)
    v_active = d[5] | ((d[7] & 0xF0) << 4)
    v_blank  = d[6] | ((d[7] & 0x0F) << 8)

    h_sync_off = d[8]  | ((d[11] & 0xC0) << 2)
    h_sync_pw  = d[9]  | ((d[11] & 0x30) << 4)
    v_sync_off = ((d[10] >> 4) & 0x0F) | ((d[11] & 0x0C) << 2)
    v_sync_pw  = (d[10] & 0x0F)        | ((d[11] & 0x03) << 4)

    h_size_mm = d[12] | ((d[14] & 0xF0) << 4)
    v_size_mm = d[13] | ((d[14] & 0x0F) << 8)

    h_border = d[15]
    v_border = d[16]
    flags = d[17]

    h_total = h_active + h_blank
    v_total = v_active + v_blank
    refresh = (pixclk_hz / (h_total * v_total)) if (h_total and v_total) else 0.0

    out.append(f"Active: {h_active} x {v_active}")
    out.append(f"Blanking: H={h_blank}, V={v_blank} -> Totals: {h_total} x {v_total}")
    out.append(f"Sync offset: H={h_sync_off}, V={v_sync_off}")
    out.append(f"Sync width : H={h_sync_pw},  V={v_sync_pw}")
    out.append(f"Physical size: {h_size_mm} x {v_size_mm} mm")
    out.append(f"Border: H={h_border}, V={v_border}")
    out.append(f"Flags: 0x{flags:02X} (bits {bits8(flags)})")
    out.append(f"Estimated refresh: {refresh:.3f} Hz")

    # A bit more interpretation of flags (EDID 1.4 DTD flags):
    interlaced = bool(flags & 0x80)
    stereo = (flags >> 5) & 0x03
    sync_type = (flags >> 3) & 0x03

    stereo_map = {
        0: "No stereo",
        1: "Field sequential stereo, right image when stereo sync = 1",
        2: "Field sequential stereo, left image when stereo sync = 1",
        3: "2-way interleaved stereo",
    }
    sync_map = {
        0: "Analog composite",
        1: "Bipolar analog composite",
        2: "Digital composite",
        3: "Digital separate",
    }
    out.append(f"Interlaced: {'Yes' if interlaced else 'No'}")
    out.append(f"Stereo mode (bits6..5): {stereo} -> {stereo_map.get(stereo,'?')}")
    out.append(f"Sync type (bits4..3): {sync_type} -> {sync_map.get(sync_type,'?')}")

    if sync_type == 3:
        # Digital separate sync: bits 2..0 define polarity and serration
        v_pol = bool(flags & 0x04)
        h_pol = bool(flags & 0x02)
        serr = bool(flags & 0x01)
        out.append(f"H sync polarity (bit1): {'Positive' if h_pol else 'Negative'}")
        out.append(f"V sync polarity (bit2): {'Positive' if v_pol else 'Negative'}")
        out.append(f"Serration on Vsync (bit0): {'Yes' if serr else 'No'}")

    return out

def decode_monitor_descriptor(d: bytes) -> List[str]:
    # Monitor descriptor format: 00 00 00 <tag> 00 ...
    tag = d[3]
    out = []
    out.append(f"Monitor Descriptor tag: 0x{tag:02X}")

    if d[4] != 0x00:
        out.append(f"NOTE: byte[4] expected 00 for standard descriptor, but is {d[4]:02X}. Might be non-standard.")
    payload = d[5:18]

    if tag == 0xFC:
        out.append(f"Display Name (0xFC): '{safe_ascii(payload)}'")
    elif tag == 0xFF:
        out.append(f"Display Serial (0xFF): '{safe_ascii(payload)}'")
    elif tag == 0xFE:
        out.append(f"Unspecified Text (0xFE): '{safe_ascii(payload)}'")
    elif tag == 0xFD:
        # Range limits
        min_v = d[5]
        max_v = d[6]
        min_h = d[7]
        max_h = d[8]
        max_pclk_mhz = d[9] * 10
        out.append("Display Range Limits (0xFD):")
        out.append(f"  Vertical rate:   {min_v}..{max_v} Hz")
        out.append(f"  Horizontal rate: {min_h}..{max_h} kHz")
        out.append(f"  Max pixel clock: {max_pclk_mhz} MHz")
        out.append(f"  Additional flags/raw: {hx(d[10:18])}")
    elif tag in (0xF7, 0xFA):
        out.append(f"Additional Standard Timings (0x{tag:02X}) raw: {hx(payload)}")
    elif tag == 0xF8:
        out.append(f"Color Management Data (0xF8) raw: {hx(payload)}")
    elif tag == 0xF9:
        out.append(f"CVT 3-Byte Timing Codes (0xF9) raw: {hx(payload)}")
    elif tag == 0xFB:
        out.append(f"Color Point Data (0xFB) raw: {hx(payload)}")
    else:
        # This is where your 0x03 ends up.
        out.append("Reserved / Non-standard monitor descriptor tag (not in common EDID list).")
        out.append(f"Raw payload: {hx(payload)}")
    return out

def decode_descriptor(d: bytes, index: int) -> List[str]:
    out = []
    out.append(f"Descriptor #{index} raw: {hx(d)}")

    pix = u16le(d[0:2])
    if pix != 0:
        out.append("Type: Detailed Timing Descriptor (DTD)")
        for line in decode_dtd(d):
            out.append("  " + line)
        return out

    # Not a DTD: usually monitor descriptor if first 3 bytes are 00 00 00
    if d[0] == 0 and d[1] == 0 and d[2] == 0:
        out.append("Type: Monitor Descriptor (00 00 00 header)")
        for line in decode_monitor_descriptor(d):
            out.append("  " + line)
        return out

    out.append("Type: Non-DTD / Non-standard descriptor (pixel clock=0, header not 00 00 00)")
    out.append("Raw bytes breakdown:")
    for i, b in enumerate(d):
        out.append(f"  byte[{i:02d}] = 0x{b:02X} (bits {bits8(b)})")
    return out

# ============================================================
# Main parsing
# ============================================================

def parse_base_edid(edid: bytes) -> None:
    if len(edid) < 128:
        raise ValueError(f"EDID must be at least 128 bytes, got {len(edid)}")

    edid = edid[:128]  # strictly base block

    print("="*78)
    print("EDID Base Block (128 bytes) — FULL DETAILED PARSE (English)")
    print("="*78)

    # ------------------------------------------------------------
    # Global summary
    # ------------------------------------------------------------
    header = edid[0:8]
    man = decode_manufacturer_id(edid[8:10])
    prod = u16le(edid[0x0A:0x0C])
    serial = u32le(edid[0x0C:0x10])
    week = edid[0x10]
    year = edid[0x11] + 1990
    ver = (edid[0x12], edid[0x13])
    ext_count = edid[0x7E]
    cs = edid[0x7F]
    cs_ok = checksum_valid(edid)

    print("\n[Summary]")
    print(f"Header: {hx(header)}")
    print(f"Manufacturer ID: {hx(edid[8:10])} -> {man}")
    print(f"Product Code: 0x{prod:04X} ({prod})")
    print(f"Serial Number: 0x{serial:08X} ({serial})")
    print(f"Manufacture Date: week={week}, year={year}")
    print(f"EDID Version: {ver[0]}.{ver[1]}")
    print(f"Extension Block Count @0x7E: {ext_count}")
    print(f"Checksum @0x7F: 0x{cs:02X} | Valid: {'YES' if cs_ok else 'NO'}")

    # ------------------------------------------------------------
    # Byte-by-byte map
    # ------------------------------------------------------------
    labels = base_byte_labels()
    print("\n" + "-"*78)
    print("[Byte Map: offset -> hex -> bits -> meaning]")
    print("-"*78)
    for off in range(128):
        b = edid[off]
        label = labels.get(off, "Reserved/Unknown")
        print(f"0x{off:02X}  {b:02X}  {bits8(b)}   {label}")

    # ------------------------------------------------------------
    # Video input definition
    # ------------------------------------------------------------
    print("\n" + "-"*78)
    print("[Video Input Definition @0x14]")
    print("-"*78)
    for line in decode_video_input_definition(edid[0x14]):
        print(line)

    # ------------------------------------------------------------
    # Screen size, gamma, feature support
    # ------------------------------------------------------------
    print("\n" + "-"*78)
    print("[Basic Display Parameters @0x15..0x18]")
    print("-"*78)
    print(f"Max Image Size: {edid[0x15]} x {edid[0x16]} cm (0 means 'unspecified')")
    print(decode_gamma(edid[0x17]))
    print("\nFeature Support @0x18:")
    for line in decode_feature_support(edid[0x18]):
        print("  " + line)

    # ------------------------------------------------------------
    # Chromaticity
    # ------------------------------------------------------------
    print("\n" + "-"*78)
    print("[Chromaticity @0x19..0x22]")
    print("-"*78)
    for line in decode_chromaticity(edid):
        print(line)

    # ------------------------------------------------------------
    # Established timings
    # ------------------------------------------------------------
    print("\n" + "-"*78)
    print("[Established Timings @0x23..0x25]")
    print("-"*78)
    for line in decode_established_timings(edid[0x23], edid[0x24], edid[0x25]):
        print(line)

    # ------------------------------------------------------------
    # Standard timings
    # ------------------------------------------------------------
    print("\n" + "-"*78)
    print("[Standard Timings @0x26..0x35 (8 entries)]")
    print("-"*78)
    for i in range(8):
        b1 = edid[0x26 + i*2]
        b2 = edid[0x27 + i*2]
        print(f"#{i+1}: {decode_standard_timing(b1, b2)}")

    # ------------------------------------------------------------
    # Descriptors
    # ------------------------------------------------------------
    print("\n" + "-"*78)
    print("[Descriptors @0x36..0x7D (4 x 18 bytes)]")
    print("-"*78)
    for i in range(4):
        base = 0x36 + i*18
        d = edid[base:base+18]
        for line in decode_descriptor(d, i+1):
            print(line)

    # ------------------------------------------------------------
    # Trailer (extensions + checksum already in summary)
    # ------------------------------------------------------------
    print("\n" + "-"*78)
    print("[Trailer @0x7E..0x7F]")
    print("-"*78)
    print(f"Extension Block Count (0x7E): {edid[0x7E]}")
    total = sum(edid) & 0xFF
    print(f"Checksum byte (0x7F): 0x{edid[0x7F]:02X}")
    print(f"Sum(all 128 bytes) & 0xFF: {total:02X} -> {'VALID' if total == 0 else 'INVALID'}")

    print("\n" + "="*78)
    print("Done.")
    print("="*78)

def main():
    # default: edid.bin in the same folder as the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_path = os.path.join(script_dir, "edid.bin")

    path = sys.argv[1] if len(sys.argv) > 1 else default_path
    if not os.path.exists(path):
        print(f"ERROR: file not found: {path}")
        print("Usage: python3 edid_base_128_detailed_en.py [path_to_edid.bin]")
        sys.exit(1)

    with open(path, "rb") as f:
        data = f.read()

    if len(data) < 128:
        print(f"ERROR: file too small ({len(data)} bytes). Need 128 bytes for base EDID.")
        sys.exit(1)

    parse_base_edid(data[:128])

if __name__ == "__main__":
    main()
