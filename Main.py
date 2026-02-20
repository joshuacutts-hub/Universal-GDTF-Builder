"""
GDTF 1.1 Builder — with Anthropic PDF parsing, wheel slots, and MA3-compatible ChannelFunctions
"""

import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile, io, uuid, re, json, base64
import anthropic
import pdfplumber

# ══════════════════════════════════════════════════════════════════════════════
#  GDTF ATTRIBUTE MAP  (name → gdtf_attr, feature_group, feature, act_group)
# ══════════════════════════════════════════════════════════════════════════════
ATTR_MAP = {
    "dimmer":           ("Dimmer",              "Dimming",   "Intensity", "Dimmer"),
    "intensity":        ("Dimmer",              "Dimming",   "Intensity", "Dimmer"),
    "master":           ("Dimmer",              "Dimming",   "Intensity", "Dimmer"),
    "pan":              ("Pan",                 "Position",  "Position",  "PanTilt"),
    "tilt":             ("Tilt",                "Position",  "Position",  "PanTilt"),
    "pan speed":        ("PanRotate",           "Position",  "Position",  "PanTilt"),
    "tilt speed":       ("TiltRotate",          "Position",  "Position",  "PanTilt"),
    "xyz x":            ("XYZ_X",              "Position",  "Position",  "XYZ"),
    "xyz y":            ("XYZ_Y",              "Position",  "Position",  "XYZ"),
    "xyz z":            ("XYZ_Z",              "Position",  "Position",  "XYZ"),
    "red":              ("ColorAdd_R",          "Color",     "Color",     "RGB"),
    "green":            ("ColorAdd_G",          "Color",     "Color",     "RGB"),
    "blue":             ("ColorAdd_B",          "Color",     "Color",     "RGB"),
    "white":            ("ColorAdd_W",          "Color",     "Color",     "RGBW"),
    "amber":            ("ColorAdd_A",          "Color",     "Color",     "RGBW"),
    "lime":             ("ColorAdd_L",          "Color",     "Color",     "RGBW"),
    "uv":               ("ColorAdd_UV",         "Color",     "Color",     "RGBW"),
    "indigo":           ("ColorAdd_I",          "Color",     "Color",     "RGBW"),
    "cyan":             ("ColorSub_C",          "Color",     "Color",     "CMY"),
    "magenta":          ("ColorSub_M",          "Color",     "Color",     "CMY"),
    "yellow":           ("ColorSub_Y",          "Color",     "Color",     "CMY"),
    "cto":              ("CTO",                 "Color",     "Color",     "CTO"),
    "ctb":              ("CTB",                 "Color",     "Color",     "CTB"),
    "hue":              ("CIE_X",              "Color",     "Color",     "HSB"),
    "saturation":       ("CIE_Y",              "Color",     "Color",     "HSB"),
    "color wheel":      ("Color1",             "Color",     "Color",     "ColorWheel"),
    "colour wheel":     ("Color1",             "Color",     "Color",     "ColorWheel"),
    "color":            ("Color1",             "Color",     "Color",     "ColorWheel"),
    "colour":           ("Color1",             "Color",     "Color",     "ColorWheel"),
    "color mix":        ("ColorMixMode",       "Color",     "Color",     "ColorWheel"),
    "shutter":          ("Shutter1",           "Beam",      "Beam",      "Shutter"),
    "strobe":           ("Shutter1Strobe",     "Beam",      "Beam",      "Shutter"),
    "strobe rate":      ("Shutter1StrobeFreq", "Beam",      "Beam",      "Shutter"),
    "strobe speed":     ("Shutter1StrobeFreq", "Beam",      "Beam",      "Shutter"),
    "zoom":             ("Zoom",               "Beam",      "Beam",      "Zoom"),
    "focus":            ("Focus1",             "Beam",      "Beam",      "Focus"),
    "iris":             ("Iris",               "Beam",      "Beam",      "Iris"),
    "frost":            ("Frost1",             "Beam",      "Beam",      "Frost"),
    "diffusion":        ("Frost1",             "Beam",      "Beam",      "Frost"),
    "gobo":             ("Gobo1",             "Gobo",      "Gobo",      "Gobo"),
    "gobo wheel":       ("Gobo1",             "Gobo",      "Gobo",      "Gobo"),
    "gobo 1":           ("Gobo1",             "Gobo",      "Gobo",      "Gobo"),
    "gobo 2":           ("Gobo2",             "Gobo",      "Gobo",      "Gobo"),
    "gobo rotation":    ("Gobo1Pos",          "Gobo",      "Gobo",      "Gobo"),
    "gobo spin":        ("Gobo1PosRotate",    "Gobo",      "Gobo",      "Gobo"),
    "gobo index":       ("Gobo1Pos",          "Gobo",      "Gobo",      "Gobo"),
    "prism":            ("Prism1",            "Beam",      "Beam",      "Prism"),
    "prism rotation":   ("Prism1Pos",         "Beam",      "Beam",      "Prism"),
    "effects":          ("Effects1",          "Beam",      "Beam",      "Effects"),
    "effect":           ("Effects1",          "Beam",      "Beam",      "Effects"),
    "animation":        ("Effects1",          "Beam",      "Beam",      "Effects"),
    "effects speed":    ("EffectsSpeed",      "Beam",      "Beam",      "Effects"),
    "effects fade":     ("EffectsFade",       "Beam",      "Beam",      "Effects"),
    "blade 1":          ("Blade1A",           "Shapers",   "Shapers",   "Blade"),
    "blade 2":          ("Blade2A",           "Shapers",   "Shapers",   "Blade"),
    "blade 3":          ("Blade3A",           "Shapers",   "Shapers",   "Blade"),
    "blade 4":          ("Blade4A",           "Shapers",   "Shapers",   "Blade"),
    "blade rotation":   ("ShaperRot",         "Shapers",   "Shapers",   "Blade"),
    "macro":            ("Macro",             "Control",   "Control",   "Macro"),
    "scene":            ("Macro",             "Control",   "Control",   "Macro"),
    "program":          ("Macro",             "Control",   "Control",   "Macro"),
    "function":         ("Function",          "Control",   "Control",   "Function"),
    "control":          ("Function",          "Control",   "Control",   "Function"),
    "reset":            ("Function",          "Control",   "Control",   "Function"),
    "lamp":             ("LampControl",       "Control",   "Control",   "Function"),
    "fans":             ("Function",          "Control",   "Control",   "Function"),
    "speed":            ("EffectsSpeed",      "Beam",      "Beam",      "Effects"),
    "video":            ("VideoEffect1Type",  "Control",   "Control",   "Function"),
    "media":            ("VideoEffect1Type",  "Control",   "Control",   "Function"),
}

