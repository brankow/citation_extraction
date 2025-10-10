import tkinter as tk
import re
from typing import Tuple, List
from tkinter import filedialog
import json
import xml.etree.ElementTree as ET


def format_schema(schema_dict):
    """
    Converts a Python dict schema to a pretty-printed JSON string for the LLM prompt.
    This function is a general utility for JSON formatting.
    """
    return json.dumps(schema_dict, indent=2)

def simplify_long_words(text: str, max_length: int = 20) -> str:
    """
    Replaces any single 'word' (non-whitespace sequence) longer than max_length 
    with the placeholder 'FORMULA'.
    """
    def replace_if_long(match):
        word = match.group(0)
        if len(word) > max_length:
            return "FORMULA"
        return word

    # Use re.sub with the callback function to process all words
    simplified_text = re.sub(r'\S+', replace_if_long, text)
    
    return simplified_text

def simplify_bio_numbers(text: str) -> str:
    """Replaces common biological number patterns with simple words to declutter LLM input."""
    
    # 1. Replace all SEQ ID NOs (e.g., SEQ ID NO: 148)
    text = re.sub(r'SEQ ID NO:\s*\d+', 'SEQUENCE_ID', text, flags=re.IGNORECASE)
    
    # 2. Replace all base-pair counts (e.g., 330-bp)
    text = re.sub(r'\b\d{1,4}-bp\b', 'BASEPAIR', text, flags=re.IGNORECASE)
    
    # 3. Replace positional ranges (e.g., positions 137 to 968)
    text = re.sub(r'positions \d+\s*to\s*\d+', 'POSITION_RANGE', text, flags=re.IGNORECASE)
    
    return text


def select_xml_file():
    """
    Opens a file dialog using tkinter to allow the user to select an XML file.
    This is a general utility for file selection.
    """

    root = tk.Tk()
    root.withdraw() 
    
    file_path = filedialog.askopenfilename(
        title="Select an XML Document",
        filetypes=(("XML files", "*.xml"), ("All files", "*.*"))
    )

    root.destroy()
    return file_path

def select_xml_folder():
    """
    Opens a file dialog using tkinter to allow the user to select a folder.
    """
    root = tk.Tk()
    root.withdraw()
    
    # Use askdirectory instead of askopenfilename
    folder_path = filedialog.askdirectory(
        title="Select a Folder Containing XML Documents"
    )

    root.destroy()
    return folder_path

def extract_paragraph_texts(p_element, xml_tags_regex):
    """
    Extracts the raw XML content and the plain text version from an XML element.
    """

    raw_content_with_tags = ""
    stripped_text = ""
    try:
        # Get full XML string of the inner content
        full_xml_string = ET.tostring(p_element, encoding='utf-8').decode('utf-8', errors='ignore')
        
        # Strip the outer <p> tag using ElementTree's representation
        start_index = full_xml_string.find('>') + 1
        end_index = full_xml_string.rfind('</p>')
        
        if start_index > 0 and end_index != -1 and end_index > start_index:
            raw_content_with_tags = full_xml_string[start_index:end_index]
        else:
            raw_content_with_tags = ""

        # Create the plain-text (stripped) version using the constants regex
        if xml_tags_regex is None:
            stripped_text = raw_content_with_tags.strip()
        else:
            stripped_text = xml_tags_regex.sub('', raw_content_with_tags).strip()
        
        return raw_content_with_tags, stripped_text

    except Exception as e:
        print(f"DEBUG: Error during text extraction: {e}")
        # Handle cases where ET.tostring might fail unexpectedly
        return "[Error extracting content or paragraph is malformed]", ""