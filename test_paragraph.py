import tkinter as tk
from tkinter import filedialog
import re
from typing import List, Callable, Tuple

# --- Configuration ---
THRESHOLD = 1000  # maximum characters per paragraph before splitting

# --- Consolidated Patent Regex Definitions (New Structure) ---

# 1. Define the core patent ID matching logic ONCE
# This constant contains the OR-separated groups for all patent formats (WO, EP, US)
PATENT_ID_REGEX = r'''
    (WO\s?\d{2,4}\/\d+[A-Z0-9]{1,2}?)   # WO patents (Group 3 in PATENT_SPLIT_PATTERN)
    |
    (EP\s?\d+[\s-]?\d+[\s-]?\d+[A-Z0-9]{1,2}?) # EP patents (Group 4)
    |
    (US\s?\d{2}\/\d+)                   # Old US format (Group 5)
    |
    (US[\s-]?[A-Z]{0,2}\s?\d{4}[-\/]?\d+) # New US format (Group 6)
''' 

# 2. Build the Global SPLIT Pattern using the core ID
# Used for: a) Splitting, b) Substitution of internal patent numbers (relies on Group 1)
PATENT_SPLIT_PATTERN = re.compile(
    r'([,;.\s])' +                           # Group 1: The separator
    r'(' + PATENT_ID_REGEX + r')',           # Group 2: The entire patent ID block
    re.IGNORECASE | re.VERBOSE) 

# 3. Build the START-OF-STRING Pattern using the core ID
# Used for: Substitution of patent numbers that start a string (no Group 1 separator)
PATENT_ONLY_START_PATTERN = re.compile(
    r'^\s*(' + PATENT_ID_REGEX + r')',       # Group 1: The entire patent ID block (at string start)
    re.IGNORECASE | re.VERBOSE)

# List of all available split functions, ordered by preference.
SPLIT_METHODS: List[Callable[[str], List[str]]] = []

def remove_tags(text):
    """Remove all XML/HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)

# ----------------------------------------------------------------------
# --- Utility for Patent Replacement (Updated to use new constants) ---

def substitute_patent_numbers(text: str) -> str:
    """
    Replaces all patent numbers in a string with 'PATENT'. Handles both 
    mid-string (with separator) and start-of-string cases.
    """
    global PATENT_SPLIT_PATTERN
    global PATENT_ONLY_START_PATTERN
    
    # 1. Handle patent numbers preceded by a separator (Group 1: [,;.\s])
    # Keeps Group 1 (the separator) and replaces Group 2 (the patent ID) with 'PATENT'.
    SUBSTITUTION_STRING = r'\g<1>PATENT'
    modified_text = PATENT_SPLIT_PATTERN.sub(SUBSTITUTION_STRING, text)

    # 2. Handle patent numbers that START the string (no leading separator)
    # Replaces the entire match (Group 1: patent ID) at the start of the string with 'PATENT'.
    final_text = PATENT_ONLY_START_PATTERN.sub('PATENT', modified_text).strip()
    
    return final_text

# ----------------------------------------------------------------------
# --- Split Functions ---

def split_paragraph_on_dot_double_newline(text: str) -> List[str]:
    """
    Primary split: split on dot followed by two or more newlines (paragraph break)
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_parts = re.split(r'\.\n{2,}', normalized)  # dot + 2+ newlines
    parts = []
    for p in raw_parts:
        p = p.strip()
        if not p:
            continue
        if not p.endswith('.') and not p.endswith('?') and not p.endswith('!'):
            p += '.'
        parts.append(p)
    return parts

def split_paragraph_on_patent_number(text: str) -> List[str]:
    """
    Splits the text immediately before a patent number (WO/EP/US).
    NOTE: Substitution is handled separately in process_paragraphs.
    """
    global PATENT_SPLIT_PATTERN

    parts = []
    last_index = 0
    
    # --- STEP 1: Structural Split ---
    for m in PATENT_SPLIT_PATTERN.finditer(text):
        
        # m.start(1) is the start of the separator (Group 1: [,;.\s])
        split_index = m.start(1) 
        
        # Append the text BEFORE the separator/patent
        part_before = text[last_index:split_index].strip()
        if part_before: 
            parts.append(part_before)
        
        # Start the next part from the separator (Group 1)
        last_index = split_index 
        
    # Append the final remaining text
    remainder = text[last_index:].strip()
    if remainder:
        parts.append(remainder)
        
    # Check for success (a split must result in more than one part)
    if len(parts) > 1:
        return [p for p in parts if p]
        
    return [text]

