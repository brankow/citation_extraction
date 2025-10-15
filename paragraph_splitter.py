import re
from typing import List, Callable, Tuple

# --- Consolidated Patent Regex Definitions ---

# 1. Define the core patent ID matching logic ONCE
PATENT_ID_REGEX = r'''
    (WO\s?\d{2,4}\s?\/?\s?\d+\s?\d*\s?[A-Z0-9]{1,2}?)   # WO patents.   WO 2023 / 069 440 A1.  WO 2016 066651
    |
    (PCT\/[A-Z]{2}\d{2,4}\/\d{3,7})       # PCT/EP2025/056529
    |
    (EP\s?\d+[\s-]?\d+[\s-]?\d+[A-Z0-9]{1,2}?) # EP patents
    |
    (U\.?S\.?\s?\d{2}\/\d+(\s?[A-Z])?)                   # Old US application format. 13/123456 A
    |
    (U\.?S\.?\s?[0-9,]{7,}(\s?[A-Z]\d?)?)                   # Old US  format.  US 6,123,456 B2
    |
    (U\.?S\.?[\s-]?[A-Z]{0,2}\s?\d{4}\s?[-\/]?\s?[\d\s]+(\s?[A-Z]\d?)?) # New US format.  US 2020/1234567 A1
    |
    (JP[\s-]?[A-B]{0,1}\s?\d{4}[-\/]?\d+(\s?[A-Z]\d?)?) # New JP format
    |
    (JP[\s-]?[A-B]{0,1}\s?[HS]\d{1,2}[-\/]?\d+(\s?[A-Z]\d?)?) # Old JP format
    |
    (CN\d{6,}(\s?[A-Z]\d?)?)
    |
    \bDE\s?\d{2}\s?\d{4}\s?\d{3}\s?\d{3}(?:\.\d)?(?:\s?[A-Z]\d?)?\b                     # DE Number format. DE 10 2019 135 544 A1.  DE19629787A1
    |    
    \bDE\s?[\d\s]{7,}(?:\s?[A-Z]\d?)?\b                     # DE Number format DE19629787A1
    |
    (GB[\s-]?[A-Z]{0,1}\s?[0-9\-]{6,}(\s?[A-Z]\d?)?x)
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


# The pattern splits on: [., :, ;] + space + (For|As an) + space + example
# Breakdown of the pattern:
# r'([\.\:\;])'           : Group 1: Matches and captures one of the punctuation marks.
# r'(\s+)'               : Group 2: Matches and captures one or more spaces.
# r'((?:for|as\san)\sexample)': Group 3: Matches and captures the entire phrase.
SPLIT_EXAMPLE_REGEX = re.compile(
    r'([\.\:\;])(\s+)((?:for|as\san)\sexample)', 
    re.IGNORECASE # Use IGNORECASE flag for case-insensitive matching
)



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
    """Split: punctuation + newline + 1-2 digits + optional bracket/dot + space"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    pattern = r'([.,:;])\n(\(?[0-9]{1,2}\)?\.?\s)'
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

def split_by_specific_example_phrase(text: str) -> list[str]:
    """
    Splits a text string into parts based on a specific punctuation and phrase
    combination: [., :, ;] + space + (For|As an) + space + example.
    
    The splitter keeps the dividing punctuation with the first part and the 
    phrase with the second part.
    """
    # Regex breakdown:
    # 1. ([\.\:\;])  : Capture group 1: Matches and captures one of the required punctuation marks (., :, ;).
    # 2. (\s+)      : Capture group 2: Matches and captures one or more spaces. (Ensures space is present)
    # 3. ((?:For|As\san)\sexample) : Capture group 3: Matches and captures the entire phrase 
    #                                (e.g., "For example", "As an example").
    #                                (?:...) is a non-capturing group for the 'For|As\san' alternation.
    # 4. re.IGNORECASE: Makes the match case-insensitive (e.g., "for example" works).
    
    # The whole pattern must be non-greedy to work correctly with re.split:
    # re.split keeps the content of any capture groups as split delimiters.
    # We capture the punctuation, the space, and the phrase so we can reconstruct the sentences.
    parts = SPLIT_EXAMPLE_REGEX.split(text)
    
    # The re.split result will look like: 
    # [Start_Text, Punctuation, Space, Phrase, Middle_Text, Punctuation, Space, Phrase, End_Text]
    
    cleaned_parts = []
    
    # The first element is always text, not a delimiter
    if parts:
        current_part = parts[0]
        
        # Iterate over the delimiters (which start at index 1) in chunks of 3
        for i in range(1, len(parts), 4):
            # Check if we have the full chunk (Punctuation, Space, Phrase, Next_Text)
            if i + 3 <= len(parts):
                
                # Delimiter components
                punctuation = parts[i]
                space_before_phrase = parts[i+1] # The space after the punctuation
                phrase = parts[i+2]
                next_text = parts[i+3]
                
                # 1. Complete the current part (A) by appending the punctuation and space
                # This puts the delimiter (., :, ;) with the first sentence.
                # Example: "Sentence 1." + " "
                part_a = current_part + punctuation
                
                # Append Part A
                if part_a.strip():
                    cleaned_parts.append(part_a.strip())
                
                # 2. Start the next part (B) with the phrase and leading space
                # This puts the rest of the delimiter ( " For example" ) with the second sentence.
                # Example: " For example" + " Sentence 2."
                current_part = space_before_phrase + phrase + next_text
            else:
                # If the split ended with a delimiter but no text, append the 
                # remaining current_part and break. (Highly unlikely with this pattern)
                break 

        # Append the final accumulated part
        if current_part.strip():
            cleaned_parts.append(current_part.strip())
            
    return cleaned_parts

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
    split_by_specific_example_phrase
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