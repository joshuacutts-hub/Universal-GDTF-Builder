"""
GDTF 1.1 Builder — Manual Entry
MA3 / Vectorworks / Capture / Onyx compatible
"""

import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile, io, uuid, re, copy

# ══════════════════════════════════════════════════════════════════════════════
#  GDTF ATTRIBUTE MAP
# ══════════════════════════════════════════════════════════════════════════════
ATTR_MAP = {
    "dimmer":           ("Dimmer",              "Dimming",  "Intensity", "Dimmer"),
    "intensity":        ("Dimmer",              "Dimming",  "Intensity", "Dimmer"),
    "master":           ("Dimmer",              "Dimming",  "Intensity", "Dimmer"),
    "pan":              ("Pan",                 "Position", "Position",  "PanTilt"),
    "tilt":             ("Tilt",                "Position", "Position",  "PanTilt"),
    "pan speed":        ("PanRotate",           "Position", "Position",  "PanTilt"),
    "tilt speed":       ("TiltRotate",          "Position", "Position",  "PanTilt"),
    "red":              ("ColorAdd_R",          "Color",    "Color",     "RGB"),
    "green":            ("ColorAdd_G",          "Color",    "Color",     "RGB"),
    "blue":             ("ColorAdd_B",          "Color",    "Color",     "RGB"),
    "white":            ("ColorAdd_W",          "Color",    "Color",     "RGBW"),
    "amber":            ("ColorAdd_A",          "Color",    "Color",     "RGBW"),
    "lime":             ("ColorAdd_L",          "Color",    "Color",     "RGBW"),
    "uv":               ("ColorAdd_UV",         "Color",    "Color",     "RGBW"),
    "indigo":           ("ColorAdd_I",          "Color",    "Color",     "RGBW"),
    "cyan":             ("ColorSub_C",          "Color",    "Color",     "CMY"),
    "magenta":          ("ColorSub_M",          "Color",    "Color",     "CMY"),
    "yellow":           ("ColorSub_Y",          "Color",    "Color",     "CMY"),
    "cto":              ("CTO",                 "Color",    "Color",     "CTO"),
    "ctb":              ("CTB",                 "Color",    "Color",     "CTB"),
    "hue":              ("CIE_X",              "Color",    "Color",     "HSB"),
    "saturation":       ("CIE_Y",              "Color",    "Color",     "HSB"),
    "color wheel":      ("Color1",             "Color",    "Color",     "ColorWheel"),
    "colour wheel":     ("Color1",             "Color",    "Color",     "ColorWheel"),
    "color":            ("Color1",             "Color",    "Color",     "ColorWheel"),
    "colour":           ("Color1",             "Color",    "Color",     "ColorWheel"),
    "color mix":        ("ColorMixMode",       "Color",    "Color",     "ColorWheel"),
    "shutter":          ("Shutter1",           "Beam",     "Beam",      "Shutter"),
    "strobe":           ("Shutter1Strobe",     "Beam",     "Beam",      "Shutter"),
    "strobe rate":      ("Shutter1StrobeFreq", "Beam",     "Beam",      "Shutter"),
    "strobe speed":     ("Shutter1StrobeFreq", "Beam",     "Beam",      "Shutter"),
    "zoom":             ("Zoom",               "Beam",     "Beam",      "Zoom"),
    "focus":            ("Focus1",             "Beam",     "Beam",      "Focus"),
    "iris":             ("Iris",               "Beam",     "Beam",      "Iris"),
    "frost":            ("Frost1",             "Beam",     "Beam",      "Frost"),
    "diffusion":        ("Frost1",             "Beam",     "Beam",      "Frost"),
    "gobo":             ("Gobo1",             "Gobo",     "Gobo",      "Gobo"),
    "gobo wheel":       ("Gobo1",             "Gobo",     "Gobo",      "Gobo"),
    "gobo 1":           ("Gobo1",             "Gobo",     "Gobo",      "Gobo"),
    "gobo 2":           ("Gobo2",             "Gobo",     "Gobo",      "Gobo"),
    "gobo rotation":    ("Gobo1Pos",          "Gobo",     "Gobo",      "Gobo"),
    "gobo spin":        ("Gobo1PosRotate",    "Gobo",     "Gobo",      "Gobo"),
    "gobo index":       ("Gobo1Pos",          "Gobo",     "Gobo",      "Gobo"),
    "prism":            ("Prism1",            "Beam",     "Beam",      "Prism"),
    "prism rotation":   ("Prism1Pos",         "Beam",     "Beam",      "Prism"),
    "effects":          ("Effects1",          "Beam",     "Beam",      "Effects"),
    "effect":           ("Effects1",          "Beam",     "Beam",      "Effects"),
    "animation":        ("Effects1",          "Beam",     "Beam",      "Effects"),
    "effects speed":    ("EffectsSpeed",      "Beam",     "Beam",      "Effects"),
    "effects fade":     ("EffectsFade",       "Beam",     "Beam",      "Effects"),
    "blade 1":          ("Blade1A",           "Shapers",  "Shapers",   "Blade"),
    "blade 2":          ("Blade2A",           "Shapers",  "Shapers",   "Blade"),
    "blade 3":          ("Blade3A",           "Shapers",  "Shapers",   "Blade"),
    "blade 4":          ("Blade4A",           "Shapers",  "Shapers",   "Blade"),
    "blade rotation":   ("ShaperRot",         "Shapers",  "Shapers",   "Blade"),
    "macro":            ("Macro",             "Control",  "Control",   "Macro"),
    "scene":            ("Macro",             "Control",  "Control",   "Macro"),
    "program":          ("Macro",             "Control",  "Control",   "Macro"),
    "function":         ("Function",          "Control",  "Control",   "Function"),
    "control":          ("Function",          "Control",  "Control",   "Function"),
    "reset":            ("Function",          "Control",  "Control",   "Function"),
    "lamp":             ("LampControl",       "Control",  "Control",   "Function"),
    "fans":             ("Function",          "Control",  "Control",   "Function"),
    "speed":            ("EffectsSpeed",      "Beam",     "Beam",      "Effects"),
    "video":            ("VideoEffect1Type",  "Control",  "Control",   "Function"),
    "media":            ("VideoEffect1Type",  "Control",  "Control",   "Function"),
}

