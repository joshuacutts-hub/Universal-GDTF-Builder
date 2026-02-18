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

# --- 1. CONFIGURATION ---
ATTR_MAP = {
    "dimmer": "Dimmer", "pan": "Pan", "tilt": "Tilt",
    "red": "ColorAdd_R", "green": "ColorAdd_G", "blue": "ColorAdd_B",
    "white": "ColorAdd_W", "amber": "ColorAdd_A", "uv": "ColorAdd_UV",
    "strobe": "Shutter_Strobe_Random", "shutter": "Shutter_1",
    "zoom": "Zoom", "focus": "Focus", "iris": "Iris",
    "gobo": "Gobo_n_WheelSlot_1", "prism": "Prism_n_WheelSlot_1"
}

def get_std_attr(name):
    clean = str(name).lower().strip()
    for key, val in ATTR_MAP.items():
        if key in clean: return val
    return str(name).strip().capitalize()

# --- 2. SURGICAL PDF CLEANER ---
def smart_clean_text(text):
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    cleaned_lines = []
    # Patterns to ignore: DMX ranges (0-255), lone numbers, and percentages
    dmx_val_pattern = r'^(\d{1,3})(\s*-\s*\d{1,3})?%?$'
    
    for line in lines:
        # Remove in-line DMX ranges
        line = re.sub(r'\d{1,3}\s*-\s*\d{1,3}%?', '', line)
        # Remove leading channel numbers (e.g., "1. Dimmer" -> "Dimmer")
        line = re.sub(r'^\d+[\s.]+', '', line)
        
        name = re.sub(r'[^a-zA-Z\s/]', '', line).strip()
        if len(name) > 2 and name.lower() not in ["page", "manual", "dmx", "function", "value"]:
            if name.title() not in cleaned_lines:
                cleaned_lines.append(name.title())
    return cleaned_lines

# --- 3. GDTF ENGINE ---
def build_gdtf(fixture_name, channels, img_bytes=None):
    unique_id = str(uuid.uuid4())
    root = ET.Element("GDTF", DataVersion="1.0")
    ft = ET.SubElement(root, "FixtureType", Name=fixture_name, ShortName=fixture_name[:6].upper(), FixtureTypeID=unique_id)
    if img_bytes: ft.set("Thumbnail", "thumbnail.png")
    
    attr_defs = ET.SubElement(ft, "AttributeDefinitions")
    feat_groups = ET.SubElement(attr_defs, "FeatureGroups")
    feat_grp = ET.SubElement(feat_groups, "FeatureGroup", Name="Control")
    ET.SubElement(feat_grp, "Feature", Name="Control")
    
    attr_xml = ET.SubElement(attr_defs, "Attributes")
    for ch in channels:
        if not any(x in str(ch).lower() for x in ["fine", "lsb"]):
            std = get_std_attr(ch)
            ET.SubElement(attr_xml, "Attribute", Name=std, Feature="Control.Control")

    geoms = ET.SubElement(ft, "Geometries")
    ET.SubElement(geoms, "Geometry", Name="Base")
    
    modes = ET.SubElement(ft, "DMXModes")
    mode = ET.SubElement(modes, "DMXMode", Name="Standard", Geometry="Base")
    dmx_chs = ET.SubElement(mode, "DMXChannels")
    
    curr_offset, last_el = 1, None
    for name in channels:
        name_str = str(name)
        is_fine = any(x in name_str.lower() for x in ["fine", "lsb", "16bit"])
        if is_fine and last_el is not None:
            start = last_el.get("Offset").split(',')[0]
            last_el.set("Offset", f"{start},{curr_offset}")
            curr_offset += 1
            continue
            
        std = get_std_attr(name_str)
        dmx_ch = ET.SubElement(dmx_chs, "DMXChannel", DMXBreak="1", Offset=str(curr_offset), Geometry="Base")
        log_ch = ET.SubElement(dmx_ch, "LogicalChannel", Attribute=std)
        ET.SubElement(log_ch, "ChannelFunction", Name=name_str, Attribute=std, DMXFrom="0/1")
        last_el, curr_offset = dmx_ch, curr_offset + 1

    return minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")

# --- 4. STREAMLIT UI ---
st.set_page_config(page_title="GDTF Builder Pro", layout="wide")
st.title("📦 Universal GDTF Builder (MA3 Optimized)")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame({"Channel Name": ["Dimmer", "Pan", "Pan Fine", "Tilt", "Tilt Fine", "Red", "Green", "Blue"]})

# Sidebar: PDF Scraper
with st.sidebar:
    st.header("1. PDF Scraper")
    pdf = st.file_uploader("Upload Manual", type=['pdf'])
    if pdf:
        reader = PdfReader(pdf)
        pages = st.slider("Select Pages", 1, len(reader.pages), (1, min(2, len(reader.pages))))
        if st.button("✨ Smart Clean & Import"):
            text = "\n".join([reader.pages[i].extract_text() for i in range(pages[0]-1, pages[1])])
            cleaned = smart_clean_text(text)
            st.session_state.df = pd.DataFrame({"Channel Name": cleaned})
            st.rerun()

    st.header("2. Fixture Image")
    img_file = st.file_uploader("Thumbnail (JPG/PNG)", type=['jpg', 'png'])
    img_data = None
    if img_file:
        img = Image.open(img_file)
        img.thumbnail((512, 512)); buf = io.BytesIO(); img.save(buf, format='PNG')
        img_data = buf.getvalue(); st.image(img)

# Main Area
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Edit Channel Map")
    fixture_name = st.text_input("Fixture Model Name", "My Awesome Light")
    
    # EASIER REORDERING: The Data Editor
    # You can click, type, and paste directly into this table.
    edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)
    st.caption("💡 **Tip:** To reorder, just copy-paste rows or edit names. Use the bottom row to add new ones.")

with col2:
    st.subheader("DMX Patch Preview")
    # Live logic to show the user what the DMX map looks like
    preview_rows = []
    off, last = 1, None
    for c in edited_df["Channel Name"]:
        if not c: continue
        if any(x in str(c).lower() for x in ["fine", "lsb"]):
            if last: 
                last["Bit"] = "16-bit"; last["Range"] = f"{last['CH']}-{off}"
                off += 1
            continue
        row = {"CH": off, "Range": str(off), "Name": c, "Attr": get_std_attr(c), "Bit": "8-bit"}
        preview_rows.append(row); last = row; off += 1
    
    st.table(pd.DataFrame(preview_rows))

# Download
if st.button("🚀 Build & Download GDTF", type="primary", use_container_width=True):
    channels = edited_df["Channel Name"].tolist()
    xml = build_gdtf(fixture_name, channels, img_data)
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as z:
        z.writestr('description.xml', xml)
        if img_data: z.writestr('thumbnail.png', img_data)
    
    st.download_button("Download Now", zip_buf.getvalue(), f"{fixture_name}.gdtf")