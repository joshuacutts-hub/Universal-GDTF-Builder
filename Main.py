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

def _safe_xml_name(text: str, fallback: str = "Ch") -> str:
    """
    Sanitise a string so it is safe as an XML attribute value AND as part
    of an MA3 InitialFunction path.
    - Strip / replace any character that isn't alphanumeric, underscore,
      hyphen, or space (MA3 path segments use dot as separator so dots must go)
    - Collapse multiple spaces/underscores
    - Never start with a digit
    """
    s = text.strip()
    # Replace common problem characters with safe equivalents
    s = s.replace("°", "deg").replace("%", "pct").replace("/", "_")
    s = s.replace(".", "_").replace(":", "_").replace(";", "_")
    # Remove everything else that isn't word-safe
    s = re.sub(r'[^A-Za-z0-9_ \-]', '', s)
    s = re.sub(r'[ _]+', '_', s).strip('_')
    if not s or s[0].isdigit():
        s = fallback + "_" + s
    return s or fallback


def _guid() -> str:
    """Return a properly formatted GDTF FixtureTypeID (8-4-4-4-12 uppercase)."""
    raw = uuid.uuid4().hex.upper()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def build_gdtf(fixture_name: str, manufacturer: str,
               modes_dict: dict) -> str:

    root = ET.Element("GDTF", DataVersion="1.1")

    # ── FixtureType — sanitised name fields ──────────────────────────────────
    safe_name  = _safe_xml_name(fixture_name, "Fixture")
    safe_short = re.sub(r'[^A-Z0-9]', '', safe_name.upper())[:8] or "FIXTURE"
    safe_mfr   = _safe_xml_name(manufacturer, "Generic")

    ft = ET.SubElement(
        root, "FixtureType",
        Name=safe_name,
        ShortName=safe_short,
        LongName=safe_name,
        Manufacturer=safe_mfr,
        Description="Generated by GDTF Builder",
        FixtureTypeID=_guid(),
        Thumbnail="",
        RefFT="",
        CanHaveChildren="No"
    )

    # ── Collect used attributes (skip fine bytes) ────────────────────────────
    used_attrs = {}
    for channels in modes_dict.values():
        for ch in channels:
            if not ch.is_fine_byte and ch.name.strip():
                attr, fg, feat, ag = resolve_attr(ch.name)
                used_attrs[attr] = (fg, feat, ag)

    # ── AttributeDefinitions ────────────────────────────────────────────────
    attr_defs = ET.SubElement(ft, "AttributeDefinitions")

    ag_xml  = ET.SubElement(attr_defs, "ActivationGroups")
    ag_seen = set()
    for _, (fg, feat, ag) in used_attrs.items():
        if ag not in ag_seen:
            ET.SubElement(ag_xml, "ActivationGroup", Name=ag)
            ag_seen.add(ag)

    fg_xml  = ET.SubElement(attr_defs, "FeatureGroups")
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
    # Build registry first so InitialFunction paths can reference wheel names
    # Key: attr name → wheel XML name (must be unique, no dots or special chars)
    wheel_registry = {}

    for mode_channels in modes_dict.values():
        for ch in mode_channels:
            if ch.is_fine_byte or not ch.slots:
                continue
            attr, *_ = resolve_attr(ch.name)
            if attr not in WHEEL_ATTRS or attr in wheel_registry:
                continue
            # Wheel name = sanitised channel name, guaranteed unique per attr
            wheel_registry[attr] = _safe_xml_name(ch.name, attr)

    wheels_el = ET.SubElement(ft, "Wheels")
    for mode_channels in modes_dict.values():
        for ch in mode_channels:
            if ch.is_fine_byte or not ch.slots:
                continue
            attr, *_ = resolve_attr(ch.name)
            wname = wheel_registry.get(attr)
            if not wname:
                continue
            # Only write each wheel once
            if wheels_el.find(f"Wheel[@Name='{wname}']") is not None:
                continue

            wheel_el = ET.SubElement(wheels_el, "Wheel", Name=wname)
            # Slot index 0 = Open (GDTF spec requirement)
            ET.SubElement(wheel_el, "Slot", Name="Open",
                          Color="0.3127,0.3290,100.000000", MediaFileName="")
            for slot in ch.slots:
                safe_slot = _safe_xml_name(slot.slot_name, "Slot")
                ET.SubElement(wheel_el, "Slot",
                              Name=safe_slot,
                              Color="0.3127,0.3290,100.000000",
                              MediaFileName="")

    # ── Physical Descriptions ────────────────────────────────────────────────
    phys = ET.SubElement(ft, "PhysicalDescriptions")
    ET.SubElement(phys, "Emitters")
    ET.SubElement(phys, "Filters")
    ET.SubElement(phys, "DMXProfiles")
    ET.SubElement(phys, "CRIs")

    # ── Models ──────────────────────────────────────────────────────────────
    ET.SubElement(ft, "Models")

    # ── Geometries ──────────────────────────────────────────────────────────
    # MA3 requires at least one geometry; "Body" is the conventional root name
    geos = ET.SubElement(ft, "Geometries")
    ET.SubElement(
        geos, "Geometry",
        Name="Body",
        Model="",
        Position="1,0,0,0 0,1,0,0 0,0,1,0 0,0,0,1"
    )

    # ── DMX Modes ────────────────────────────────────────────────────────────
    dmx_modes_el = ET.SubElement(ft, "DMXModes")

    for mode_name, channels in modes_dict.items():
        safe_mode = _safe_xml_name(mode_name, "Mode")
        mode_el   = ET.SubElement(dmx_modes_el, "DMXMode",
                                  Name=safe_mode, Geometry="Body")
        chs_el    = ET.SubElement(mode_el, "DMXChannels")

        offset           = 1
        prev_ch_el       = None
        prev_offset_start = None

        for ch in channels:
            if not ch.name.strip():
                continue

            # ── 16-bit fine byte: extend previous channel offset ──────────
            if ch.is_fine_byte:
                if prev_ch_el is not None:
                    prev_ch_el.set("Offset", f"{prev_offset_start},{offset}")
                offset += 1
                prev_ch_el = None
                continue

            attr, fg, feat, ag = resolve_attr(ch.name)
            safe_ch = _safe_xml_name(ch.name, f"Ch{offset}")

            # ── Build ChannelFunction list first so we know the first CF name
            # (needed for a correct InitialFunction reference)
            cf_list = []  # list of dicts, one per ChannelFunction to emit

            if ch.slots:
                wname = wheel_registry.get(attr, "")
                for slot_idx, slot in enumerate(ch.slots, start=1):
                    safe_slot_name = _safe_xml_name(slot.name, f"Slot{slot_idx}")
                    cf = dict(
                        Name=safe_slot_name,
                        Attribute=attr,
                        OriginalAttribute=_safe_xml_name(ch.name),
                        DMXFrom=f"{slot.dmx_from}/1",
                        Default=f"{slot.dmx_from}/1",
                        PhysicalFrom=f"{slot.physical_from:.6f}",
                        PhysicalTo=f"{slot.physical_to:.6f}",
                        RealFade="0",
                        RealAcceleration="0",
                        WheelSlotIndex=str(slot_idx) if wname else "0",
                    )
                    if wname:
                        cf["Wheel"] = wname
                    cf_list.append(cf)
            else:
                cf_list.append(dict(
                    Name=attr,
                    Attribute=attr,
                    OriginalAttribute=_safe_xml_name(ch.name),
                    DMXFrom="0/1",
                    Default="0/1",
                    PhysicalFrom="0.000000",
                    PhysicalTo="1.000000",
                    RealFade="0",
                    RealAcceleration="0",
                    WheelSlotIndex="0",
                ))

            # InitialFunction must exactly match:
            # "ModeName.ChannelName.AttributeName.ChannelFunctionName"
            first_cf_name = cf_list[0]["Name"]
            initial_fn    = f"{safe_mode}.{safe_ch}.{attr}.{first_cf_name}"

            ch_el = ET.SubElement(
                chs_el, "DMXChannel",
                DMXBreak="1",
                Offset=str(offset),
                Default=cf_list[0]["Default"],
                Highlight="255/1",
                Geometry="Body",
                InitialFunction=initial_fn
            )

            log_el = ET.SubElement(
                ch_el, "LogicalChannel",
                Attribute=attr,
                Snap="No",
                Master="None",
                MibFade="0",
                DMXChangeTimeLimit="0"
            )

            for cf in cf_list:
                ET.SubElement(log_el, "ChannelFunction", **cf)

            prev_ch_el        = ch_el
            prev_offset_start = offset
            offset           += 1

        ET.SubElement(mode_el, "Relations")
        ET.SubElement(mode_el, "FTMacros")

    # ── Revision history (MA3 likes to see this) ─────────────────────────────
    revisions = ET.SubElement(ft, "Revisions")
    ET.SubElement(revisions, "Revision",
                  UserID="0", Date="2024-01-01T00:00:00",
                  Text="Created by GDTF Builder", ModifiedBy="GDTFBuilder")

    ET.SubElement(ft, "FTPresets")
    ET.SubElement(ft, "FTRDMInfo")

    raw    = ET.tostring(root, encoding="unicode", xml_declaration=False)
    pretty = minidom.parseString(
        f'<?xml version="1.0" encoding="UTF-8"?>{raw}'
    ).toprettyxml(indent="  ", encoding=None)
    return pretty.replace('<?xml version="1.0" ?>',
                          '<?xml version="1.0" encoding="UTF-8"?>')