# Wheel-capable attributes — these get Wheel + WheelSlot children in GDTF
WHEEL_ATTRS = {
    "Color1", "Color2", "Gobo1", "Gobo2", "Gobo1Pos", "Gobo2Pos",
    "Prism1", "Effects1", "Animation1", "Macro", "LampControl", "Function",
    "Shutter1", "Shutter1Strobe",
}


def resolve_attr(raw: str):
    clean = raw.lower().strip()
    if clean in ATTR_MAP:
        return ATTR_MAP[clean]
    for key, val in ATTR_MAP.items():
        if key in clean:
            return val
    safe = re.sub(r'[^A-Za-z0-9_]', '_', raw.strip()) or "Custom"
    return (safe, "Control", "Control", safe)


def is_fine(name: str) -> bool:
    return any(w in name.lower() for w in ["fine", " lsb", "16-bit", "16bit", "low byte"])


# ══════════════════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

class ChannelSlot:
    def __init__(self, name: str, dmx_from: int, dmx_to: int,
                 physical_from: float = 0.0, physical_to: float = 1.0,
                 slot_name: str = ""):
        self.name = name
        self.dmx_from = dmx_from
        self.dmx_to = dmx_to
        self.physical_from = physical_from
        self.physical_to = physical_to
        self.slot_name = slot_name or name


class ChannelDef:
    def __init__(self, name: str, is_fine_byte: bool = False,
                 slots: list = None):
        self.name = name
        self.is_fine_byte = is_fine_byte
        self.slots = slots or []


