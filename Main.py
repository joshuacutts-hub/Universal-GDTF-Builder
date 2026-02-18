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

# --- CONFIGURATION ---
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

def smart_clean_text(text):
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    cleaned_lines = []
    for line in lines:
        line = re.sub(r'\d{1,3}\s*-\s*\d{1,3}%?', '', line)
        line = re.sub(r'^\d+[\s.]+', '', line)
        name = re.sub(r'[^a-zA-Z\s/]', '', line).strip()
        if len(name) > 2 and name.lower() not in ["page", "manual", "dmx", "function", "value"]:
            if name.title() not in cleaned_lines:
                cleaned_lines.append(name.title())
    return cleaned_lines

# --- MULTI-MODE GDTF ENGINE ---
def build_multi_mode_gdtf(fixture_name, modes_dict, img_bytes=None):
    unique_id = str(uuid.uuid4())
    root = ET.Element("GDTF", DataVersion="1.0")
    ft = ET.SubElement(root, "FixtureType", Name=fixture_name, ShortName=fixture_name[:6].upper(), FixtureTypeID=unique_id)
    if img_bytes: ft.set("Thumbnail", "thumbnail.png")
    
    attr_defs = ET.SubElement(ft, "AttributeDefinitions")
    feat_groups = ET.SubElement(attr_defs, "FeatureGroups")
    feat_grp = ET.SubElement(feat_groups, "FeatureGroup", Name="Control")
    ET.SubElement(feat_grp, "Feature", Name="Control")
    
    attr_xml = ET.SubElement(attr_defs, "Attributes")
    all_channels = []
    for m_channels in modes_dict.values():
        all_channels.extend(m_channels)
    
    unique_attrs = {get_std_attr(ch) for ch in all_channels if not any(x in str(ch).lower() for x in ["fine", "lsb"])}
    for a in unique_attrs:
        ET.SubElement(attr_xml, "Attribute", Name=a, Feature="Control.Control")

    geoms = ET.SubElement(ft, "Geometries")
    ET.SubElement(geoms, "Geometry", Name="Base")
    
    dmx_modes_root = ET.SubElement(ft, "DMXModes")
    for mode_name, channels in modes_dict.items():
        mode = ET.SubElement(dmx_modes_root, "DMXMode", Name=mode_name, Geometry="Base")
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

# --- UI ---
st.set_page_config(page_title="Multi-Mode GDTF Pro", layout="wide")
st.title("📦 Multi-Mode GDTF Builder")

if 'modes' not in st.session_state:
    st.session_state.modes = {"Standard": ["Dimmer", "Pan", "Pan Fine", "Tilt", "Tilt Fine"]}
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = "Standard"

with st.sidebar:
    st.header("1. Assets")
    pdf = st.file_uploader("Upload Manual", type=['pdf'])
    img_file = st.file_uploader("Thumbnail", type=['jpg', 'png'])
    img_data = None
    if img_file:
        img = Image.open(img_file)
        img.thumbnail((512, 512)); buf = io.BytesIO(); img.save(buf, format='PNG'); img_data = buf.getvalue()
        st.image(img)

# Mode Management UI
st.subheader("Mode Management")
m_col1, m_col2, m_col3 = st.columns([2, 1, 1])

with m_col1:
    mode_names = list(st.session_state.modes.keys())
    st.session_state.current_mode = st.selectbox("Select Mode to Edit", mode_names, index=mode_names.index(st.session_state.current_mode))

with m_col2:
    new_mode = st.text_input("New Mode Name", placeholder="e.g. Extended")
    if st.button("➕ Add New"):
        if new_mode and new_mode not in st.session_state.modes:
            st.session_state.modes[new_mode] = ["Dimmer"]
            st.rerun()

with m_col3:
    if st.button("👯 Clone Current"):
        clone_name = f"{st.session_state.current_mode} Copy"
        st.session_state.modes[clone_name] = list(st.session_state.modes[st.session_state.current_mode])
        st.rerun()

# Scraper Button
if pdf:
    if st.sidebar.button("✨ Scrape PDF into current Mode"):
        reader = PdfReader(pdf)
        text = "\n".join([p.extract_text() for p in reader.pages[:3]])
        st.session_state.modes[st.session_state.current_mode] = smart_clean_text(text)
        st.rerun()

st.divider()
c1, c2 = st.columns([1, 1])

with c1:
    st.write(f"### Editing: **{st.session_state.current_mode}**")
    f_name = st.text_input("Fixture Model Name", "Generic Wash")
    df = pd.DataFrame({"Channel Name": st.session_state.modes[st.session_state.current_mode]})
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"ed_{st.session_state.current_mode}")
    st.session_state.modes[st.session_state.current_mode] = edited_df["Channel Name"].tolist()

with c2:
    st.write("### DMX Patch Preview")
    rows = []
    off, last = 1, None
    for c in st.session_state.modes[st.session_state.current_mode]:
        if not c: continue
        if any(x in str(c).lower() for x in ["fine", "lsb"]):
            if last: 
                last["Bit"] = "16-bit"; last["Range"] = f"{last['CH']}-{off}"
                off += 1
            continue
        row = {"CH": off, "Range": str(off), "Name": c, "Bit": "8-bit"}
        rows.append(row); last = row; off += 1
    st.table(pd.DataFrame(rows))

# Build Button (The line that caused the error is fixed here)
if st.button("🚀 Build & Download GDTF", type="primary", use_container_width=True):
    xml = build_multi_mode_gdtf(f_name, st.session_state.modes, img_data)
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as z:
        z.writestr('description.xml', xml)
        if img_data: z.writestr('thumbnail.png', img_data)
    
    st.download_button(
        label="Download Now", 
        data=zip_buf.getvalue(), 
        file_name=f"{f_name.replace(' ', '_')}.gdtf", 
        mime="application/octet-stream"
    )