def create_gdtf_package(xml_content: str) -> bytes:
    # GDTF spec requires ZIP_STORED (no compression) — ZIP_DEFLATED causes
    # silent import failures in MA3 and Vectorworks
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
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

st.set_page_config(page_title="GDTF Builder", page_icon="💡", layout="wide",
                   initial_sidebar_state="collapsed")

# Inject dark background into the page <head> immediately — before any
# Streamlit rendering — to eliminate the white flash on load
st.markdown("""
<style>
/* ── Force dark on every possible entry point ───────────────────────────── */
html, html body, body, #root, #root > div,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
[data-testid="block-container"],
[data-testid="stMain"],
.main, .block-container, section.main {
    background-color: #0A0A0A !important;
    background: #0A0A0A !important;
}
/* Kill the white header bar Streamlit adds */
[data-testid="stHeader"] {
    background-color: #0A0A0A !important;
    border-bottom: 1px solid #2E2E2E !important;
}
/* Kill white toolbar */
[data-testid="stToolbar"] { background: #0A0A0A !important; }
/* Scrollbar to match */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0A0A0A; }
::-webkit-scrollbar-thumb { background: #3A3A3A; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #E8A000; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@300;400;500;600&display=swap');

/* ── MA3 base colours ───────────────────────────────────────────────────── */
:root {
    --ma-black:    #0A0A0A;
    --ma-panel:    #1A1A1A;
    --ma-border:   #3A3A3A;
    --ma-mid:      #4A4A4A;
    --ma-amber:    #E8A000;
    --ma-amber-dk: #A06800;
    --ma-text:     #EBEBEB;
    --ma-muted:    #AAAAAA;
    --ma-subtle:   #777777;
    --ma-green:    #00C800;
    --ma-red:      #C80000;
    --ma-blue:     #0078C8;
}

html, body, [class*="css"] {
    font-family: 'Barlow', sans-serif;
    background: var(--ma-black) !important;
    color: var(--ma-text);
}
h1, h2, h3, h4 {
    font-family: 'Share Tech Mono', monospace;
    letter-spacing: 0.04em;
    color: var(--ma-amber);
}
.block-container { padding-top: 1.6rem; max-width: 1200px; }

/* ── Inputs ─────────────────────────────────────────────────────────────── */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background: var(--ma-panel) !important;
    border: 1px solid var(--ma-border) !important;
    border-radius: 3px !important;
    color: var(--ma-text) !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.88rem !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--ma-amber) !important;
    box-shadow: 0 0 0 2px rgba(232,160,0,0.2) !important;
}

/* ── Labels ─────────────────────────────────────────────────────────────── */
label, .stRadio label, div[data-testid="stWidgetLabel"] {
    color: #BBBBBB !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* ── Primary button — MA3 amber executor style ──────────────────────────── */
.stButton>button[kind="primary"] {
    background: var(--ma-amber);
    border: 1px solid var(--ma-amber);
    border-bottom: 2px solid var(--ma-amber-dk);
    border-radius: 3px;
    color: #000;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 0.55rem 1.5rem;
    text-transform: uppercase;
    transition: background .15s, border-color .15s;
}
.stButton>button[kind="primary"]:hover {
    background: #FFB800;
    border-color: #FFB800;
}
.stButton>button[kind="primary"]:active {
    background: var(--ma-amber-dk);
    border-color: var(--ma-amber-dk);
}

/* ── Secondary buttons ──────────────────────────────────────────────────── */
.stButton>button:not([kind="primary"]) {
    background: var(--ma-panel);
    border: 1px solid var(--ma-border);
    border-bottom: 2px solid #111;
    border-radius: 3px;
    color: #CCCCCC;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.78rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    transition: border-color .15s, color .15s;
}
.stButton>button:not([kind="primary"]):hover {
    border-color: var(--ma-amber);
    color: var(--ma-amber);
}

/* ── Tabs — MA3 pool button style ───────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 3px;
    background: var(--ma-black);
    border-radius: 3px;
    padding: 3px;
    border: 1px solid var(--ma-border);
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.76rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border-radius: 2px;
    padding: 6px 20px;
    color: #BBBBBB;
    border-bottom: 2px solid transparent;
}
.stTabs [aria-selected="true"] {
    background: var(--ma-amber) !important;
    color: #000 !important;
    font-weight: 700;
    border-bottom: 2px solid var(--ma-amber-dk) !important;
}

/* ── Cards — MA3 window style ───────────────────────────────────────────── */
.card {
    background: var(--ma-panel);
    border: 1px solid var(--ma-border);
    border-top: 2px solid var(--ma-amber);
    border-radius: 3px;
    padding: 1rem 1.2rem;
    margin-bottom: 1rem;
}

/* ── Badges ─────────────────────────────────────────────────────────────── */
.badge {
    display: inline-block;
    border-radius: 2px;
    padding: 2px 7px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.68rem;
    margin: 2px;
    border: 1px solid;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.b-ok   { color: var(--ma-amber);  border-color: #E8A00066; background: #E8A00020; }
.b-fine { color: #4AB0FF;          border-color: #4AB0FF66; background: #4AB0FF20; }
.b-slot { color: #00E000;          border-color: #00E00066; background: #00E00020; }
.b-unk  { color: #FF5555;          border-color: #FF555566; background: #FF555520; }

/* ── Slot table ─────────────────────────────────────────────────────────── */
.slot-row {
    display: flex; gap: 8px; align-items: center;
    padding: 4px 0;
    border-bottom: 1px solid var(--ma-border);
    font-size: 0.78rem;
    font-family: 'Share Tech Mono', monospace;
}
.slot-dmx  { color: var(--ma-amber); width: 90px; flex-shrink: 0; }
.slot-name { color: #DDDDDD;         flex: 1; }
.slot-phys { color: #AAAAAA;         width: 100px; flex-shrink: 0; }

/* ── Info / warn boxes ──────────────────────────────────────────────────── */
.info-box {
    background: #141414;
    border-left: 3px solid var(--ma-amber);
    border-radius: 0 3px 3px 0;
    padding: 0.65rem 1rem;
    font-size: 0.82rem;
    color: #BBBBBB;
    margin: 0.5rem 0;
}
.warn-box {
    background: #1A1200;
    border-left: 3px solid #D07000;
    border-radius: 0 3px 3px 0;
    padding: 0.65rem 1rem;
    font-size: 0.82rem;
    color: #D09040;
    margin: 0.5rem 0;
}

/* ── Expander headers ───────────────────────────────────────────────────── */
details summary {
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.8rem !important;
    color: #BBBBBB !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
details summary:hover { color: var(--ma-amber) !important; }

/* ── Number inputs ──────────────────────────────────────────────────────── */
div[data-testid="stNumberInput"] input {
    background: var(--ma-panel) !important;
    border: 1px solid var(--ma-border) !important;
    color: #EBEBEB !important;
    font-family: 'Share Tech Mono', monospace !important;
}

/* ── Streamlit success / error / warning alerts ─────────────────────────── */
div[data-testid="stAlert"] {
    border-radius: 3px !important;
}

/* ── Divider ────────────────────────────────────────────────────────────── */
hr { border-color: #3A3A3A !important; }
</style>
""", unsafe_allow_html=True)