# ══════════════════════════════════════════════════════════════════════════════
#  GDTF XML BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_gdtf(fixture_name: str, manufacturer: str,
               modes_dict: dict) -> str:

    root = ET.Element("GDTF", DataVersion="1.1")
    ft = ET.SubElement(
        root, "FixtureType",
        Name=fixture_name,
        ShortName=fixture_name[:8].upper().replace(" ", ""),
        LongName=fixture_name,
        Manufacturer=manufacturer,
        Description="Generated by GDTF Builder + AI PDF Parser",
        FixtureTypeID=str(uuid.uuid4()).upper(),
        Thumbnail=""
    )

    # ── Collect used attributes ──────────────────────────────────────────────
    used_attrs = {}
    for channels in modes_dict.values():
        for ch in channels:
            if not ch.is_fine_byte:
                attr, fg, feat, ag = resolve_attr(ch.name)
                used_attrs[attr] = (fg, feat, ag)

    # ── AttributeDefinitions ────────────────────────────────────────────────
    attr_defs = ET.SubElement(ft, "AttributeDefinitions")

    ag_xml = ET.SubElement(attr_defs, "ActivationGroups")
    ag_seen = set()
    for _, (fg, feat, ag) in used_attrs.items():
        if ag not in ag_seen:
            ET.SubElement(ag_xml, "ActivationGroup", Name=ag)
            ag_seen.add(ag)

    fg_xml = ET.SubElement(attr_defs, "FeatureGroups")
    fg_used = {}
    for _, (fg, feat, ag) in used_attrs.items():
        fg_used.setdefault(fg, set()).add(feat)
    for fg_name, feats in fg_used.items():
        fg_el = ET.SubElement(fg_xml, "FeatureGroup", Name=fg_name, Pretty=fg_name)
        for f in sorted(feats):
            ET.SubElement(fg_el, "Feature", Name=f)

    attrs_xml = ET.SubElement(attr_defs, "Attributes")
    for attr, (fg, feat, ag) in used_attrs.items():
        ET.SubElement(
            attrs_xml, "Attribute",
            Name=attr, Pretty=attr,
            ActivationGroup=ag,
            Feature=f"{fg}.{feat}",
            PhysicalUnit="None",
            Color="0.3127,0.3290,100.000000"
        )

    # ── Wheels ───────────────────────────────────────────────────────────────
    wheels_el = ET.SubElement(ft, "Wheels")
    wheel_registry = {}  # attr → wheel_name

    for mode_channels in modes_dict.values():
        for ch in mode_channels:
            if ch.is_fine_byte or not ch.slots:
                continue
            attr, *_ = resolve_attr(ch.name)
            if attr not in WHEEL_ATTRS:
                continue
            wheel_name = re.sub(r'[^A-Za-z0-9]', '', ch.name)
            if attr in wheel_registry:
                continue
            wheel_registry[attr] = wheel_name

            wheel_el = ET.SubElement(wheels_el, "Wheel", Name=wheel_name)
            # Slot 0 = Open (required by GDTF spec)
            ET.SubElement(wheel_el, "Slot", Name="Open",
                          Color="0.3127,0.3290,100.000000", MediaFileName="")
            for slot in ch.slots:
                ET.SubElement(wheel_el, "Slot",
                              Name=slot.slot_name,
                              Color="0.3127,0.3290,100.000000",
                              MediaFileName="")

    # ── Physical Descriptions / Models ──────────────────────────────────────
    ET.SubElement(ft, "PhysicalDescriptions")
    ET.SubElement(ft, "Models")

    # ── Geometries ──────────────────────────────────────────────────────────
    geos = ET.SubElement(ft, "Geometries")
    ET.SubElement(geos, "Geometry", Name="Body", Model="",
                  Position="1,0,0,0 0,1,0,0 0,0,1,0 0,0,0,1")

    ET.SubElement(ft, "FTRDMInfo")
    ET.SubElement(ft, "FTPresets")

    # ── DMX Modes ────────────────────────────────────────────────────────────
    dmx_modes_el = ET.SubElement(ft, "DMXModes")

    for mode_name, channels in modes_dict.items():
        mode_el = ET.SubElement(dmx_modes_el, "DMXMode",
                                Name=mode_name, Geometry="Body")
        chs_el = ET.SubElement(mode_el, "DMXChannels")

        offset = 1
        prev_ch_el = None
        prev_offset_start = None

        for ch in channels:
            if not ch.name.strip():
                continue

            if ch.is_fine_byte:
                if prev_ch_el is not None:
                    prev_ch_el.set("Offset", f"{prev_offset_start},{offset}")
                offset += 1
                prev_ch_el = None
                continue

            attr, fg, feat, ag = resolve_attr(ch.name)
            safe_ch_name = re.sub(r'[^A-Za-z0-9_]', '_', ch.name.strip())

            ch_el = ET.SubElement(
                chs_el, "DMXChannel",
                DMXBreak="1",
                Offset=str(offset),
                Default="0/1",
                Highlight="255/1",
                Geometry="Body",
                InitialFunction=f"{mode_name}.{safe_ch_name}.{attr}.{attr}"
            )

            log_el = ET.SubElement(ch_el, "LogicalChannel",
                                   Attribute=attr,
                                   Snap="No", Master="None",
                                   MibFade="0", DMXChangeTimeLimit="0")

            if ch.slots:
                # ── Rich channel: one ChannelFunction per slot ────────────
                wheel_name = wheel_registry.get(attr, "")
                for slot_idx, slot in enumerate(ch.slots, start=1):
                    cf_kwargs = dict(
                        Name=re.sub(r'[^A-Za-z0-9_ \-]', '', slot.name),
                        Attribute=attr,
                        OriginalAttribute=ch.name,
                        DMXFrom=f"{slot.dmx_from}/1",
                        Default=f"{slot.dmx_from}/1",
                        PhysicalFrom=f"{slot.physical_from:.6f}",
                        PhysicalTo=f"{slot.physical_to:.6f}",
                        RealFade="0",
                        RealAcceleration="0",
                        WheelSlotIndex=str(slot_idx) if wheel_name else "0",
                    )
                    if wheel_name:
                        cf_kwargs["Wheel"] = wheel_name
                    ET.SubElement(log_el, "ChannelFunction", **cf_kwargs)
            else:
                # ── Simple channel: full 0-255 range ─────────────────────
                ET.SubElement(log_el, "ChannelFunction",
                              Name=attr,
                              Attribute=attr,
                              OriginalAttribute=ch.name,
                              DMXFrom="0/1",
                              Default="0/1",
                              PhysicalFrom="0.000000",
                              PhysicalTo="1.000000",
                              RealFade="0",
                              RealAcceleration="0",
                              WheelSlotIndex="0")

            prev_ch_el = ch_el
            prev_offset_start = offset
            offset += 1

        ET.SubElement(mode_el, "Relations")
        ET.SubElement(mode_el, "FTMacros")

    raw = ET.tostring(root, encoding="unicode", xml_declaration=False)
    pretty = minidom.parseString(
        f'<?xml version="1.0" encoding="UTF-8"?>{raw}'
    ).toprettyxml(indent="  ", encoding=None)
    return pretty.replace('<?xml version="1.0" ?>',
                          '<?xml version="1.0" encoding="UTF-8"?>')


