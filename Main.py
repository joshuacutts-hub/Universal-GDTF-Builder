import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
import zipfile
import io
import re # Added for text cleaning
import pandas as pd
from PIL import Image
from pypdf import PdfReader

# --- Configuration & Mapping ---
ATTR_MAP = {
    "dimmer": "Dimmer", "pan": "Pan", "tilt": "Tilt",
    "red": "ColorAdd_R", "green": "ColorAdd_G", "blue": "ColorAdd_B",
    "white": "ColorAdd_W", "amber": "ColorAdd_A", "uv": "ColorAdd_UV",
    "strobe": "Shutter_Strobe_Random", "shutter": "Shutter_1",
    "zoom": "Zoom", "focus": "Focus", "iris": "Iris",
    "gobo": "Gobo_n_WheelSlot_1", "prism": "Prism_n_WheelSlot_1",
    "control": "Control_1", "macro": "Macro_1"
}

def get_std_attr(user_input):
    clean = user_input.lower().strip()
    for key, val in ATTR_MAP.items():
        if key in clean: return val
    return user_input.strip().capitalize()

def clean_dmx_text(raw_text):
    """Removes DMX values (0-255), percentages, and special characters."""
    lines = raw_text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Remove numbers (0-255), ranges (000-255), and symbols like %
        # We keep letters and spaces
        newline = re.sub(r'(\d{1,3}-\d{1,3})|(\d{1,3})|[%()\-:.]', '', line)
        newline = newline.strip()
        if len(newline) > 2: # Ignore tiny fragments
            cleaned_lines.append(newline)
    return "\n".join(cleaned_lines)

# --- Logic Functions ---
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def generate_preview_data(channels):
    data = []
    current_offset = 1
    last_entry = None
    for raw_name in channels:
        if not raw_name.strip(): continue
        name = raw_name.strip()
        is_fine = any(w in name.lower() for w in ["fine", "lsb", "16bit"])
        
        if is_fine and last_entry:
            last_entry["Resolution"] = "16-bit"
            last_entry["DMX Range"] = f"{last_entry['Start']} - {current_offset}"
            current_offset += 1
        else:
            entry = {"Start": current_offset, "Channel Name": name, 
                     "GDTF Attribute": get_std_attr(name), "Resolution": "8-bit", 
                     "DMX Range": str(current_offset)}
            data.append(entry)
            last_entry = entry
            current_offset += 1
    return data

def build_gdtf_xml(fixture_name, channels, has_thumbnail=False):
    root = ET.Element("GDTF", DataVersion="1.0")
    ft_attribs = {"Name": fixture_name, "ShortName": fixture_name[:6].upper(),
                  "Description": "AI Generated GDTF", "FixtureTypeID": "0000-0000-0000"}
    if has_thumbnail: ft_attribs["Thumbnail"] = "thumbnail.png"
    
    ft = ET.SubElement(root, "FixtureType", **ft_attribs)
    attr_defs = ET.SubElement(ft, "AttributeDefinitions")
    ET.SubElement(attr_defs, "ActivationGroups")
    ET.SubElement(attr_defs, "FeatureGroups")
    attributes_xml = ET.SubElement(attr_defs, "Attributes")
    
    unique_attrs = {get_std_attr(c) for c in channels if not any(x in c.lower() for x in ["fine", "lsb"])}
    for a in unique_attrs:
        ET.SubElement(attributes_xml, "Attribute", Name=a, Feature="Control.Control")

    ET.SubElement(ft, "WheelDefinitions")
    geometries = ET.SubElement(ft, "Geometries")
    ET.SubElement(geometries, "Geometry", Name="Base")

    dmx_modes = ET.SubElement(ft, "DMXModes")
    dmx_mode = ET.SubElement(dmx_modes, "DMXMode", Name="Standard", Geometry="Base")
    dmx_channels = ET.SubElement(dmx_mode, "DMXChannels")
    
    last_ch_element = None
    current_offset = 1
    for raw_name in channels:
        if not raw_name.strip(): continue
        is_fine = any(w in raw_name.lower() for w in ["fine", "lsb", "16bit"])
        if is_fine and last_ch_element is not None:
            start_addr = int(last_ch_element.get("Offset").split(",")[0])
            last_ch_element.set("Offset", f"{start_addr},{current_offset}")
            current_offset += 1
            continue 
        
        std_attr = get_std_attr(raw_name)
        dmx_ch = ET.SubElement(dmx_channels, "DMXChannel", DMXBreak="1", Offset=str(current_offset), Geometry="Base")
        log_ch = ET.SubElement(dmx_ch, "LogicalChannel", Attribute=std_attr)
        ET.SubElement(log_ch, "ChannelFunction", Name=raw_name, Attribute=std_attr, DMXFrom="0/1")
        last_ch_element = dmx_ch
        current_offset += 1

    xml_str = ET.tostring(root, encoding='utf-8')
    return minidom.parseString(xml_str).toprettyxml(indent="  ")

# --- Streamlit UI ---
st.set_page_config(page_title="GDTF Pro Builder", layout="wide")
st.title("📦 GDTF Pro Builder")

# Sidebar
if 'cleaned_text' not in st.session_state:
    st.session_state.cleaned_text = "Dimmer\nRed\nGreen\nBlue\nPan\nPan Fine\nTilt\nTilt Fine"

with st.sidebar:
    st.header("Upload Assets")
    pdf_file = st.file_uploader("Step 1: Scrape PDF Manual", type=['pdf'])
    if pdf_file:
        raw_pdf_text = extract_text_from_pdf(pdf_file)
        if st.button("✨ Clean & Transfer Text"):
            st.session_state.cleaned_text = clean_dmx_text(raw_pdf_text)
            st.success("Cleaned list moved to main editor!")

    st.divider()
    img_file = st.file_uploader("Step 2: Fixture Image", type=['png', 'jpg'])
    img_bytes = None
    if img_file:
        img = Image.open(img_file)
        img.thumbnail((512, 512))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_bytes = buf.getvalue()
        st.image(img)

# Main Panel
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Fixture Definition")
    fixture_name = st.text_input("Manufacturer & Model", "Generic LED")
    dmx_input = st.text_area("DMX Map", value=st.session_state.cleaned_text, height=400)
    channel_list = [c.strip() for c in dmx_input.split('\n') if c.strip()]

with col2:
    st.subheader("DMX Preview")
    
    if channel_list:
        try:
            preview_data = generate_preview_data(channel_list)
            st.table(pd.DataFrame(preview_data)[["Start", "DMX Range", "Channel Name", "Resolution"]])
        except:
            st.warning("Enter channels to see preview.")

if st.button("Build & Download .gdtf", use_container_width=True, type="primary"):
    xml_content = build_gdtf_xml(fixture_name, channel_list, has_thumbnail=(img_bytes is not None))
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w') as z:
        z.writestr('description.xml', xml_content)
        if img_bytes:
            z.writestr('thumbnail.png', img_bytes)
    st.download_button("Download Now", zip_buf.getvalue(), f"{fixture_name}.gdtf", "application/octet-stream")