WHEEL_ATTRS = {
    "Color1", "Color2", "Gobo1", "Gobo2", "Gobo1Pos", "Gobo2Pos",
    "Prism1", "Effects1", "Animation1", "Macro", "LampControl",
    "Function", "Shutter1", "Shutter1Strobe",
}

# Channels that are continuous (no DMX slots needed)
CONTINUOUS = {
    "Dimmer", "Dimmer Fine", "Pan", "Pan Fine", "Tilt", "Tilt Fine",
    "Red", "Green", "Blue", "White", "Amber", "Lime", "UV", "Indigo",
    "Cyan", "Magenta", "Yellow", "CTO", "CTB", "Hue", "Saturation",
    "Zoom", "Zoom Fine", "Focus", "Focus Fine", "Iris",
    "Pan Speed", "Tilt Speed", "Effects Speed", "Effects Fade",
    "Gobo Rotation", "Gobo Spin", "Gobo Index", "Prism Rotation",
    "Blade 1", "Blade 2", "Blade 3", "Blade 4", "Blade Rotation",
}

PRESETS = {
    "Shutter": [
        (0,9,"Closed"),(10,19,"Open"),
        (20,129,"Strobe Slow-Fast"),(130,139,"Open"),
        (140,189,"Pulse"),(190,199,"Open"),
        (200,249,"Random Strobe"),(250,255,"Open"),
    ],
    "Strobe": [(0,9,"Closed"),(10,19,"Open"),(20,255,"Strobe Slow-Fast")],
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
    "Colour Wheel": [
        (0,9,"Open"),(10,19,"Color 1"),(20,29,"Color 2"),
        (30,39,"Color 3"),(40,49,"Color 4"),(50,59,"Color 5"),
    ],
    "Gobo Wheel": [
        (0,9,"Open"),(10,19,"Gobo 1"),(20,29,"Gobo 2"),
        (30,39,"Gobo 3"),(40,49,"Gobo 4"),(50,59,"Gobo 5"),
        (60,69,"Gobo 6"),(70,79,"Gobo 7"),
    ],
    "Gobo 1": [
        (0,9,"Open"),(10,19,"Gobo 1"),(20,29,"Gobo 2"),
        (30,39,"Gobo 3"),(40,49,"Gobo 4"),(50,59,"Gobo 5"),
    ],
    "Gobo 2": [
        (0,9,"Open"),(10,19,"Gobo 1"),(20,29,"Gobo 2"),
        (30,39,"Gobo 3"),(40,49,"Gobo 4"),(50,59,"Gobo 5"),
    ],
    "Prism": [(0,9,"No Prism"),(10,255,"Prism")],
    "Effects": [
        (0,9,"No Effect"),(10,19,"Effect 1"),
        (20,29,"Effect 2"),(30,39,"Effect 3"),
    ],
    "Scene": [
        (0,9,"Off"),(10,19,"Scene 1"),(20,29,"Scene 2"),
        (30,39,"Scene 3"),(40,49,"Scene 4"),(50,59,"Scene 5"),
    ],
    "Program": [
        (0,9,"Off"),(10,19,"Program 1"),(20,29,"Program 2"),
        (30,39,"Program 3"),(40,49,"Program 4"),
    ],
}