def create_gdtf_package(xml_content: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("description.xml", xml_content.encode("utf-8"))
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  SIMPLE CHANNEL LIST → ChannelDef  (for manual entry tab)
# ══════════════════════════════════════════════════════════════════════════════

def plain_lines_to_channel_defs(lines: list) -> list:
    defs = []
    for raw in lines:
        if not raw.strip():
            continue
        defs.append(ChannelDef(name=raw.strip(), is_fine_byte=is_fine(raw)))
    return defs


# ══════════════════════════════════════════════════════════════════════════════
#  ANTHROPIC PDF PARSER
# ══════════════════════════════════════════════════════════════════════════════

PDF_SYSTEM_PROMPT = """You are an expert lighting console programmer specialising in DMX fixture profiles and GDTF.

Your job is to read a manufacturer's fixture specification sheet (PDF) and extract the complete DMX channel map, including ALL sub-ranges / slot values within each channel.

Return ONLY a valid JSON object (no markdown, no explanation) with this exact schema:

{
  "fixture_name": "string",
  "manufacturer": "string",
  "modes": [
    {
      "name": "string",
      "channels": [
        {
          "number": 1,
          "name": "string",
          "is_fine": false,
          "slots": [
            {
              "name": "string",
              "dmx_from": 0,
              "dmx_to": 10,
              "physical_from": 0.0,
              "physical_to": 1.0
            }
          ]
        }
      ]
    }
  ]
}

Rules:
- Extract EVERY mode separately; do NOT merge modes.
- For continuous channels (Dimmer, Pan, Tilt, RGB components, Zoom, Focus, Iris) leave slots as [].
- For stepped channels (Gobo, Color Wheel, Strobe modes, Macro, Control, Shutter functions, Prism) list EVERY named range from the table.
- For Shutter/Strobe channels: separate "Closed", "Open", "Strobe slow-fast", "Random strobe", "Pulse" etc. as distinct slots with their DMX ranges.
- dmx_from and dmx_to must cover the FULL 0-255 range when combined across all slots.
- Do NOT invent data; only output what is in the PDF.
- If a channel is a 16-bit fine/LSB byte, set is_fine to true.
- Preserve exact gobo names, color filter names, and macro labels from the PDF.
"""


def parse_pdf_with_claude(pdf_bytes: bytes, api_key: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    messages = [{
        "role": "user",
        "content": [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64
                }
            },
            {
                "type": "text",
                "text": "Extract the complete DMX channel map from this fixture manual and return only the JSON."
            }
        ]
    }]

    # Use multi-turn continuation if response is cut off
    full_text = ""
    for attempt in range(3):
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=16000,
            system=PDF_SYSTEM_PROMPT,
            messages=messages,
        )

        chunk = msg.content[0].text
        full_text += chunk

        # If finished naturally, we're done
        if msg.stop_reason == "end_turn":
            break

        # Response was cut off — ask Claude to continue from where it stopped
        if msg.stop_reason == "max_tokens":
            messages.append({"role": "assistant", "content": chunk})
            messages.append({"role": "user",
                             "content": "Continue the JSON exactly from where you stopped. "
                                        "Do not repeat anything already written."})
        else:
            break

    # Strip markdown fences if present
    raw_text = full_text.strip()
    raw_text = re.sub(r'^```[a-z]*\n?', '', raw_text)
    raw_text = re.sub(r'\n?```$', '', raw_text)

    # Attempt to repair truncated JSON by closing open structures
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        repaired = _repair_truncated_json(raw_text)
        return json.loads(repaired)


def _repair_truncated_json(text: str) -> str:
    """
    Best-effort repair of a truncated JSON string by closing any
    unclosed arrays, objects, and strings.
    """
    # Trim to last complete-looking value boundary
    # Remove trailing partial line
    lines = text.splitlines()
    while lines and not lines[-1].strip().endswith(('}', ']', '"', ',')):
        lines.pop()
    text = "\n".join(lines)

    # Count open braces/brackets to figure out what needs closing
    in_string = False
    escape_next = False
    depth_brace = 0
    depth_bracket = 0

    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth_brace += 1
        elif ch == '}':
            depth_brace -= 1
        elif ch == '[':
            depth_bracket += 1
        elif ch == ']':
            depth_bracket -= 1

    # If we're still inside a string, close it
    closing = ""
    if in_string:
        closing += '"'

    # Strip trailing comma before closing (invalid JSON)
    text = re.sub(r',\s*$', '', text.rstrip())

    # Close open arrays then objects
    closing += ']' * max(depth_bracket, 0)
    closing += '}' * max(depth_brace, 0)

    return text + closing