SPLIT_METHODS.append(split_paragraph_on_patent_number)

def split_paragraph_on_punctuation_dash(text: str) -> List[str]:
    """Secondary split: punctuation (. , : ;) followed by newline + dash"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    pattern = r'([.,:;])\n(-)'
    parts = []
    last_index = 0
    for m in re.finditer(pattern, normalized):
        split_index = m.start(1) + 1
        parts.append(normalized[last_index:split_index].strip())
        last_index = m.start(2)
    remainder = normalized[last_index:].strip()
    if remainder:
        parts.append(remainder)
    return parts

SPLIT_METHODS.append(split_paragraph_on_punctuation_dash)

def split_paragraph_on_arrow(text: str) -> List[str]:
    """Tertiary/fallback split: split on ' -->'"""
    parts = []
    last_index = 0
    pattern = r'(\s-->\s?)' 
    for m in re.finditer(pattern, text):
        split_index = m.start() 
        parts.append(text[last_index:split_index].strip())
        last_index = m.end() 
    remainder = text[last_index:].strip()
    if remainder:
        parts.append(remainder)
    return parts

SPLIT_METHODS.append(split_paragraph_on_arrow)

def split_paragraph_on_z_b(text: str) -> List[str]:
    """Quaternary/fallback split: split on ' z. B. '"""
    parts = []
    last_index = 0
    pattern = r' z\. B\. '
    for m in re.finditer(pattern, text):
        split_index = m.start() + 1
        parts.append(text[last_index:split_index].strip())
        last_index = m.start() + 1
    remainder = text[last_index:].strip()
    if remainder:
        parts.append(remainder)
    return parts

SPLIT_METHODS.append(split_paragraph_on_z_b)

def split_paragraph_on_or_newline_dash(text: str) -> List[str]:
    """Split: space + 'or' + newline + dash + space"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    pattern = r'(\sor)(\n-\s)'
    parts = []
    last_index = 0
    for m in re.finditer(pattern, normalized):
        split_index = m.end(1)
        parts.append(normalized[last_index:split_index].strip())
        last_index = m.start(2)
    remainder = normalized[last_index:].strip()
    if remainder:
        parts.append(remainder)
    return parts

SPLIT_METHODS.append(split_paragraph_on_or_newline_dash)


def split_paragraph_on_punctuation_list_item(text: str) -> List[str]:
    """Split: punctuation + newline + 1-2 digits + optional bracket/dot"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    pattern = r'([.,:;])\n(\(?[0-9]{1,2}\)?\.?)'
    parts = []
    last_index = 0
    for m in re.finditer(pattern, normalized):
        split_index = m.start(1) + 1
        parts.append(normalized[last_index:split_index].strip())
        last_index = m.start(2)
    remainder = normalized[last_index:].strip()
    if remainder:
        parts.append(remainder)
    return parts

SPLIT_METHODS.append(split_paragraph_on_punctuation_list_item)


def split_paragraph_on_punctuation_letter_bracket(text: str) -> List[str]:
    """Split: punctuation + newline + letter + ')'"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    pattern = r'([.,:;])\n+([a-zA-Z]\))'
    parts = []
    last_index = 0
    for m in re.finditer(pattern, normalized):
        split_index = m.start(1) + 1
        parts.append(normalized[last_index:split_index].strip())
        last_index = m.start(2)
    remainder = normalized[last_index:].strip()
    if remainder:
        parts.append(remainder)
    return parts

SPLIT_METHODS.append(split_paragraph_on_punctuation_letter_bracket)


