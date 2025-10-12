import re
from typing import List, Callable, Tuple

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

PATENT_FINDER_PATTERN = re.compile(
    PATENT_ID_REGEX,  # Just the IDs
    re.IGNORECASE | re.VERBOSE)


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
def split_paragraph_on_patent_number(text: str) -> List[str]:
    """
    Splits the text immediately BEFORE a patent reference and DISCARDS the patent
    reference and any preceding separator/whitespace from the resulting segments.
    """
    parts = []
    last_index = 0
    
    for m in PATENT_FINDER_PATTERN.finditer(text):
        
        # 1. Determine the split point: It should be before the patent ID
        # We search backward for the nearest meaningful separator (., ; or end of word)
        
        # Split point is the start of the patent match (m.start())
        split_index = m.start()
        
        # Get the part BEFORE the patent reference
        part_before = text[last_index:split_index].strip()
        
        # Only add the part if it contains actual content
        if part_before:
            parts.append(part_before)
        
        # 2. Update last_index to the END of the entire match (m.end()).
        # This is the critical step: it skips over the entire patent ID,
        # effectively consuming and discarding it from the rest of the processing.
        last_index = m.end() 
        
    remainder = text[last_index:].strip()
    if remainder:
        parts.append(remainder)
        
    # The split might have created just one part if the patent was the very first thing
    # or the only thing. We return the splits if multiple segments were created.
    # Note: We rely on the rest of the cascading split logic to handle parts cleanly.
        
    return [p for p in parts if p] if len(parts) > 1 else [text]

def split_paragraph_on_dot_double_newline(text: str) -> List[str]:
    """Primary split: split on dot followed by two or more newlines (paragraph break)"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_parts = re.split(r'\.\n{2,}', normalized)  # dot + 2+ newlines
    parts = []
    for p in raw_parts:
        p = p.strip()
        if not p:
            continue
        if not p.endswith(('.', '?', '!')):
            p += '.'
        parts.append(p)
    return parts



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
    return [p for p in parts if p] if len(parts) > 1 else [text]


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
        
    return [p for p in parts if p] if len(parts) > 1 else [text]


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
    return [p for p in parts if p] if len(parts) > 1 else [text]




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
    return [p for p in parts if p] if len(parts) > 1 else [text]


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
    return [p for p in parts if p] if len(parts) > 1 else [text]


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
    return [p for p in parts if p] if len(parts) > 1 else [text]


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
    return [p for p in parts if p] if len(parts) > 1 else [text]

# --- Ordered List of all Split Methods ---
FINAL_SPLIT_ORDER: List[Callable[[str], List[str]]] = [
    split_paragraph_on_patent_number,
    split_paragraph_on_dot_double_newline,
    split_paragraph_on_punctuation_dash,
    split_paragraph_on_figure_enumeration,
    split_paragraph_on_punctuation_list_item,
    split_paragraph_on_punctuation_letter_bracket,
    split_paragraph_on_or_newline_dash,
    split_paragraph_on_z_b,
    split_paragraph_on_arrow,
]
# ----------------------------------------------------------------------
# --- Core Unconditional Cascading Splitter ---

def cascading_split(part: str, split_methods: List[Callable[[str], List[str]]]) -> List[str]:
    """
    Applies split methods sequentially and recursively, UNCONDITIONALLY, 
    until all methods have been tried.
    """
    # Base case 1: Empty part
    if not part.strip():
        return []

    # Base case 2: No more split methods left
    if not split_methods:
        return [part]
    
    current_split_func = split_methods[0]
    remaining_split_methods = split_methods[1:]
    
    # 1. Attempt the current split
    sub_parts = current_split_func(part)

    # 2. If the split was successful (yielded more than 1 part)
    if len(sub_parts) > 1:
        final_parts = []
        # Recursively apply the *remaining* methods to the new sub-parts
        for sub_part in sub_parts:
            final_parts.extend(cascading_split(sub_part, remaining_split_methods))
        return final_parts
    else:
        # 3. If the current split failed, try the *next* method recursively on the original part.
        return cascading_split(part, remaining_split_methods)

# --- Main Exportable Splitter Function ---

def split_and_clean_paragraph(text: str) -> List[str]:
    """
    Main function to split a single raw paragraph string using all defined split methods 
    in a cascading and UNCONDITIONAL manner, and then clean patents.
    """
    if text is None:
        return []
    
    clean_text = text.strip()

    # Apply the cascading split using the final, ordered list of split methods
    final_parts = cascading_split(clean_text, FINAL_SPLIT_ORDER)

    # NEW STEP: Clean up any remaining patent numbers using your existing substitution logic
    final_parts_cleaned = [substitute_patent_numbers(p) for p in final_parts]

    # Filter out empty strings
    return [p for p in final_parts_cleaned if p.strip()]