def parse_pdf_with_pdfplumber(pdf_bytes: bytes) -> dict:
    """
    Extract text from a PDF using pdfplumber (no API key needed).
    Attempts to detect modes and channel rows from tables and raw text.
    Returns a dict in the same schema as the Claude parser so the rest
    of the app can treat both paths identically.
    """
    extracted_pages = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_data = {"text": page.extract_text() or "", "tables": []}

            for table in page.extract_tables():
                # Filter out completely empty tables
                cleaned = [
                    [cell.strip() if cell else "" for cell in row]
                    for row in table
                    if any(cell and cell.strip() for cell in row)
                ]
                if cleaned:
                    page_data["tables"].append(cleaned)

            extracted_pages.append(page_data)

    # ── Heuristic channel detection ──────────────────────────────────────────
    # Look for rows that start with a number (channel number) in tables
    # and try to identify the channel name and any value ranges.

    # Patterns to identify DMX value range rows like "0-10  Open" or "0   10   Strobe"
    RANGE_RE = re.compile(
        r'(\d{1,3})\s*[-–~to]+\s*(\d{1,3})\s+(.+)', re.IGNORECASE
    )
    CHAN_NUM_RE = re.compile(r'^\s*(\d{1,3})\s*$')

    # Mode header keywords
    MODE_KEYWORDS = re.compile(
        r'(mode|channel\s*\w*\s*chart|dmx\s*chart|channel\s*list|(\d+)\s*ch)',
        re.IGNORECASE
    )

    modes_found = {}
    current_mode = "Default Mode"
    current_channels = []
    current_ch_name = None
    current_slots = []
    current_ch_number = 0

    def flush_channel():
        nonlocal current_ch_name, current_slots, current_ch_number
        if current_ch_name:
            current_channels.append({
                "number": current_ch_number,
                "name": current_ch_name,
                "is_fine": is_fine(current_ch_name),
                "slots": current_slots,
            })
        current_ch_name = None
        current_slots = []

    def flush_mode():
        nonlocal current_channels
        flush_channel()
        if current_channels:
            modes_found[current_mode] = list(current_channels)
        current_channels.clear()

    for page_data in extracted_pages:
        # ── Try structured tables first ──────────────────────────────────────
        for table in page_data["tables"]:
            for row in table:
                if not row:
                    continue

                row_text = " | ".join(r for r in row if r)

                # Detect mode header in any cell
                if MODE_KEYWORDS.search(row_text) and len(row_text) < 60:
                    flush_mode()
                    current_mode = row_text.strip().replace("|", "").strip()
                    continue

                # Detect channel row: first cell is a number, second is a name
                if len(row) >= 2 and CHAN_NUM_RE.match(row[0]):
                    flush_channel()
                    current_ch_number = int(row[0].strip())
                    current_ch_name = row[1].strip() if row[1] else f"Ch {current_ch_number}"

                    # Check remaining cells for a value range description
                    rest = " ".join(r for r in row[2:] if r).strip()
                    m = RANGE_RE.match(rest)
                    if m:
                        current_slots.append({
                            "name": m.group(3).strip(),
                            "dmx_from": int(m.group(1)),
                            "dmx_to": int(m.group(2)),
                            "physical_from": round(int(m.group(1)) / 255, 4),
                            "physical_to": round(int(m.group(2)) / 255, 4),
                        })
                    continue

                # Detect value range rows (sub-rows under a channel)
                m = RANGE_RE.match(row[0]) if row[0] else None
                if m and current_ch_name:
                    current_slots.append({
                        "name": m.group(3).strip(),
                        "dmx_from": int(m.group(1)),
                        "dmx_to": int(m.group(2)),
                        "physical_from": round(int(m.group(1)) / 255, 4),
                        "physical_to": round(int(m.group(2)) / 255, 4),
                    })
                    continue

                # Multi-cell range row: "0" | "10" | "Open"
                if (len(row) >= 3
                        and CHAN_NUM_RE.match(row[0])
                        and CHAN_NUM_RE.match(row[1])
                        and row[2]
                        and current_ch_name):
                    current_slots.append({
                        "name": row[2].strip(),
                        "dmx_from": int(row[0].strip()),
                        "dmx_to": int(row[1].strip()),
                        "physical_from": round(int(row[0].strip()) / 255, 4),
                        "physical_to": round(int(row[1].strip()) / 255, 4),
                    })

        # ── Fall back to raw text for pages with no useful tables ────────────
        text = page_data["text"]
        if not text:
            continue

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            # Mode header
            if MODE_KEYWORDS.search(line) and len(line) < 80:
                flush_mode()
                current_mode = line.strip()
                continue

            # Channel line: "1  Dimmer" or "Ch1 - Dimmer"
            ch_line = re.match(
                r'^(?:ch(?:annel)?\s*)?(\d{1,3})\s*[-–.]?\s+([A-Za-z][^\d].{1,40}?)$',
                line, re.IGNORECASE
            )
            if ch_line:
                flush_channel()
                current_ch_number = int(ch_line.group(1))
                current_ch_name = ch_line.group(2).strip()
                continue

            # Value range line under current channel
            m = RANGE_RE.match(line)
            if m and current_ch_name:
                current_slots.append({
                    "name": m.group(3).strip(),
                    "dmx_from": int(m.group(1)),
                    "dmx_to": int(m.group(2)),
                    "physical_from": round(int(m.group(1)) / 255, 4),
                    "physical_to": round(int(m.group(2)) / 255, 4),
                })

    flush_mode()

    # If nothing was detected at all, dump all text as a single note
    if not modes_found:
        all_text = "\n".join(p["text"] for p in extracted_pages if p["text"])
        return {
            "fixture_name": "Unknown — check extracted text",
            "manufacturer": "Unknown",
            "modes": [],
            "_raw_text": all_text,
            "_parse_warning": (
                "pdfplumber could not find a structured channel table. "
                "The raw text is shown below — copy channel names into Manual Entry."
            )
        }

    return {
        "fixture_name": "Unknown — edit above",
        "manufacturer": "Unknown — edit above",
        "modes": [
            {"name": mode_name, "channels": channels}
            for mode_name, channels in modes_found.items()
        ],
    }


def parsed_dict_to_modes(parsed: dict):
    name = parsed.get("fixture_name", "Unknown Fixture")
    mfr  = parsed.get("manufacturer", "Unknown")
    modes = {}

    for mode in parsed.get("modes", []):
        mode_name = mode.get("name", "Default")
        ch_defs = []
        for ch in mode.get("channels", []):
            raw_slots = ch.get("slots") or []
            slots = [
                ChannelSlot(
                    name=s.get("name", ""),
                    dmx_from=int(s.get("dmx_from") or 0),
                    dmx_to=int(s.get("dmx_to") or 255),
                    physical_from=float(s.get("physical_from") or 0.0),
                    physical_to=float(s.get("physical_to") or 1.0),
                    slot_name=s.get("name", ""),
                )
                for s in raw_slots
                if s.get("name")
            ]
            ch_defs.append(ChannelDef(
                name=ch.get("name", f"Ch {ch.get('number', '')}"),
                is_fine_byte=bool(ch.get("is_fine", False)),
                slots=slots,
            ))
        modes[mode_name] = ch_defs

    return name, mfr, modes


# ══════════════════════════════════════════════════════════════════════════════
#  STREAMLIT UI
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="GDTF Builder", page_icon="💡", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:ital,wght@0,400;0,700;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background: #0b0d12;
    color: #dde1ed;
}
h1, h2, h3, h4 { font-family: 'Space Mono', monospace; letter-spacing: -0.02em; }
.block-container { padding-top: 1.8rem; max-width: 1200px; }