CHANNEL_CATALOGUE = {
    "DIMMING": [("Dimmer",False),("Dimmer Fine",True)],
    "POSITION": [
        ("Pan",False),("Pan Fine",True),
        ("Tilt",False),("Tilt Fine",True),
        ("Pan Speed",False),("Tilt Speed",False),
    ],
    "COLOR — RGB/W": [
        ("Red",False),("Green",False),("Blue",False),
        ("White",False),("Amber",False),("Lime",False),
        ("UV",False),("Indigo",False),
    ],
    "COLOR — CMY": [("Cyan",False),("Magenta",False),("Yellow",False)],
    "COLOR — MISC": [
        ("CTO",False),("CTB",False),
        ("Hue",False),("Saturation",False),
        ("Color Wheel",False),("Color Mix",False),
    ],
    "BEAM": [
        ("Shutter",False),("Strobe",False),("Strobe Speed",False),
        ("Zoom",False),("Zoom Fine",True),
        ("Focus",False),("Focus Fine",True),
        ("Iris",False),("Frost",False),("Diffusion",False),
    ],
    "GOBO": [
        ("Gobo Wheel",False),("Gobo 1",False),("Gobo 2",False),
        ("Gobo Rotation",False),("Gobo Index",False),("Gobo Spin",False),
    ],
    "PRISM / EFFECTS": [
        ("Prism",False),("Prism Rotation",False),
        ("Effects",False),("Effects Speed",False),
        ("Effects Fade",False),("Animation",False),
    ],
    "SHAPERS": [
        ("Blade 1",False),("Blade 2",False),
        ("Blade 3",False),("Blade 4",False),
        ("Blade Rotation",False),
    ],
    "CONTROL": [
        ("Macro",False),("Scene",False),("Program",False),
        ("Function",False),("Control",False),("Reset",False),
        ("Lamp",False),("Fans",False),("Speed",False),
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

class ChannelSlot:
    def __init__(self, name, dmx_from, dmx_to,
                 physical_from=0.0, physical_to=1.0, slot_name=""):
        self.name          = name
        self.dmx_from      = dmx_from
        self.dmx_to        = dmx_to
        self.physical_from = physical_from
        self.physical_to   = physical_to
        self.slot_name     = slot_name or name

class ChannelDef:
    def __init__(self, name, is_fine_byte=False, slots=None):
        self.name         = name
        self.is_fine_byte = is_fine_byte
        self.slots        = slots or []


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def resolve_attr(raw):
    clean = raw.lower().strip()
    if clean in ATTR_MAP:
        return ATTR_MAP[clean]
    for key, val in ATTR_MAP.items():
        if key in clean:
            return val
    safe = re.sub(r'[^A-Za-z0-9_]', '_', raw.strip()) or "Custom"
    return (safe, "Control", "Control", safe)

def is_fine(name):
    return any(w in name.lower()
               for w in ["fine", " lsb", "16-bit", "16bit", "low byte"])

def _safe(text, fallback="Ch"):
    s = text.strip()
    for old, new in [("°","deg"),("%","pct"),("/","_"),(".","_"),
                     (":","_"),(";","_")]:
        s = s.replace(old, new)
    s = re.sub(r'[^A-Za-z0-9_ \-]', '', s)
    s = re.sub(r'[ _]+', '_', s).strip('_')
    if not s or s[0].isdigit():
        s = fallback + "_" + s
    return s or fallback

def _guid():
    raw = uuid.uuid4().hex.upper()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

def _new_channel_id():
    return uuid.uuid4().hex[:8]

def make_channel_entry(name, fine=False):
    return {"id": _new_channel_id(), "name": name,
            "is_fine": fine, "slots": []}

def make_slot_entry(dmx_from=0, dmx_to=10, name=""):
    return {"dmx_from": dmx_from, "dmx_to": dmx_to, "name": name}

def channel_defs_from_mode(mode):
    defs = []
    for ch in mode.get("channel_list", []):
        slots = [
            ChannelSlot(
                name=s["name"],
                dmx_from=int(s["dmx_from"]),
                dmx_to=int(s["dmx_to"]),
                physical_from=round(int(s["dmx_from"]) / 255, 6),
                physical_to=round(int(s["dmx_to"]) / 255, 6),
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


# ══════════════════════════════════════════════════════════════════════════════
#  GDTF XML BUILDER
#  DMX slots → ChannelFunction (one per slot) + ChannelSet per slot
#  This is what MA3 reads for Channel Sets in the fixture sheet
# ══════════════════════════════════════════════════════════════════════════════

def build_gdtf(fixture_name, manufacturer, modes_dict):
    root = ET.Element("GDTF", DataVersion="1.1")

    safe_name  = _safe(fixture_name, "Fixture")
    safe_short = re.sub(r'[^A-Z0-9]', '', safe_name.upper())[:8] or "FIXTURE"
    safe_mfr   = _safe(manufacturer, "Generic")

    ft = ET.SubElement(root, "FixtureType",
        Name=safe_name, ShortName=safe_short, LongName=safe_name,
        Manufacturer=safe_mfr, Description="Generated by GDTF Builder",
        FixtureTypeID=_guid(), Thumbnail="", RefFT="", CanHaveChildren="No")

    # ── Collect used attributes ──────────────────────────────────────────────
    used_attrs = {}
    for channels in modes_dict.values():
        for ch in channels:
            if not ch.is_fine_byte and ch.name.strip():
                attr, fg, feat, ag = resolve_attr(ch.name)
                used_attrs[attr] = (fg, feat, ag)

    # ── AttributeDefinitions ────────────────────────────────────────────────
    attr_defs = ET.SubElement(ft, "AttributeDefinitions")
    ag_xml    = ET.SubElement(attr_defs, "ActivationGroups")
    ag_seen   = set()
    for _, (fg, feat, ag) in used_attrs.items():
        if ag not in ag_seen:
            ET.SubElement(ag_xml, "ActivationGroup", Name=ag)
            ag_seen.add(ag)

    fg_xml  = ET.SubElement(attr_defs, "FeatureGroups")
    fg_used = {}
    for _, (fg, feat, ag) in used_attrs.items():
        fg_used.setdefault(fg, set()).add(feat)
    for fg_name, feats in fg_used.items():
        fg_el = ET.SubElement(fg_xml, "FeatureGroup",
                              Name=fg_name, Pretty=fg_name)
        for f in sorted(feats):
            ET.SubElement(fg_el, "Feature", Name=f)

    attrs_xml = ET.SubElement(attr_defs, "Attributes")
    for attr, (fg, feat, ag) in used_attrs.items():
        ET.SubElement(attrs_xml, "Attribute",
            Name=attr, Pretty=attr, ActivationGroup=ag,
            Feature=f"{fg}.{feat}", PhysicalUnit="None",
            Color="0.3127,0.3290,100.000000")

    # ── Wheels ───────────────────────────────────────────────────────────────
    wheel_registry = {}
    for mode_channels in modes_dict.values():
        for ch in mode_channels:
            if ch.is_fine_byte or not ch.slots:
                continue
            attr, *_ = resolve_attr(ch.name)
            if attr not in WHEEL_ATTRS or attr in wheel_registry:
                continue
            wheel_registry[attr] = _safe(ch.name, attr)

    wheels_el = ET.SubElement(ft, "Wheels")
    for mode_channels in modes_dict.values():
        for ch in mode_channels:
            if ch.is_fine_byte or not ch.slots:
                continue
            attr, *_ = resolve_attr(ch.name)
            wname = wheel_registry.get(attr)
            if not wname:
                continue
            if wheels_el.find(f"Wheel[@Name='{wname}']") is not None:
                continue
            wheel_el = ET.SubElement(wheels_el, "Wheel", Name=wname)
            # Slot 0 = Open (GDTF spec requires this)
            ET.SubElement(wheel_el, "Slot", Name="Open",
                          Color="0.3127,0.3290,100.000000", MediaFileName="")
            for slot in ch.slots:
                ET.SubElement(wheel_el, "Slot",
                              Name=_safe(slot.slot_name, "Slot"),
                              Color="0.3127,0.3290,100.000000",
                              MediaFileName="")

    # ── Physical / Models / Geometries ───────────────────────────────────────
    phys = ET.SubElement(ft, "PhysicalDescriptions")
    ET.SubElement(phys, "Emitters")
    ET.SubElement(phys, "Filters")
    ET.SubElement(phys, "DMXProfiles")
    ET.SubElement(phys, "CRIs")
    ET.SubElement(ft, "Models")
    geos = ET.SubElement(ft, "Geometries")
    ET.SubElement(geos, "Geometry", Name="Body", Model="",
                  Position="1,0,0,0 0,1,0,0 0,0,1,0 0,0,0,1")

    # ── DMX Modes ────────────────────────────────────────────────────────────
    dmx_modes_el = ET.SubElement(ft, "DMXModes")

    for mode_name, channels in modes_dict.items():
        safe_mode = _safe(mode_name, "Mode")
        mode_el   = ET.SubElement(dmx_modes_el, "DMXMode",
                                  Name=safe_mode, Geometry="Body")
        chs_el    = ET.SubElement(mode_el, "DMXChannels")

        offset            = 1
        prev_ch_el        = None
        prev_offset_start = None

        for ch in channels:
            if not ch.name.strip():
                continue

            if ch.is_fine_byte:
                if prev_ch_el is not None:
                    prev_ch_el.set("Offset",
                                   f"{prev_offset_start},{offset}")
                offset += 1
                prev_ch_el = None
                continue

            attr, fg, feat, ag = resolve_attr(ch.name)
            safe_ch = _safe(ch.name, f"Ch{offset}")

            if ch.slots:
                # ── Slotted channel ──────────────────────────────────────────
                # One ChannelFunction covering the full 0-255 range,
                # with one ChannelSet per user-defined slot.
                # This is what MA3 reads as "Channel Sets" — they appear
                # in the fixture sheet and snap positions on the encoder.
                wname = wheel_registry.get(attr, "")

                # The single CF spans 0-255, name = attribute name
                cf_name    = attr
                initial_fn = f"{safe_mode}.{safe_ch}.{attr}.{cf_name}"

                ch_el = ET.SubElement(chs_el, "DMXChannel",
                    DMXBreak="1", Offset=str(offset),
                    Default="0/1", Highlight="255/1",
                    Geometry="Body", InitialFunction=initial_fn)

                log_el = ET.SubElement(ch_el, "LogicalChannel",
                    Attribute=attr, Snap="Yes",  # Snap=Yes for stepped channels
                    Master="None", MibFade="0", DMXChangeTimeLimit="0")

                cf_kwargs = dict(
                    Name=cf_name,
                    Attribute=attr,
                    OriginalAttribute=_safe(ch.name),
                    DMXFrom="0/1",
                    Default="0/1",
                    PhysicalFrom="0.000000",
                    PhysicalTo="1.000000",
                    RealFade="0",
                    RealAcceleration="0",
                    WheelSlotIndex="0",
                )
                if wname:
                    cf_kwargs["Wheel"] = wname

                cf_el = ET.SubElement(log_el, "ChannelFunction", **cf_kwargs)

                # ChannelSet per slot — this is what MA3 shows as
                # named snap positions and channel set buttons
                for slot_idx, slot in enumerate(ch.slots):
                    cs_kwargs = dict(
                        Name=_safe(slot.name, f"Set{slot_idx+1}"),
                        DMXFrom=f"{slot.dmx_from}/1",
                        PhysicalFrom=f"{slot.physical_from:.6f}",
                        PhysicalTo=f"{slot.physical_to:.6f}",
                    )
                    # Link to wheel slot if this attribute has a wheel
                    if wname:
                        cs_kwargs["WheelSlotIndex"] = str(slot_idx + 1)
                    ET.SubElement(cf_el, "ChannelSet", **cs_kwargs)

            else:
                # ── Continuous channel ───────────────────────────────────────
                cf_name    = attr
                initial_fn = f"{safe_mode}.{safe_ch}.{attr}.{cf_name}"

                ch_el = ET.SubElement(chs_el, "DMXChannel",
                    DMXBreak="1", Offset=str(offset),
                    Default="0/1", Highlight="255/1",
                    Geometry="Body", InitialFunction=initial_fn)

                log_el = ET.SubElement(ch_el, "LogicalChannel",
                    Attribute=attr, Snap="No",
                    Master="None", MibFade="0", DMXChangeTimeLimit="0")

                ET.SubElement(log_el, "ChannelFunction",
                    Name=cf_name, Attribute=attr,
                    OriginalAttribute=_safe(ch.name),
                    DMXFrom="0/1", Default="0/1",
                    PhysicalFrom="0.000000", PhysicalTo="1.000000",
                    RealFade="0", RealAcceleration="0",
                    WheelSlotIndex="0")

            prev_ch_el        = ch_el
            prev_offset_start = offset
            offset           += 1

        ET.SubElement(mode_el, "Relations")
        ET.SubElement(mode_el, "FTMacros")

    revisions = ET.SubElement(ft, "Revisions")
    ET.SubElement(revisions, "Revision",
                  UserID="0", Date="2024-01-01T00:00:00",
                  Text="Created by GDTF Builder",
                  ModifiedBy="GDTFBuilder")
    ET.SubElement(ft, "FTPresets")
    ET.SubElement(ft, "FTRDMInfo")

    raw    = ET.tostring(root, encoding="unicode", xml_declaration=False)
    pretty = minidom.parseString(
        f'<?xml version="1.0" encoding="UTF-8"?>{raw}'
    ).toprettyxml(indent="  ", encoding=None)
    return pretty.replace('<?xml version="1.0" ?>',
                          '<?xml version="1.0" encoding="UTF-8"?>')


def create_gdtf_package(xml_content):
    buf = io.BytesIO()
    # GDTF spec requires ZIP_STORED — compressed zips fail silently in MA3
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("description.xml", xml_content.encode("utf-8"))
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
#  STREAMLIT PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="GDTF Builder", page_icon="💡",
                   layout="wide", initial_sidebar_state="collapsed")

# Force dark before Streamlit renders — kills white flash
st.markdown("""
<style>
html,body,#root,#root>div,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
[data-testid="block-container"],
[data-testid="stMain"],
.main,.block-container,section.main {
    background-color:#0A0A0A !important;
    background:#0A0A0A !important;
}
[data-testid="stHeader"] {
    background-color:#0A0A0A !important;
    border-bottom:1px solid #3A3A3A !important;
}
[data-testid="stToolbar"] { background:#0A0A0A !important; }
::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track { background:#0A0A0A; }
::-webkit-scrollbar-thumb { background:#3A3A3A; border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:#E8A000; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@300;400;500;600&display=swap');

:root {
    --ma-black:    #0A0A0A;
    --ma-panel:    #1A1A1A;
    --ma-border:   #3A3A3A;
    --ma-amber:    #E8A000;
    --ma-amber-dk: #A06800;
    --ma-text:     #EBEBEB;
    --ma-muted:    #AAAAAA;
    --ma-green:    #00E000;
    --ma-red:      #FF5555;
    --ma-blue:     #4AB0FF;
}

html,body,[class*="css"] {
    font-family:'Barlow',sans-serif;
    background:var(--ma-black) !important;
    color:var(--ma-text);
}
h1,h2,h3,h4 {
    font-family:'Share Tech Mono',monospace;
    letter-spacing:0.04em;
    color:var(--ma-amber);
}
/* Mobile-friendly max-width and padding */
.block-container {
    padding-top:1rem !important;
    padding-left:1rem !important;
    padding-right:1rem !important;
    max-width:900px;
}

/* ── Inputs ─────────────────────────────────────────────────────────────── */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
    background:var(--ma-panel) !important;
    border:1px solid var(--ma-border) !important;
    border-radius:3px !important;
    color:var(--ma-text) !important;
    font-family:'Share Tech Mono',monospace !important;
    font-size:0.9rem !important;
    /* Larger tap target on mobile */
    min-height:2.4rem !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color:var(--ma-amber) !important;
    box-shadow:0 0 0 2px rgba(232,160,0,0.2) !important;
}
div[data-testid="stNumberInput"] input {
    background:var(--ma-panel) !important;
    border:1px solid var(--ma-border) !important;
    color:var(--ma-text) !important;
    font-family:'Share Tech Mono',monospace !important;
    min-height:2.4rem !important;
}

label, .stRadio label, div[data-testid="stWidgetLabel"] {
    color:#BBBBBB !important;
    font-size:0.75rem !important;
    text-transform:uppercase;
    letter-spacing:0.08em;
}

/* ── Buttons — larger tap targets on mobile ─────────────────────────────── */
.stButton>button[kind="primary"] {
    background:var(--ma-amber);
    border:1px solid var(--ma-amber);
    border-bottom:2px solid var(--ma-amber-dk);
    border-radius:3px; color:#000;
    font-family:'Share Tech Mono',monospace;
    font-size:0.85rem; font-weight:700;
    letter-spacing:0.08em;
    padding:0.65rem 1.5rem;
    min-height:2.8rem;
    text-transform:uppercase;
    width:100%;
    transition:background .15s;
}
.stButton>button[kind="primary"]:hover { background:#FFB800; }

.stButton>button:not([kind="primary"]) {
    background:var(--ma-panel);
    border:1px solid var(--ma-border);
    border-bottom:2px solid #111;
    border-radius:3px; color:#CCCCCC;
    font-family:'Share Tech Mono',monospace;
    font-size:0.8rem; letter-spacing:0.04em;
    text-transform:uppercase;
    min-height:2.6rem;
    transition:border-color .15s,color .15s;
}
.stButton>button:not([kind="primary"]):hover {
    border-color:var(--ma-amber);
    color:var(--ma-amber);
}

/* ── Cards ──────────────────────────────────────────────────────────────── */
.card {
    background:var(--ma-panel);
    border:1px solid var(--ma-border);
    border-top:2px solid var(--ma-amber);
    border-radius:3px;
    padding:0.85rem 1rem;
    margin-bottom:1rem;
}

/* ── Badges ─────────────────────────────────────────────────────────────── */
.badge {
    display:inline-block; border-radius:2px;
    padding:3px 8px;
    font-family:'Share Tech Mono',monospace;
    font-size:0.7rem; margin:2px; border:1px solid;
    text-transform:uppercase; letter-spacing:0.04em;
}
.b-ok   { color:var(--ma-amber); border-color:#E8A00066; background:#E8A00020; }
.b-fine { color:var(--ma-blue);  border-color:#4AB0FF66; background:#4AB0FF20; }
.b-slot { color:var(--ma-green); border-color:#00E00066; background:#00E00020; }
.b-unk  { color:var(--ma-red);   border-color:#FF555566; background:#FF555520; }

/* ── Info / warn ────────────────────────────────────────────────────────── */
.info-box {
    background:#141414; border-left:3px solid var(--ma-amber);
    border-radius:0 3px 3px 0; padding:0.7rem 1rem;
    font-size:0.82rem; color:#BBBBBB; margin:0.5rem 0;
}
.warn-box {
    background:#1A1200; border-left:3px solid #D07000;
    border-radius:0 3px 3px 0; padding:0.7rem 1rem;
    font-size:0.82rem; color:#D09040; margin:0.5rem 0;
}

/* ── Channel row ────────────────────────────────────────────────────────── */
.ch-num {
    color:var(--ma-amber);
    font-family:'Share Tech Mono',monospace;
    font-size:0.82rem;
    margin-top:0.6rem;
    text-align:right;
}

/* ── Slot table ─────────────────────────────────────────────────────────── */
.slot-row {
    display:flex; gap:8px; align-items:center;
    padding:4px 0; border-bottom:1px solid var(--ma-border);
    font-size:0.78rem; font-family:'Share Tech Mono',monospace;
}
.slot-dmx  { color:var(--ma-amber); width:90px; flex-shrink:0; }
.slot-name { color:#DDDDDD; flex:1; }

/* ── Expanders ──────────────────────────────────────────────────────────── */
details summary {
    font-family:'Share Tech Mono',monospace !important;
    font-size:0.8rem !important; color:#BBBBBB !important;
    text-transform:uppercase; letter-spacing:0.06em;
}
details summary:hover { color:var(--ma-amber) !important; }

hr { border-color:#3A3A3A !important; }

/* ── Mobile tweaks ──────────────────────────────────────────────────────── */
@media (max-width:640px) {
    .block-container {
        padding-left:0.5rem !important;
        padding-right:0.5rem !important;
    }
    h1 { font-size:1.4rem !important; }
    .stButton>button { min-height:3rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════════════════════════

col_header_left, col_header_right = st.columns([3, 1])
with col_header_left:
    st.title("GDTF BUILDER")
    st.markdown(
        "<p style='color:#BBBBBB;font-size:0.75rem;margin-top:-0.8rem;"
        "font-family:Share Tech Mono,monospace;letter-spacing:0.1em'>"
        "GDTF 1.1 &nbsp;·&nbsp; MA3 CHANNEL SETS &amp; WHEELS &nbsp;·&nbsp; "
        "VECTORWORKS &nbsp;·&nbsp; CAPTURE &nbsp;·&nbsp; ONYX</p>",
        unsafe_allow_html=True
    )
with col_header_right:
    st.markdown('<div style="margin-top: 1.5rem;">', unsafe_allow_html=True)
    st.image("NCET_white_with_strip.png", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
st.divider()

# ── Fixture metadata ──────────────────────────────────────────────────────────
st.markdown(
    "<p style='color:#BBBBBB;font-family:Share Tech Mono,monospace;"
    "font-size:0.72rem;letter-spacing:0.1em;margin-bottom:0.2rem'>"
    "FIXTURE INFO</p>",
    unsafe_allow_html=True
)
fi1, fi2 = st.columns(2)
with fi1:
    fixture_name = st.text_input(
        "MODEL NAME",
        value=st.session_state.get("fixture_name", "Generic LED Par")
    )
    st.session_state["fixture_name"] = fixture_name
with fi2:
    manufacturer = st.text_input(
        "MANUFACTURER",
        value=st.session_state.get("manufacturer", "Generic")
    )
    st.session_state["manufacturer"] = manufacturer

st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE INIT
# ══════════════════════════════════════════════════════════════════════════════

if "modes" not in st.session_state:
    st.session_state.modes = [{
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
    }]

def add_mode():
    st.session_state.modes.append({
        "name": f"Mode {len(st.session_state.modes)+1}",
        "channel_list": [make_channel_entry("Dimmer")]
    })

def copy_mode(i):
    src   = st.session_state.modes[i]
    clone = copy.deepcopy(src)
    # Give each cloned channel a fresh ID so widget keys don't clash
    for ch in clone["channel_list"]:
        ch["id"] = _new_channel_id()
    clone["name"] = src["name"] + " (Copy)"
    st.session_state.modes.insert(i + 1, clone)

def remove_mode(i):
    if len(st.session_state.modes) > 1:
        st.session_state.modes.pop(i)


# ══════════════════════════════════════════════════════════════════════════════
#  PER-MODE RENDERING
# ══════════════════════════════════════════════════════════════════════════════

for mode_idx, mode in enumerate(st.session_state.modes):

    # Backwards compat — plain string format from older versions
    if "channel_list" not in mode:
        old = mode.get("channels", "")
        mode["channel_list"] = [
            make_channel_entry(l.strip(), is_fine(l))
            for l in old.split("\n") if l.strip()
        ]

    # Ensure every channel has a stable ID
    for ch in mode["channel_list"]:
        if "id" not in ch:
            ch["id"] = _new_channel_id()

    ch_list = mode["channel_list"]

    st.markdown('<div class="card">', unsafe_allow_html=True)

    # ── Mode header ───────────────────────────────────────────────────────────
    hc1, hc2, hc3, hc4 = st.columns([3, 1, 1, 1])
    with hc1:
        mode["name"] = st.text_input(
            "MODE NAME", value=mode["name"],
            key=f"mname_{mode_idx}"
        )
    with hc2:
        st.write(""); st.write("")
        if st.button("⧉ Copy", key=f"copy_{mode_idx}",
                     help="Duplicate this mode"):
            copy_mode(mode_idx)
            st.rerun()
    with hc3:
        st.write(""); st.write("")
        st.markdown(
            f'<p style="color:var(--ma-amber);font-family:Share Tech Mono,'
            f'monospace;font-size:0.82rem;margin-top:0.55rem">'
            f'{len(ch_list)} CH</p>',
            unsafe_allow_html=True
        )
    with hc4:
        st.write(""); st.write("")
        if st.button("🗑", key=f"rm_{mode_idx}",
                     disabled=len(st.session_state.modes) == 1,
                     help="Remove mode"):
            remove_mode(mode_idx)
            st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    #  CHANNEL LIST  (collapsible, starts expanded)
    # ══════════════════════════════════════════════════════════════════════════
    n_ch = len(ch_list)
    ch_label = (
        f"CHANNEL LIST — {n_ch} CH — DMX ORDER"
        if n_ch > 0 else
        "CHANNEL LIST — empty — add channels below"
    )

    ch_to_delete = None
    ch_to_move   = None

    with st.expander(ch_label, expanded=True):

        if not ch_list:
            st.markdown(
                '<p style="color:#AAAAAA;font-size:0.85rem;padding:0.5rem 0">' +
                'No channels yet — use the picker below to add channels.</p>',
                unsafe_allow_html=True
            )

        for ci, ch in enumerate(ch_list):
            ch_id = ch["id"]
            attr, *_ = resolve_attr(ch["name"])
            known = any(k in ch["name"].lower() for k in ATTR_MAP)
            fine  = ch.get("is_fine", False)

            badge = (
                '<span class="badge b-fine">FINE</span>'
                if fine else
                f'<span class="badge {"b-ok" if known else "b-unk"}">{attr}</span>'
            )

            # ── Channel row: number | name | badge | ▲ | ▼ | ✕ ──────────────────
            # Use stable ch_id in widget key so moves don't corrupt input values
            r1, r2, r3, r4, r5, r6 = st.columns([0.4, 2.5, 1.2, 0.35, 0.35, 0.35])

            with r1:
                st.markdown(
                    f'<p class="ch-num">{ci+1}</p>',
                    unsafe_allow_html=True
                )
            with r2:
                # Key uses stable channel ID — so after a swap the widget
                # renders with the correct stored name, not the old position's value
                new_name = st.text_input(
                    "ch", value=ch["name"],
                    label_visibility="collapsed",
                    key=f"chname_{ch_id}"
                )
                if new_name != ch["name"]:
                    ch["name"] = new_name
            with r3:
                st.markdown(
                    f'<div style="margin-top:0.5rem">{badge}</div>',
                    unsafe_allow_html=True
                )
            with r4:
                if st.button("▲", key=f"up_{ch_id}",
                             disabled=ci == 0, help="Move up"):
                    ch_to_move = (ci, -1)
            with r5:
                if st.button("▼", key=f"dn_{ch_id}",
                             disabled=ci == len(ch_list)-1,
                             help="Move down"):
                    ch_to_move = (ci, 1)
            with r6:
                if st.button("✕", key=f"del_{ch_id}",
                             help="Remove channel"):
                    ch_to_delete = ci

            # ── DMX Slot / Channel Set Editor ────────────────────────────────────
            show_slots = (
                not fine and
                ch["name"] not in CONTINUOUS and
                known
            )

            if show_slots:
                slots = ch.setdefault("slots", [])
                n     = len(slots)
                label = (
                    f"  ↳ {n} channel set{'s' if n != 1 else ''} "
                    f"(MA3 snap positions) — tap to edit"
                    if n > 0 else
                    "  ↳ No channel sets — tap to add (optional)"
                )
                with st.expander(label, expanded=n > 0):
                    # Column headers
                    if slots:
                        hh1, hh2, hh3, hh4 = st.columns([1,1,2,0.4])
                        with hh1:
                            st.markdown(
                                '<p style="color:#888;font-size:0.68rem;'
                                'font-family:Share Tech Mono,monospace;'
                                'text-transform:uppercase;letter-spacing:0.06em;'
                                'margin-bottom:0.2rem">FROM</p>',
                                unsafe_allow_html=True
                            )
                        with hh2:
                            st.markdown(
                                '<p style="color:#888;font-size:0.68rem;'
                                'font-family:Share Tech Mono,monospace;'
                                'text-transform:uppercase;letter-spacing:0.06em;'
                                'margin-bottom:0.2rem">TO</p>',
                                unsafe_allow_html=True
                            )
                        with hh3:
                            st.markdown(
                                '<p style="color:#888;font-size:0.68rem;'
                                'font-family:Share Tech Mono,monospace;'
                                'text-transform:uppercase;letter-spacing:0.06em;'
                                'margin-bottom:0.2rem">LABEL (MA3 CHANNEL SET NAME)</p>',
                                unsafe_allow_html=True
                            )

                    slot_to_delete = None
                    for si, slot in enumerate(slots):
                        sc1, sc2, sc3, sc4 = st.columns([1,1,2,0.4])
                        with sc1:
                            slot["dmx_from"] = st.number_input(
                                "From", min_value=0, max_value=255,
                                value=int(slot["dmx_from"]),
                                key=f"sf_{ch_id}_{si}",
                                label_visibility="collapsed"
                            )
                        with sc2:
                            slot["dmx_to"] = st.number_input(
                                "To", min_value=0, max_value=255,
                                value=int(slot["dmx_to"]),
                                key=f"st_{ch_id}_{si}",
                                label_visibility="collapsed"
                            )
                        with sc3:
                            slot["name"] = st.text_input(
                                "Label", value=slot["name"],
                                placeholder="e.g. Open / Gobo 3 / Slow CW",
                                key=f"sn_{ch_id}_{si}",
                                label_visibility="collapsed"
                            )
                        with sc4:
                            if st.button("✕", key=f"sdel_{ch_id}_{si}"):
                                slot_to_delete = si

                    if slot_to_delete is not None:
                        slots.pop(slot_to_delete)
                        st.rerun()

                    # Add slot button with auto-suggested next value
                    next_from = slots[-1]["dmx_to"] + 1 if slots else 0
                    next_to   = min(next_from + 10, 255)
                    if st.button(
                        f"＋ Add channel set  (next: {next_from} – {next_to})",
                        key=f"sadd_{ch_id}",
                        use_container_width=True
                    ):
                        slots.append(make_slot_entry(next_from, next_to, ""))
                        st.rerun()

                    # Quick-fill preset
                    preset_match = next(
                        (v for k, v in PRESETS.items()
                         if k.lower() in ch["name"].lower()), None
                    )
                    if preset_match and not slots:
                        if st.button(
                            "⚡ Quick-fill standard channel sets",
                            key=f"preset_{ch_id}",
                            use_container_width=True
                        ):
                            for pf, pt, pn in preset_match:
                                slots.append(make_slot_entry(pf, pt, pn))
                            st.rerun()

                    if slots:
                        st.markdown(
                            '<p style="color:#777;font-size:0.72rem;'
                            'font-family:Share Tech Mono,monospace;margin-top:0.4rem">'
                            '⟶ These will appear as named snap positions on MA3 '
                            'encoders and in the fixture sheet channel sets column.</p>',
                            unsafe_allow_html=True
                        )

    # Apply moves and deletes after full render to avoid index confusion
    if ch_to_delete is not None:
        ch_list.pop(ch_to_delete)
        st.rerun()
    if ch_to_move is not None:
        i, d = ch_to_move
        j = i + d
        if 0 <= j < len(ch_list):
            ch_list[i], ch_list[j] = ch_list[j], ch_list[i]
        st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    #  CHANNEL PICKER  (below list, collapsible)
    # ══════════════════════════════════════════════════════════════════════════
    with st.expander("＋ ADD CHANNELS — tap a group to browse"):
        for group_name, group_channels in CHANNEL_CATALOGUE.items():
            with st.expander(group_name):
                # 2 columns on wide screens, readable on mobile
                gcols = st.columns(2)
                for ci2, (ch_name, ch_fine) in enumerate(group_channels):
                    with gcols[ci2 % 2]:
                        already = any(
                            c["name"].lower() == ch_name.lower()
                            for c in ch_list
                        )
                        label = f"✓ {ch_name}" if already else f"＋ {ch_name}"
                        if st.button(
                            label,
                            key=f"pick_{mode_idx}_{group_name}_{ch_name}",
                            use_container_width=True
                        ):
                            if not already:
                                ch_list.append(
                                    make_channel_entry(ch_name, ch_fine)
                                )
                                st.rerun()

        # Custom channel
        st.markdown(
            '<p style="color:#BBBBBB;font-family:Share Tech Mono,monospace;'
            'font-size:0.72rem;letter-spacing:0.08em;margin:0.8rem 0 0.3rem">'
            'CUSTOM CHANNEL NAME</p>',
            unsafe_allow_html=True
        )
        cc1, cc2 = st.columns([4, 1])
        with cc1:
            custom_name = st.text_input(
                "Custom", label_visibility="collapsed",
                placeholder="e.g. Pixel Row 1 / Virtual Dimmer",
                key=f"custom_name_{mode_idx}"
            )
        with cc2:
            if st.button("ADD", key=f"custom_add_{mode_idx}",
                         use_container_width=True):
                if custom_name.strip():
                    ch_list.append(
                        make_channel_entry(custom_name.strip(),
                                           is_fine(custom_name))
                    )
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)  # end .card


# ── Add Mode ──────────────────────────────────────────────────────────────────
st.button("＋ Add Mode", on_click=add_mode)
st.divider()


# ══════════════════════════════════════════════════════════════════════════════
#  GENERATE
# ══════════════════════════════════════════════════════════════════════════════

if st.button("⚡ Generate .gdtf File", type="primary", key="gen_manual"):
    fname = st.session_state.get("fixture_name", "").strip() or "Unknown Fixture"
    mfr   = st.session_state.get("manufacturer", "").strip() or "Generic"
    modes_dict = {
        m["name"]: channel_defs_from_mode(m)
        for m in st.session_state.modes
        if m["name"].strip()
    }
    try:
        xml_data   = build_gdtf(fname, mfr, modes_dict)
        gdtf_bytes = create_gdtf_package(xml_data)
        total_ch   = sum(len(v) for v in modes_dict.values())
        total_sets = sum(
            len(ch.get("slots", []))
            for m in st.session_state.modes
            for ch in m.get("channel_list", [])
        )
        st.success(
            f"✅  {total_ch} channels · {total_sets} channel sets · "
            f"{len(modes_dict)} mode(s) · {len(gdtf_bytes):,} bytes"
        )
        col_dl, col_xp = st.columns([1, 2])
        with col_dl:
            st.download_button(
                "📦 Download .gdtf", gdtf_bytes,
                file_name=f"{fname.replace(' ','_')}.gdtf",
                mime="application/octet-stream"
            )
            st.markdown("""
            <div class="info-box" style="margin-top:0.8rem;font-size:0.78rem">
            <b>MA3 onPC — place file at:</b><br>
            <code style="font-size:0.7rem">Documents\\MA Lighting Technologies\\grandMA3\\gma3_library\\fixturetypes\\</code><br><br>
            Then: <b>Menu → Patch → Fixture Types → Import → User tab</b>
            </div>
            """, unsafe_allow_html=True)
        with col_xp:
            with st.expander("View description.xml"):
                st.code(xml_data, language="xml")
    except Exception as e:
        st.exception(e)


# ── Attribute reference ───────────────────────────────────────────────────────
st.divider()
with st.expander("📖 Supported Channel Names"):
    cols = st.columns(3)
    items = list(ATTR_MAP.items())
    chunk = len(items) // 3 + 1
    for i, col in enumerate(cols):
        with col:
            for raw, (attr, *_) in items[i*chunk:(i+1)*chunk]:
                st.markdown(
                    f'<span class="badge b-ok">{raw}</span>'
                    f'<span style="color:#999;font-size:0.7rem"> → {attr}</span>',
                    unsafe_allow_html=True
                )