def split_paragraph_on_figure_enumeration(text: str) -> List[str]:
    """Split: punctuation + optional newline + 'Fig', 'FIG', or 'FIGURE' + number"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    pattern = r'([.,:;])\n*((FIG|FIGURE|Fig)\.?\s[0-9]{1,3})' 
    parts = []
    last_index = 0
    for m in re.finditer(pattern, normalized):
        split_index = m.start(1) + 1
        parts.append(normalized[last_index:split_index].strip())
        last_index = m.start(2)
    remainder = normalized[last_index:].strip()
    if remainder:
        parts.append(remainder)
    return parts

SPLIT_METHODS.append(split_paragraph_on_figure_enumeration)

# ----------------------------------------------------------------------
# --- Core Recursive Logic ---

def recursively_split_long_part(part: str, split_methods: List[Callable[[str], List[str]]]) -> Tuple[List[str], bool]:
    """
    Recursively applies fallback split methods to a text part until its length 
    is below THRESHOLD or all methods fail.
    """
    if len(part) <= THRESHOLD:
        return [part], False

    for split_func in split_methods:
        sub_parts = split_func(part)

        if len(sub_parts) > 1:
            final_parts = []
            successful_split = True
            
            for sub_part in sub_parts:
                recursed_parts, _ = recursively_split_long_part(sub_part, split_methods)
                final_parts.extend(recursed_parts)
                
            return final_parts, successful_split

    return [part], False


def process_paragraphs(file_path):
    """Read XML, extract paragraphs, clean, attempt split, and print results/errors."""
    with open(file_path, "r", encoding="utf-8") as f:
        xml_text = f.read()

    paragraph_matches = re.findall(r'<p[^>]*num="([^"]+)"[^>]*>(.*?)</p>', xml_text, flags=re.DOTALL)

    for num, para in paragraph_matches:
        clean_text = remove_tags(para).strip()
        length = len(clean_text)
        
        # If the whole paragraph is already short enough, skip
        if length <= THRESHOLD:
            # Clean patents and skip printing if short
            # final_part = substitute_patent_numbers(clean_text)
            # print(f"--- paragraph {num}.1 ---")
            # print(final_part)
            # print()
            continue

        # --- Initial Splitting Strategy (for long paragraphs) ---
        
        # 1️⃣ Primary split: dot + double newline
        parts = split_paragraph_on_dot_double_newline(clean_text)
        
        # 2️⃣ Secondary/Recursive check: 
        final_parts = []
        was_split = len(parts) > 1 

        for part in parts:
            # The recursive function applies all methods in SPLIT_METHODS
            recursed_parts, part_was_split = recursively_split_long_part(part, SPLIT_METHODS)
            final_parts.extend(recursed_parts)
            if part_was_split:
                was_split = True
        
        # 3️⃣ If primary split failed, apply recursive fallbacks to the whole text
        if not was_split and len(final_parts) <= 1:
            final_parts, was_split = recursively_split_long_part(clean_text, SPLIT_METHODS)
            
        # --- End of Splitting Logic ---

        # If splitting still did not produce multiple parts and it's too long -> error
        if len(final_parts) <= 1 and length > THRESHOLD:
            print(f"ERROR: paragraph {num} could not be split (length: {length})")
            print("--- Paragraph content for inspection ---")
            print(clean_text)
            print("----------------------------------------\n")
            continue

        # Check if the final resulting parts are all below the threshold
        still_too_long = [p for p in final_parts if len(p) > THRESHOLD]
        if still_too_long:
            print(f"WARNING: paragraph {num} split, but {len(still_too_long)} parts remain > {THRESHOLD} chars.")
            
        # We have multiple parts — print summary and each part
        lengths = [len(p) for p in final_parts]
        print(f"paragraph {num} lengths : {', '.join(map(str, lengths))}")
        for j, part in enumerate(final_parts, start=1):
            
            # 🌟 FINAL STEP: Apply the patent substitution before printing
            cleaned_part = substitute_patent_numbers(part)
            
            print(f"--- paragraph {num}.{j} ---")
            print(cleaned_part)
            print()


def main():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select XML file",
        filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
    )

    if not file_path:
        print("No file selected.")
        return

    process_paragraphs(file_path)


if __name__ == "__main__":
    main()