div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] select {
    background: #13161f !important;
    border: 1px solid #252836 !important;
    border-radius: 6px !important;
    color: #dde1ed !important;
    font-family: 'DM Sans', sans-serif !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: #4f6ef7 !important;
    box-shadow: 0 0 0 3px rgba(79,110,247,0.15) !important;
}

.stButton>button[kind="primary"] {
    background: linear-gradient(135deg, #4f6ef7 0%, #9b3ff5 100%);
    border: none; border-radius: 8px; color: #fff;
    font-family: 'Space Mono', monospace; font-size: 0.82rem;
    letter-spacing: 0.06em; padding: 0.6rem 1.6rem;
    transition: opacity .2s, transform .15s;
}
.stButton>button[kind="primary"]:hover { opacity: .88; transform: translateY(-1px); }

.stButton>button:not([kind="primary"]) {
    background: #13161f; border: 1px solid #252836;
    border-radius: 6px; color: #8892b0;
    font-size: 0.8rem; padding: 0.45rem 1rem;
    transition: border-color .2s, color .2s;
}
.stButton>button:not([kind="primary"]):hover { border-color: #4f6ef7; color: #dde1ed; }

.stTabs [data-baseweb="tab-list"] {
    gap: 4px; background: #13161f;
    border-radius: 8px; padding: 4px;
    border: 1px solid #252836;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Space Mono', monospace;
    font-size: 0.78rem; letter-spacing: 0.05em;
    border-radius: 6px; padding: 6px 18px;
    color: #8892b0;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #4f6ef7, #9b3ff5) !important;
    color: #fff !important;
}

.card {
    background: #13161f;
    border: 1px solid #252836;
    border-radius: 10px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 1rem;
}

.badge {
    display: inline-block;
    border-radius: 4px; padding: 2px 8px;
    font-family: 'Space Mono', monospace; font-size: 0.68rem;
    margin: 2px; border: 1px solid;
}
.b-ok   { color: #4f6ef7; border-color: #4f6ef733; background: #4f6ef710; }
.b-fine { color: #f59e0b; border-color: #f59e0b33; background: #f59e0b10; }
.b-slot { color: #10b981; border-color: #10b98133; background: #10b98110; }
.b-unk  { color: #ef4444; border-color: #ef444433; background: #ef444410; }

.slot-row {
    display: flex; gap: 8px; align-items: center;
    padding: 4px 0; border-bottom: 1px solid #1e2133;
    font-size: 0.8rem; font-family: 'Space Mono', monospace;
}
.slot-dmx  { color: #f59e0b; width: 90px; flex-shrink: 0; }
.slot-name { color: #dde1ed; flex: 1; }
.slot-phys { color: #8892b0; width: 100px; flex-shrink: 0; }

.info-box {
    background: #0f1829; border-left: 3px solid #4f6ef7;
    border-radius: 0 6px 6px 0; padding: 0.7rem 1rem;
    font-size: 0.85rem; color: #8892b0; margin: 0.5rem 0;
}
.warn-box {
    background: #1a1208; border-left: 3px solid #f59e0b;
    border-radius: 0 6px 6px 0; padding: 0.7rem 1rem;
    font-size: 0.85rem; color: #a07820; margin: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

st.title("💡 GDTF Builder")
st.markdown(
    "<p style='color:#8892b0;font-size:0.88rem;margin-top:-0.6rem'>"
    "GDTF 1.1 · MA3 wheels &amp; slots · PDF AI import · Vectorworks · Capture · Onyx</p>",
    unsafe_allow_html=True
)
st.divider()

# ── Fixture metadata ──────────────────────────────────────────────────────────
st.subheader("Fixture Info")
fi_col1, fi_col2 = st.columns(2)
with fi_col1:
    fixture_name = st.text_input("Model Name",
                                 value=st.session_state.get("fixture_name", "Generic LED Par"))
    st.session_state["fixture_name"] = fixture_name
with fi_col2:
    manufacturer = st.text_input("Manufacturer",
                                 value=st.session_state.get("manufacturer", "Generic"))
    st.session_state["manufacturer"] = manufacturer

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_pdf, tab_manual = st.tabs(["📄  PDF Import  (AI)", "✏️  Manual Entry"])


# ─────────────────────────────────────────────────────────────────────────────
#  TAB 1 — PDF IMPORT
# ─────────────────────────────────────────────────────────────────────────────
with tab_pdf:

    # ── Parser mode toggle ────────────────────────────────────────────────────
    parser_mode = st.radio(
        "Parser method",
        ["🤖 Claude AI (full slot data, needs API key)",
         "📋 pdfplumber (no API key, basic channel names only)"],
        horizontal=True,
        help="Claude extracts gobo names, DMX ranges, and all slot data. "
             "pdfplumber extracts text only — good for getting channel names quickly."
    )
    use_claude = parser_mode.startswith("🤖")

    if use_claude:
        st.markdown("""
        <div class="info-box">
        Claude reads every page and extracts all DMX modes, channel names, gobo/color slot names,
        DMX ranges, strobe types, and macro labels — giving MA3 full wheel and preset pool data.
        </div>
        """, unsafe_allow_html=True)
        api_key = st.text_input(
            "Anthropic API Key",
            type="password",
            help="Used only for this request, never stored.",
            placeholder="sk-ant-…"
        )
    else:
        st.markdown("""
        <div class="info-box">
        pdfplumber extracts text and tables directly from the PDF — <b>no API key needed</b>.
        It detects channel numbers and names, and attempts to read DMX value ranges from tables.
        Works best on clean text-based PDFs. Scanned/image PDFs will return raw text only.
        </div>
        """, unsafe_allow_html=True)
        api_key = ""

    uploaded_pdf = st.file_uploader("Fixture Manual (PDF)", type=["pdf"])

    if uploaded_pdf:
        if use_claude and not api_key:
            st.markdown(
                '<div class="warn-box">Enter your Anthropic API key above to use Claude parsing.</div>',
                unsafe_allow_html=True
            )
        else:
            btn_label = "🤖 Parse PDF with Claude" if use_claude else "📋 Extract with pdfplumber"
            if st.button(btn_label, type="primary"):
                pdf_bytes = uploaded_pdf.read()

                if use_claude:
                    with st.spinner("Claude is reading the manual and extracting DMX data…"):
                        try:
                            parsed = parse_pdf_with_claude(pdf_bytes, api_key)
                            p_name, p_mfr, p_modes = parsed_dict_to_modes(parsed)
                            st.session_state["pdf_parsed"] = {
                                "name": p_name,
                                "manufacturer": p_mfr,
                                "modes": p_modes,
                                "raw": parsed,
                                "method": "claude",
                            }
                            st.session_state["fixture_name"] = p_name
                            st.session_state["manufacturer"] = p_mfr
                            st.rerun()
                        except json.JSONDecodeError as e:
                            st.error(f"Claude returned non-JSON. Try again or use pdfplumber.\n\n{e}")
                        except Exception as e:
                            st.exception(e)

                else:
                    with st.spinner("Extracting text and tables from PDF…"):
                        try:
                            parsed = parse_pdf_with_pdfplumber(pdf_bytes)

                            # Show raw text fallback if no structure found
                            if "_parse_warning" in parsed:
                                st.warning(parsed["_parse_warning"])
                                with st.expander("📄 Raw extracted text — copy channel names from here"):
                                    st.text_area(
                                        "Raw PDF text",
                                        value=parsed.get("_raw_text", ""),
                                        height=400,
                                        help="Copy channel names from here into the Manual Entry tab."
                                    )
                            else:
                                p_name, p_mfr, p_modes = parsed_dict_to_modes(parsed)
                                st.session_state["pdf_parsed"] = {
                                    "name": p_name,
                                    "manufacturer": p_mfr,
                                    "modes": p_modes,
                                    "raw": parsed,
                                    "method": "pdfplumber",
                                }
                                st.session_state["fixture_name"] = p_name
                                st.session_state["manufacturer"] = p_mfr
                                st.rerun()
                        except Exception as e:
                            st.exception(e)

    # ── Parsed result preview ─────────────────────────────────────────────────
    if "pdf_parsed" in st.session_state:
        p = st.session_state["pdf_parsed"]
        method = p.get("method", "claude")
        total_slots = sum(
            len(ch.slots)
            for chs in p["modes"].values()
            for ch in chs
        )
        method_badge = "🤖 Claude AI" if method == "claude" else "📋 pdfplumber"
        st.success(
            f"✅ **{p['name']}** by {p['manufacturer']} — "
            f"{len(p['modes'])} mode(s) · {total_slots} total wheel slots · parsed via {method_badge}"
        )

        if method == "pdfplumber" and total_slots == 0:
            st.markdown("""
            <div class="warn-box">
            <b>pdfplumber found channel names but no slot data.</b> This is normal — pdfplumber
            can't interpret DMX value tables as reliably as Claude. The GDTF will still be valid
            with simple 0–255 ranges per channel. To get gobo names, color slots, and strobe
            sub-ranges on MA3 wheels, re-parse with Claude AI.
            </div>
            """, unsafe_allow_html=True)

        for mode_name, ch_defs in p["modes"].items():
            with st.expander(f"Mode: {mode_name}  ({len(ch_defs)} channels)"):
                for i, ch in enumerate(ch_defs):
                    if ch.is_fine_byte:
                        st.markdown(
                            f'<span class="badge b-fine">Ch {i+1} — {ch.name} &nbsp;(fine byte)</span>',
                            unsafe_allow_html=True
                        )
                        continue

                    attr, fg, feat, _ = resolve_attr(ch.name)
                    badge_cls = "b-slot" if ch.slots else "b-ok"
                    slot_html = ""

                    if ch.slots:
                        rows = "".join(
                            f'<div class="slot-row">'
                            f'<span class="slot-dmx">{s.dmx_from}–{s.dmx_to}</span>'
                            f'<span class="slot-name">{s.slot_name}</span>'
                            f'<span class="slot-phys">{s.physical_from:.2f} → {s.physical_to:.2f}</span>'
                            f'</div>'
                            for s in ch.slots
                        )
                        slot_html = (
                            f'<div style="margin:4px 0 10px 0;padding-left:10px;'
                            f'border-left:2px solid #252836">{rows}</div>'
                        )

                    n_slots = f'&nbsp;<span class="badge b-slot">{len(ch.slots)} slots</span>' if ch.slots else ""
                    st.markdown(
                        f'<span class="badge {badge_cls}">Ch {i+1} — {ch.name} → {attr}</span>{n_slots}'
                        + slot_html,
                        unsafe_allow_html=True
                    )

        with st.expander("Raw AI response (JSON)"):
            st.json(p["raw"])

        st.divider()
        if st.button("⚡ Generate .gdtf from PDF data", type="primary", key="gen_pdf"):
            try:
                xml_data   = build_gdtf(p["name"], p["manufacturer"], p["modes"])
                gdtf_bytes = create_gdtf_package(xml_data)
                safe_name  = re.sub(r'[^A-Za-z0-9_\-]', '_', p["name"])

                st.success(f"GDTF package ready — {len(gdtf_bytes):,} bytes")
                col_dl, col_xp = st.columns([1, 2])
                with col_dl:
                    st.download_button(
                        "📦 Download .gdtf", gdtf_bytes,
                        file_name=f"{safe_name}.gdtf",
                        mime="application/octet-stream"
                    )
                with col_xp:
                    with st.expander("View description.xml"):
                        st.code(xml_data, language="xml")
            except Exception as e:
                st.exception(e)

    elif not uploaded_pdf and "pdf_parsed" not in st.session_state:
        st.markdown("""
        <div class="card" style="text-align:center;padding:2.5rem 1rem">
          <p style="font-size:2rem;margin:0">📄</p>
          <p style="color:#8892b0;margin:0.4rem 0 0">Upload a PDF fixture manual above to get started.</p>
          <p style="color:#3d4460;font-size:0.78rem;margin-top:0.4rem">
            Works best with text-based PDFs from manufacturers like Robe, Martin, ETC, Ayrton, GLP.
          </p>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  TAB 2 — MANUAL ENTRY
# ─────────────────────────────────────────────────────────────────────────────
with tab_manual:
    st.markdown("""
    <div class="info-box">
    Type one channel per line. Append <b>Fine</b> after a channel for 16-bit pairs (e.g. "Pan" then
    "Pan Fine"). For full wheel/slot data use the PDF import tab — manual entry produces simple
    0–255 ranges only.
    </div>
    """, unsafe_allow_html=True)

    if "modes" not in st.session_state:
        st.session_state.modes = [
            {
                "name": "10 Channel",
                "channels": "Dimmer\nDimmer Fine\nRed\nGreen\nBlue\nWhite\nAmber\nUV\nStrobe\nMacro"
            }
        ]

    def add_mode():
        st.session_state.modes.append({
            "name": f"Mode {len(st.session_state.modes) + 1}",
            "channels": "Dimmer\nRed\nGreen\nBlue"
        })

    def remove_mode(i):
        if len(st.session_state.modes) > 1:
            st.session_state.modes.pop(i)

    for idx, mode in enumerate(st.session_state.modes):
        st.markdown('<div class="card">', unsafe_allow_html=True)
        mc1, mc2 = st.columns([4, 1])
        with mc1:
            mode["name"] = st.text_input(
                "Mode Name", value=mode["name"], key=f"mname_{idx}"
            )
        with mc2:
            st.write("")
            st.write("")
            if st.button("🗑 Remove", key=f"rm_{idx}",
                         disabled=len(st.session_state.modes) == 1):
                remove_mode(idx)
                st.rerun()

        mode["channels"] = st.text_area(
            "Channels (one per line)",
            value=mode["channels"], height=180, key=f"mch_{idx}",
            help="Append 'Fine' for 16-bit: 'Pan' then 'Pan Fine'"
        )

        lines = [l for l in mode["channels"].split("\n") if l.strip()]
        if lines:
            badges = []
            for l in lines:
                if is_fine(l):
                    badges.append(f'<span class="badge b-fine">⬆ {l.strip()} (fine)</span>')
                else:
                    attr, *_ = resolve_attr(l)
                    known = any(k in l.lower() for k in ATTR_MAP)
                    cls = "b-ok" if known else "b-unk"
                    badges.append(f'<span class="badge {cls}">{l.strip()} → {attr}</span>')
            st.markdown(" ".join(badges), unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

    st.button("＋ Add Mode", on_click=add_mode)
    st.divider()

    if st.button("⚡ Generate .gdtf File", type="primary", key="gen_manual"):
        fname = st.session_state.get("fixture_name", fixture_name).strip()
        mfr   = st.session_state.get("manufacturer", manufacturer).strip()
        if not fname:
            st.error("Enter a fixture model name above.")
        else:
            modes_dict = {
                m["name"]: plain_lines_to_channel_defs(m["channels"].split("\n"))
                for m in st.session_state.modes
                if m["name"].strip()
            }
            try:
                xml_data   = build_gdtf(fname, mfr, modes_dict)
                gdtf_bytes = create_gdtf_package(xml_data)
                total_ch   = sum(len(v) for v in modes_dict.values())
                st.success(
                    f"✅ {total_ch} channels across {len(modes_dict)} mode(s) — "
                    f"{len(gdtf_bytes):,} bytes"
                )
                col_dl, col_xp = st.columns([1, 2])
                with col_dl:
                    st.download_button(
                        "📦 Download .gdtf", gdtf_bytes,
                        file_name=f"{fname.replace(' ', '_')}.gdtf",
                        mime="application/octet-stream"
                    )
                with col_xp:
                    with st.expander("View description.xml"):
                        st.code(xml_data, language="xml")
            except Exception as e:
                st.exception(e)


# ── Attribute reference ───────────────────────────────────────────────────────
with st.expander("📖 Supported Channel Names"):
    cols = st.columns(3)
    items = list(ATTR_MAP.items())
    chunk = len(items) // 3 + 1
    for i, col in enumerate(cols):
        with col:
            for raw, (attr, *_) in items[i * chunk:(i + 1) * chunk]:
                st.markdown(
                    f'<span class="badge b-ok">{raw}</span>'
                    f'<span style="color:#3d4460;font-size:0.72rem"> → {attr}</span>',
                    unsafe_allow_html=True
                )