st.title("GDTF BUILDER")
st.markdown(
    "<p style='color:#BBBBBB;font-size:0.78rem;margin-top:-0.8rem;font-family:Share Tech Mono,monospace;letter-spacing:0.1em'>"
    "GDTF 1.1 &nbsp;·&nbsp; MA3 WHEELS &amp; SLOTS &nbsp;·&nbsp; PDF AI IMPORT &nbsp;·&nbsp; VECTORWORKS &nbsp;·&nbsp; CAPTURE &nbsp;·&nbsp; ONYX</p>",
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
                            # Do NOT overwrite fixture_name / manufacturer —
                            # the user's entries in the top boxes are always used
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
                                # Do NOT overwrite fixture_name / manufacturer
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
        # Always show the user's entered name, not what the PDF parser found
        display_name = st.session_state.get("fixture_name", "—") or "—"
        display_mfr  = st.session_state.get("manufacturer", "—") or "—"
        st.success(
            f"✅ **{display_name}** by {display_mfr} — "
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
                # Always use the name/manufacturer from the top-of-page inputs
                fname = st.session_state.get("fixture_name", "").strip() or "Unknown Fixture"
                fmfr  = st.session_state.get("manufacturer", "").strip() or "Generic"
                xml_data   = build_gdtf(fname, fmfr, p["modes"])
                gdtf_bytes = create_gdtf_package(xml_data)
                safe_name  = re.sub(r'[^A-Za-z0-9_\-]', '_', fname)

                st.success(f"GDTF package ready — {len(gdtf_bytes):,} bytes")
                col_dl, col_xp = st.columns([1, 2])
                with col_dl:
                    st.download_button(
                        "📦 Download .gdtf", gdtf_bytes,
                        file_name=f"{safe_name}.gdtf",
                        mime="application/octet-stream"
                    )
                    st.markdown("""
                    <div class="info-box" style="margin-top:0.8rem;font-size:0.78rem">
                    <b>MA3 onPC — place file at:</b><br>
                    <code style="font-size:0.72rem">C:\\Users\\[you]\\Documents\\MA Lighting Technologies\\grandMA3\\gma3_library\\fixturetypes\\</code><br><br>
                    Then in MA3: <b>Menu → Patch → Fixture Types → Import</b><br>
                    Look under the <b>User</b> tab, not grandMA3 tab.
                    </div>
                    """, unsafe_allow_html=True)
                with col_xp:
                    with st.expander("View description.xml"):
                        st.code(xml_data, language="xml")
            except Exception as e:
                st.exception(e)

    elif not uploaded_pdf and "pdf_parsed" not in st.session_state:
        st.markdown("""
        <div class="card" style="text-align:center;padding:2.5rem 1rem">
          <p style="font-size:2rem;margin:0">📄</p>
          <p style="color:#AAAAAA;margin:0.4rem 0 0">Upload a PDF fixture manual above to get started.</p>
          <p style="color:#999999;font-size:0.78rem;margin-top:0.4rem">
            Works best with text-based PDFs from manufacturers like Robe, Martin, ETC, Ayrton, GLP.
          </p>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  CHANNEL PICKER CATALOGUE
#  Grouped by fixture section — each entry: (display_label, is_fine_byte)
# ─────────────────────────────────────────────────────────────────────────────
CHANNEL_CATALOGUE = {
    "DIMMING": [
        ("Dimmer", False),
        ("Dimmer Fine", True),
    ],
    "POSITION": [
        ("Pan", False),
        ("Pan Fine", True),
        ("Tilt", False),
        ("Tilt Fine", True),
        ("Pan Speed", False),
        ("Tilt Speed", False),
    ],
    "COLOR — ADDITIVE (RGB/W)": [
        ("Red", False),
        ("Green", False),
        ("Blue", False),
        ("White", False),
        ("Amber", False),
        ("Lime", False),
        ("UV", False),
        ("Indigo", False),
    ],
    "COLOR — SUBTRACTIVE (CMY)": [
        ("Cyan", False),
        ("Magenta", False),
        ("Yellow", False),
    ],
    "COLOR — MISC": [
        ("CTO", False),
        ("CTB", False),
        ("Hue", False),
        ("Saturation", False),
        ("Color Wheel", False),
        ("Color Mix", False),
    ],
    "BEAM": [
        ("Shutter", False),
        ("Strobe", False),
        ("Strobe Speed", False),
        ("Zoom", False),
        ("Zoom Fine", True),
        ("Focus", False),
        ("Focus Fine", True),
        ("Iris", False),
        ("Frost", False),
        ("Diffusion", False),
    ],
    "GOBO": [
        ("Gobo Wheel", False),
        ("Gobo 1", False),
        ("Gobo 2", False),
        ("Gobo Rotation", False),
        ("Gobo Index", False),
        ("Gobo Spin", False),
    ],
    "PRISM / EFFECTS": [
        ("Prism", False),
        ("Prism Rotation", False),
        ("Effects", False),
        ("Effects Speed", False),
        ("Effects Fade", False),
        ("Animation", False),
    ],
    "SHAPERS": [
        ("Blade 1", False),
        ("Blade 2", False),
        ("Blade 3", False),
        ("Blade 4", False),
        ("Blade Rotation", False),
    ],
    "CONTROL": [
        ("Macro", False),
        ("Scene", False),
        ("Program", False),
        ("Function", False),
        ("Control", False),
        ("Reset", False),
        ("Lamp", False),
        ("Fans", False),
        ("Speed", False),
    ],
}


def make_channel_entry(name: str, fine: bool = False) -> dict:
    """Create a fresh channel dict for session state."""
    return {"name": name, "is_fine": fine, "slots": []}


def make_slot_entry(dmx_from: int = 0, dmx_to: int = 10, name: str = "") -> dict:
    return {"dmx_from": dmx_from, "dmx_to": dmx_to, "name": name}


def channel_defs_from_mode(mode: dict) -> list:
    """Convert session-state mode channels to ChannelDef objects for build_gdtf."""
    defs = []
    for ch in mode.get("channel_list", []):
        slots = [
            ChannelSlot(
                name=s["name"],
                dmx_from=s["dmx_from"],
                dmx_to=s["dmx_to"],
                physical_from=round(s["dmx_from"] / 255, 6),
                physical_to=round(s["dmx_to"] / 255, 6),
                slot_name=s["name"],
            )
            for s in ch.get("slots", [])
            if s.get("name", "").strip()
        ]
        defs.append(ChannelDef(
            name=ch["name"],
            is_fine_byte=ch.get("is_fine", False),
            slots=slots,
        ))
    return defs


# ─────────────────────────────────────────────────────────────────────────────
#  TAB 2 — MANUAL ENTRY
# ─────────────────────────────────────────────────────────────────────────────
with tab_manual:

    # ── Session state init ────────────────────────────────────────────────────
    if "modes" not in st.session_state:
        st.session_state.modes = [
            {
                "name": "10 Channel",
                "channel_list": [
                    make_channel_entry("Dimmer"),
                    make_channel_entry("Dimmer Fine", True),
                    make_channel_entry("Red"),
                    make_channel_entry("Green"),
                    make_channel_entry("Blue"),
                    make_channel_entry("White"),
                    make_channel_entry("Amber"),
                    make_channel_entry("UV"),
                    make_channel_entry("Strobe"),
                    make_channel_entry("Macro"),
                ]
            }
        ]

    # ── Mode-level helpers ────────────────────────────────────────────────────
    def add_mode():
        st.session_state.modes.append({
            "name": f"Mode {len(st.session_state.modes) + 1}",
            "channel_list": [make_channel_entry("Dimmer")]
        })

    def copy_mode(i):
        import copy
        src = st.session_state.modes[i]
        clone = copy.deepcopy(src)
        clone["name"] = src["name"] + " (Copy)"
        st.session_state.modes.insert(i + 1, clone)

    def remove_mode(i):
        if len(st.session_state.modes) > 1:
            st.session_state.modes.pop(i)

    # ── Per-mode rendering ────────────────────────────────────────────────────
    for mode_idx, mode in enumerate(st.session_state.modes):

        # Ensure channel_list exists (backwards compat)
        if "channel_list" not in mode:
            old = mode.get("channels", "")
            mode["channel_list"] = [
                make_channel_entry(l.strip(), is_fine(l))
                for l in old.split("\n") if l.strip()
            ]

        ch_list = mode["channel_list"]

        st.markdown('<div class="card">', unsafe_allow_html=True)

        # ── Mode header row ───────────────────────────────────────────────────
        hc1, hc2, hc3, hc4 = st.columns([3, 1, 1, 1])
        with hc1:
            mode["name"] = st.text_input(
                "MODE NAME", value=mode["name"], key=f"mname_{mode_idx}"
            )
        with hc2:
            st.write("")
            st.write("")
            if st.button("⧉ Copy", key=f"copy_{mode_idx}",
                         help="Duplicate this mode"):
                copy_mode(mode_idx)
                st.rerun()
        with hc3:
            st.write("")
            st.write("")
            st.markdown(
                f'<p style="color:var(--ma-amber);font-family:Share Tech Mono,monospace;'
                f'font-size:0.82rem;margin-top:0.6rem">'
                f'{len(ch_list)} CH</p>',
                unsafe_allow_html=True
            )
        with hc4:
            st.write("")
            st.write("")
            if st.button("🗑", key=f"rm_{mode_idx}",
                         disabled=len(st.session_state.modes) == 1,
                         help="Remove this mode"):
                remove_mode(mode_idx)
                st.rerun()

        st.divider()

        # ══════════════════════════════════════════════════════════════════════
        #  TWO-COLUMN LAYOUT: picker left, channel list right
        # ══════════════════════════════════════════════════════════════════════
        left_col, right_col = st.columns([2, 3], gap="medium")

        # ── LEFT: Channel Picker ──────────────────────────────────────────────
        with left_col:
            st.markdown(
                '<p style="color:#BBBBBB;font-family:Share Tech Mono,monospace;'
                'font-size:0.72rem;letter-spacing:0.1em;margin-bottom:0.4rem">'
                'CHANNEL PICKER</p>',
                unsafe_allow_html=True
            )

            for group_name, group_channels in CHANNEL_CATALOGUE.items():
                with st.expander(group_name):
                    gcols = st.columns(2)
                    for ci, (ch_name, ch_fine) in enumerate(group_channels):
                        with gcols[ci % 2]:
                            # Show if already in list
                            already = any(
                                c["name"].lower() == ch_name.lower()
                                for c in ch_list
                            )
                            btn_style = "b-slot" if already else "b-ok"
                            label = f"✓ {ch_name}" if already else f"+ {ch_name}"
                            if st.button(
                                label,
                                key=f"pick_{mode_idx}_{group_name}_{ch_name}",
                                help=f"Add {ch_name} to channel list",
                                use_container_width=True
                            ):
                                if not already:
                                    ch_list.append(make_channel_entry(ch_name, ch_fine))
                                    st.rerun()

            # Custom channel input
            st.markdown(
                '<p style="color:#BBBBBB;font-family:Share Tech Mono,monospace;'
                'font-size:0.68rem;letter-spacing:0.1em;margin:0.8rem 0 0.3rem">'
                'CUSTOM CHANNEL</p>',
                unsafe_allow_html=True
            )
            cust_col1, cust_col2 = st.columns([3, 1])
            with cust_col1:
                custom_name = st.text_input(
                    "Custom name", label_visibility="collapsed",
                    placeholder="e.g. Pixel Row 1",
                    key=f"custom_name_{mode_idx}"
                )
            with cust_col2:
                if st.button("ADD", key=f"custom_add_{mode_idx}",
                             use_container_width=True):
                    if custom_name.strip():
                        ch_list.append(make_channel_entry(
                            custom_name.strip(), is_fine(custom_name)
                        ))
                        st.rerun()

        # ── RIGHT: Channel List ───────────────────────────────────────────────
        with right_col:
            st.markdown(
                '<p style="color:#BBBBBB;font-family:Share Tech Mono,monospace;'
                'font-size:0.72rem;letter-spacing:0.1em;margin-bottom:0.4rem">'
                'CHANNEL LIST — DMX ORDER</p>',
                unsafe_allow_html=True
            )

            if not ch_list:
                st.markdown(
                    '<p style="color:#BBBBBB;font-size:0.82rem">'
                    'No channels yet — use the picker on the left.</p>',
                    unsafe_allow_html=True
                )

            ch_to_delete = None
            ch_to_move   = None  # (index, direction)

            for ci, ch in enumerate(ch_list):
                attr, *_ = resolve_attr(ch["name"])
                known = any(k in ch["name"].lower() for k in ATTR_MAP)
                fine  = ch.get("is_fine", False)

                badge = (
                    f'<span class="badge b-fine">FINE</span>'
                    if fine else
                    f'<span class="badge {"b-ok" if known else "b-unk"}">{attr}</span>'
                )

                # Row: ch number | name | badge | up | down | delete
                r1, r2, r3, r4, r5, r6 = st.columns([0.4, 2.2, 1.2, 0.35, 0.35, 0.35])

                with r1:
                    st.markdown(
                        f'<p style="color:var(--ma-amber);font-family:Share Tech Mono,monospace;'
                        f'font-size:0.78rem;margin-top:0.55rem;text-align:right">'
                        f'{ci + 1}</p>',
                        unsafe_allow_html=True
                    )
                with r2:
                    new_name = st.text_input(
                        "ch", value=ch["name"],
                        label_visibility="collapsed",
                        key=f"chname_{mode_idx}_{ci}"
                    )
                    if new_name != ch["name"]:
                        ch["name"] = new_name
                with r3:
                    st.markdown(
                        f'<div style="margin-top:0.5rem">{badge}</div>',
                        unsafe_allow_html=True
                    )
                with r4:
                    if st.button("▲", key=f"up_{mode_idx}_{ci}",
                                 disabled=ci == 0,
                                 help="Move up"):
                        ch_to_move = (ci, -1)
                with r5:
                    if st.button("▼", key=f"dn_{mode_idx}_{ci}",
                                 disabled=ci == len(ch_list) - 1,
                                 help="Move down"):
                        ch_to_move = (ci, 1)
                with r6:
                    if st.button("✕", key=f"del_{mode_idx}_{ci}",
                                 help="Remove channel"):
                        ch_to_delete = ci

                # ── DMX Slot Editor ───────────────────────────────────────────
                # Only show for channels that benefit from slot data
                # (not continuous channels like dimmer/pan/tilt/RGB)
                CONTINUOUS = {
                    "Dimmer", "Pan", "Tilt", "Red", "Green", "Blue",
                    "White", "Amber", "Lime", "UV", "Indigo",
                    "Cyan", "Magenta", "Yellow", "CTO", "CTB",
                    "Hue", "Saturation", "Pan Fine", "Tilt Fine",
                    "Dimmer Fine", "Zoom Fine", "Focus Fine",
                    "Pan Speed", "Tilt Speed",
                }
                show_slots = (
                    not fine and
                    ch["name"] not in CONTINUOUS and
                    known
                )

                if show_slots:
                    slots = ch.setdefault("slots", [])
                    with st.expander(
                        f"  ↳ DMX slots ({len(slots)}) — click to edit",
                        expanded=len(slots) > 0
                    ):
                        slot_to_delete = None
                        for si, slot in enumerate(slots):
                            sc1, sc2, sc3, sc4 = st.columns([1, 1, 2, 0.4])
                            with sc1:
                                slot["dmx_from"] = st.number_input(
                                    "From", min_value=0, max_value=255,
                                    value=slot["dmx_from"],
                                    key=f"sf_{mode_idx}_{ci}_{si}",
                                    label_visibility="collapsed"
                                )
                            with sc2:
                                slot["dmx_to"] = st.number_input(
                                    "To", min_value=0, max_value=255,
                                    value=slot["dmx_to"],
                                    key=f"st_{mode_idx}_{ci}_{si}",
                                    label_visibility="collapsed"
                                )
                            with sc3:
                                slot["name"] = st.text_input(
                                    "Label", value=slot["name"],
                                    placeholder="e.g. Open, Gobo 3, Slow CW",
                                    key=f"sn_{mode_idx}_{ci}_{si}",
                                    label_visibility="collapsed"
                                )
                            with sc4:
                                if st.button("✕", key=f"sdel_{mode_idx}_{ci}_{si}"):
                                    slot_to_delete = si

                        if slot_to_delete is not None:
                            slots.pop(slot_to_delete)
                            st.rerun()

                        # Auto-suggest next DMX from value
                        next_from = slots[-1]["dmx_to"] + 1 if slots else 0
                        next_to   = min(next_from + 10, 255)
                        if st.button(
                            f"＋ Add slot  (next: {next_from}–{next_to})",
                            key=f"sadd_{mode_idx}_{ci}",
                            use_container_width=True
                        ):
                            slots.append(make_slot_entry(next_from, next_to, ""))
                            st.rerun()

                        # Quick-fill presets for common channels
                        PRESETS = {
                            "Shutter": [
                                (0,9,"Closed"),(10,19,"Open"),
                                (20,129,"Strobe Slow→Fast"),(130,139,"Open"),
                                (140,189,"Pulse"),(190,199,"Open"),
                                (200,249,"Random Strobe"),(250,255,"Open"),
                            ],
                            "Strobe": [
                                (0,9,"Closed"),(10,19,"Open"),
                                (20,255,"Strobe Slow→Fast"),
                            ],
                            "Macro": [
                                (0,9,"Off"),(10,19,"Macro 1"),(20,29,"Macro 2"),
                                (30,39,"Macro 3"),(40,49,"Macro 4"),(50,59,"Macro 5"),
                            ],
                            "Function": [
                                (0,9,"No Function"),(10,19,"Reset"),
                                (20,29,"Lamp On"),(30,39,"Lamp Off"),
                            ],
                            "Control": [
                                (0,9,"No Function"),(10,19,"Reset"),
                                (20,29,"Lamp On"),(30,39,"Lamp Off"),
                            ],
                            "Color Wheel": [
                                (0,9,"Open"),(10,19,"Color 1"),(20,29,"Color 2"),
                                (30,39,"Color 3"),(40,49,"Color 4"),(50,59,"Color 5"),
                                (60,69,"Color 6"),(70,79,"Color 7"),(80,89,"Color 8"),
                            ],
                            "Gobo Wheel": [
                                (0,9,"Open"),(10,19,"Gobo 1"),(20,29,"Gobo 2"),
                                (30,39,"Gobo 3"),(40,49,"Gobo 4"),(50,59,"Gobo 5"),
                                (60,69,"Gobo 6"),(70,79,"Gobo 7"),
                            ],
                            "Prism": [
                                (0,9,"No Prism"),(10,255,"Prism"),
                            ],
                            "Effects": [
                                (0,9,"No Effect"),(10,19,"Effect 1"),
                                (20,29,"Effect 2"),(30,39,"Effect 3"),
                            ],
                        }

                        ch_key = ch["name"]
                        preset_match = next(
                            (v for k, v in PRESETS.items()
                             if k.lower() in ch_key.lower()), None
                        )
                        if preset_match and not slots:
                            if st.button(
                                "⚡ Quick-fill preset slots",
                                key=f"preset_{mode_idx}_{ci}",
                                use_container_width=True
                            ):
                                for pf, pt, pn in preset_match:
                                    slots.append(make_slot_entry(pf, pt, pn))
                                st.rerun()

            st.markdown(
                '<div style="height:4px;border-bottom:1px solid var(--ma-border);'
                'margin:4px 0 8px"></div>',
                unsafe_allow_html=True
            )

            # Apply reorder / delete after rendering all rows
            if ch_to_delete is not None:
                ch_list.pop(ch_to_delete)
                st.rerun()
            if ch_to_move is not None:
                i, d = ch_to_move
                j = i + d
                if 0 <= j < len(ch_list):
                    ch_list[i], ch_list[j] = ch_list[j], ch_list[i]
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)  # end card

    # ── Add mode button ───────────────────────────────────────────────────────
    st.button("＋ Add Mode", on_click=add_mode)
    st.divider()

    # ── Generate ─────────────────────────────────────────────────────────────
    if st.button("⚡ Generate .gdtf File", type="primary", key="gen_manual"):
        fname = st.session_state.get("fixture_name", fixture_name).strip()
        mfr   = st.session_state.get("manufacturer", manufacturer).strip()
        if not fname:
            st.error("Enter a fixture model name above.")
        else:
            modes_dict = {
                m["name"]: channel_defs_from_mode(m)
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
                    st.markdown("""
                    <div class="info-box" style="margin-top:0.8rem;font-size:0.78rem">
                    <b>MA3 onPC — place file at:</b><br>
                    <code style="font-size:0.72rem">C:\\Users\\[you]\\Documents\\MA Lighting Technologies\\grandMA3\\gma3_library\\fixturetypes\\</code><br><br>
                    Then: <b>Menu → Patch → Fixture Types → Import → User tab</b>
                    </div>
                    """, unsafe_allow_html=True)
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
                    f'<span style="color:#999999;font-size:0.72rem"> → {attr}</span>',
                    unsafe_allow_html=True
                )
