# paragraph_splitter.py

import re
from typing import List, Callable, Tuple

# --- Configuration ---
THRESHOLD = 1000  # maximum characters per paragraph before splitting
# --- Consolidated Patent Regex Definitions ---

# 1. Define the core patent ID matching logic ONCE
PATENT_ID_REGEX = r'''
    (WO\s?\d{2,4}\/\d+[A-Z0-9]{1,2}?)   # WO patents
    |
    (EP\s?\d+[\s-]?\d+[\s-]?\d+[A-Z0-9]{1,2}?) # EP patents
    |
    (US\s?\d{2}\/\d+)                   # Old US format
    |
    (US[\s-]?[A-Z]{0,2}\s?\d{4}[-\/]?\d+) # New US format
''' 

# 2. Build the Global SPLIT Pattern (for splitting and mid-string substitution)
PATENT_SPLIT_PATTERN = re.compile(
    r'([,;.\s])' +                           # Group 1: The separator
    r'(' + PATENT_ID_REGEX + r')',           # Group 2: The entire patent ID block
    re.IGNORECASE | re.VERBOSE) 

# 3. Build the START-OF-STRING Pattern (for substitution at string start)
PATENT_ONLY_START_PATTERN = re.compile(
    r'^\s*(' + PATENT_ID_REGEX + r')',       # Group 1: The entire patent ID block (at string start)
    re.IGNORECASE | re.VERBOSE)

# List of all available split functions, ordered by preference.
SPLIT_METHODS: List[Callable[[str], List[str]]] = []
def remove_tags(text: str) -> str:
    """Remove all XML/HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)

def substitute_patent_numbers(text: str) -> str:
    """
    Replaces all patent numbers in a string with 'PATENT'. Handles both 
    mid-string (with separator) and start-of-string cases.
    """
    # 1. Handle patent numbers preceded by a separator
    SUBSTITUTION_STRING = r'\g<1>PATENT'
    modified_text = PATENT_SPLIT_PATTERN.sub(SUBSTITUTION_STRING, text)

    # 2. Handle patent numbers that START the string
    final_text = PATENT_ONLY_START_PATTERN.sub('PATENT', modified_text).strip()
    
    return final_text

# ----------------------------------------------------------------------
# --- Split Functions ---
def split_paragraph_on_dot_double_newline(text: str) -> List[str]:
    """Primary split: split on dot followed by two or more newlines (paragraph break)"""
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
    Splits the text immediately before a patent number (WO/US).
    The patent number itself starts the new part.
    """
    
    parts = []
    last_index = 0
    
    # Use the compiled pattern from above (assuming it's defined globally in this file)
    for m in PATENT_SPLIT_PATTERN.finditer(text):
        
        # m.start(1) is the start of the separator (Group 1: [,;.\s])
        # The split point should be immediately after the *previous* content ends,
        # and before the patent starts. 
        
        # We find the start of the separator:
        split_index = m.start(1) 
        
        # 1. Append the text BEFORE the separator/patent
        part_before = text[last_index:split_index].strip()
        if part_before:
            parts.append(part_before)
        
        # 2. The rest of the text starts with the separator and the patent number
        last_index = split_index # Start the next part from the separator
        
    # Append the final remaining text
    remainder = text[last_index:].strip()
    if remainder:
        parts.append(remainder)
        
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
    
    # We match the space, the arrows, and a possible trailing space
    pattern = r'(\s--\s?>\s*)'
    for m in re.finditer(pattern, text):
        # Split index is the start of the matched pattern (the leading space)
        split_index = m.start() 
        parts.append(text[last_index:split_index].strip())
        # The next part starts AFTER the entire matched pattern
        last_index = m.end() 
    
    remainder = text[last_index:].strip()
    if remainder:
        parts.append(remainder)
        
    if len(parts) > 1:
        return [p for p in parts if p]
        
    return [text]

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
    # Note the \n* to make the newline optional, addressing the previous issue.
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


# --- Core Recursive Logic ---

def recursively_split_long_part(part: str, split_methods: List[Callable[[str], List[str]]]) -> Tuple[List[str], bool]:
    """Recursively applies fallback split methods to a text part."""
    global THRESHOLD # Use the global threshold
    
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

def split_and_clean_paragraph(text: str) -> List[str]:
    """
    Main function to split a single raw paragraph string, recursively applying
    splitting rules, and performing final patent number substitution.
    
    Args:
        text (str): The raw paragraph string (assumed to be already stripped of XML tags).
        
    Returns:
        List[str]: A list of cleaned, split sub-paragraphs.
    """
    clean_text = text.strip()
    length = len(clean_text)
    
    # 1. Handle short paragraphs immediately (only apply cleaning/substitution)
    if length <= THRESHOLD:
        cleaned_part = substitute_patent_numbers(clean_text)
        return [cleaned_part]

    # 2. Primary split: dot + double newline
    parts = split_paragraph_on_dot_double_newline(clean_text)
    
    final_parts = []
    was_split = len(parts) > 1 

    # 3. Recursive check on primary parts
    for part in parts:
        recursed_parts, part_was_split = recursively_split_long_part(part, SPLIT_METHODS)
        final_parts.extend(recursed_parts)
        if part_was_split:
            was_split = True
    
    # 4. If primary split failed, apply recursive fallbacks to the whole text
    if not was_split and len(final_parts) <= 1:
        final_parts, was_split = recursively_split_long_part(clean_text, SPLIT_METHODS)
        
    # 5. Final cleaning and substitution
    # The splitting logic might produce a single, long part if all splitting failed.
    # We apply the substitution to ALL final parts.
    
    output_parts = []
    for part in final_parts:
        # Check if the part is still too long (an error condition to log elsewhere)
        if len(part) > THRESHOLD and not was_split:
             # If a single, long part remains and no splitting occurred, substitute and return
             cleaned_part = substitute_patent_numbers(part)
             return [f"ERROR: COULD NOT SPLIT (Length: {length}) - {cleaned_part}"] 
             
        cleaned_part = substitute_patent_numbers(part)
        output_parts.append(cleaned_part)
            
    return output_parts