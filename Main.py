import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile
import io
import re
import uuid
import pandas as pd
from PIL import Image
from pypdf import PdfReader

# --- 1. CONFIGURATION & MAPPING ---
ATTR_MAP = {
    "dimmer": "Dimmer", "pan": "Pan", "tilt": "Tilt",
    "red": "ColorAdd_R", "green": "ColorAdd_G", "blue": "ColorAdd_B",
    "white": "ColorAdd_W", "amber": "ColorAdd_A", "uv": "ColorAdd_UV",
    "strobe": "Shutter_Strobe_Random", "shutter": "Shutter_1",
    "zoom": "Zoom", "focus": "Focus", "iris": "Iris",
    "gobo": "Gobo_n_WheelSlot_1", "prism": "Prism_n_WheelSlot_1"
}

def get_std_attr(name):
    clean = name.lower().strip()
    for key, val in ATTR_MAP.items():
        if key in clean: return val
    return name.strip().capitalize()

# --- 2. LOGIC: CLEANING & PDF ---
def smart_clean_text(text):
    """Smarter filtering: removes DMX values and keeps channel names."""
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        # Remove DMX ranges (0-255) and leading digits
        line = re.sub(r'\b\d{1,3}-\d{1,3}\b', '', line)
        line = re.sub(r'^\d+', '', line)
        # Remove symbols
        name = re.sub(r'[^a-zA-Z\s]', '', line).strip()
        if len(name) > 2 and name.lower() not in ["page", "manual", "table"]:
            cleaned.append(name.title())
    return "\n".join(cleaned)

# --- 3. GDTF BUILDER (MA3 OPTIMIZED) ---
def build_gdtf(fixture_name, channels, img_bytes=None):
    # MA3 requires a unique FixtureTypeID to avoid conflicts
    unique_id = str(uuid.uuid4())
    root = ET.Element("GDTF", DataVersion="1.0")
    
    ft_attribs = {
        "Name": fixture_name, 
        "ShortName": fixture_name[:6].upper(),
        "FixtureTypeID": unique_id
    }
    if img_bytes: ft_attribs["Thumbnail"] = "thumbnail.png"
    
    ft = ET.SubElement(root, "FixtureType", **ft_attribs)
    
    # Attributes Definition
    attr_defs = ET.SubElement(ft, "AttributeDefinitions")
    feat_groups = ET.SubElement(attr_defs, "FeatureGroups")
    feat_grp = ET.SubElement(feat_groups, "FeatureGroup", Name="Control")
    ET.SubElement(feat_grp, "Feature", Name="Control")
    
    attr_xml = ET.SubElement(attr_defs, "Attributes")
    for ch in channels:
        if not any(x in ch.lower() for x in ["fine", "lsb"]):
            std = get_std_attr(ch)
            ET.SubElement(attr_xml, "Attribute", Name=std, Feature="Control.Control")

    # Geometry & DMX
    geoms = ET.SubElement(ft, "Geometries")
    ET.SubElement(geoms, "Geometry", Name="Base")
    
    modes = ET.SubElement(ft, "DMXModes")
    mode = ET.SubElement(modes, "DMXMode", Name="Standard", Geometry="Base")
    dmx_chs = ET.SubElement(mode, "DMXChannels")
    
    curr_offset = 1
    last_el = None
    for name in channels:
        is_fine = any(x in name.lower() for x in ["fine", "lsb", "16bit"])
        if is_fine and last_el is not None:
            start = last_el.get("Offset").split(',')[0]
            last_el.set("Offset", f"{start},{curr_offset}")
            curr_offset += 1
            continue
            
        std = get_std_attr(name)
        dmx_ch = ET.SubElement(dmx_chs, "DMXChannel", DMXBreak="1", Offset=str(curr_offset), Geometry="Base")
        log_ch = ET.SubElement(dmx_ch, "LogicalChannel", Attribute=std)
        ET.SubElement(log_ch, "ChannelFunction", Name=name, Attribute=std, DMXFrom="0/1")
        last_el = dmx_ch
        curr_offset += 1

    return minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")

# --- 4. STREAMLIT UI ---
st.set_page_config(page_title="GDTF Pro Builder", layout="wide")
st.title("📦 GDTF Pro: MA3 & Vectorworks Builder")

if 'channel_list' not in st.session_state:
    st.session_state.channel_list = ["Dimmer", "Pan", "Pan Fine", "Tilt", "Tilt Fine", "Red", "Green", "Blue"]

# Sidebar: PDF Scraper
with st.sidebar:
    st.header("1. Scrape Manual")
    pdf = st.file_uploader("Upload PDF", type=['pdf'])
    if pdf:
        reader = PdfReader(pdf)
        raw_text = "\n".join([p.extract_text() for p in reader.pages])
        if st.button("✨ Smart Clean & Import"):
            cleaned = smart_clean_text(raw_text)
            st.session_state.channel_list = cleaned.split('\n')
            st.success("Cleaned list imported!")

    st.header("2. Fixture Image")
    img_file = st.file_uploader("Upload Image", type=['jpg', 'png'])
    img_data = None
    if img_file:
        img = Image.open(img_file)
        img.thumbnail((512, 512))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_data = buf.getvalue()
        st.image(img)

# Main Area
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Edit Channel Order")
    fixture_name = st.text_input("Manufacturer & Model", "My New Fixture")
    
    # THE REORDER FEATURE: A list of text inputs
    new_channels = []
    for i, ch in enumerate(st.session_state.channel_list):
        new_ch = st.text_input(f"CH {i+1}", value=ch, key=f"ch_{i}")
        new_channels.append(new_ch)
    
    if st.button("➕ Add Channel"):
        st.session_state.channel_list.append("New Channel")
        st.rerun()

with col2:
    st.subheader("MA3 DMX Preview")
    # Build a quick table for the user to see the patch
    preview_data = []
    off = 1
    last = None
    for c in new_channels:
        if any(x in c.lower() for x in ["fine", "lsb"]):
            if last: 
                last["Res"] = "16-bit"
                last["Range"] = f"{last['Start']}-{off}"
                off += 1
            continue
        row = {"Start": off, "Name": c, "Attr": get_std_attr(c), "Res": "8-bit", "Range": str(off)}
        preview_data.append(row)
        last = row
        off += 1
    
    st.table(pd.DataFrame(preview_data)[["Start", "Range", "Name", "Res"]])

# Download Button
if st.button("🚀 Build MA3 Compatible GDTF", use_container_width=True, type="primary"):
    xml = build_gdtf(fixture_name, new_channels, img_data)
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as z:
        z.writestr('description.xml', xml)
        if img_data: z.writestr('thumbnail.png', img_data)
    
    st.download_button("Download .gdtf", zip_buf.getvalue(), f"{fixture_name}.gdtf", "application/octet-stream")