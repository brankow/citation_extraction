import tkinter as tk
from tkinter import filedialog
import re
from typing import List, Callable, Tuple

# --- Configuration ---
THRESHOLD = 1000  # maximum characters per paragraph before splitting

# List of all available split functions, ordered by preference.
# The primary split_paragraph_on_dot_double_newline is handled separately.
SPLIT_METHODS: List[Callable[[str], List[str]]] = []


def remove_tags(text):
    """Remove all XML/HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)


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
        # Only add a dot if the part doesn't already end with a dot, '?', or '!'
        if not p.endswith('.') and not p.endswith('?') and not p.endswith('!'):
            p += '.'
        parts.append(p)
    return parts


def split_paragraph_on_punctuation_dash(text: str) -> List[str]:
    """
    Secondary split: punctuation (. , : ;) followed by newline + dash
    The punctuation stays at the end of the first part, dash stays at the start of the next part
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    # Include dot in the punctuation set
    pattern = r'([.,:;])\n(-)'

    parts = []
    last_index = 0
    for m in re.finditer(pattern, normalized):
        split_index = m.start(1) + 1  # include punctuation in first part
        parts.append(normalized[last_index:split_index].strip())
        last_index = m.start(2)  # dash at start of next part
    remainder = normalized[last_index:].strip()
    if remainder:
        parts.append(remainder)
    return parts

SPLIT_METHODS.append(split_paragraph_on_punctuation_dash)


def split_paragraph_on_arrow(text: str) -> List[str]:
    """
    Tertiary/fallback split: split on ' -->'
    '-->' belongs to the next part
    """
    parts = []
    last_index = 0
    for m in re.finditer(r'\s-->', text):
        split_index = m.start()  # end previous part just before ' -->'
        parts.append(text[last_index:split_index].strip())
        last_index = m.start() + 1  # include space, '-->' goes to next part
    remainder = text[last_index:].strip()
    if remainder:
        parts.append(remainder)
    return parts

SPLIT_METHODS.append(split_paragraph_on_arrow)


def split_paragraph_on_z_b(text: str) -> List[str]:
    """
    Quaternary/fallback split: split on ' z. B. ' (German for 'e.g.').
    ' z. B. ' belongs to the next part.
    """
    parts = []
    last_index = 0
    pattern = r' z\. B\. '
    
    for m in re.finditer(pattern, text):
        split_index = m.start() + 1 # end previous part just *before* 'z.'
        parts.append(text[last_index:split_index].strip())
        last_index = m.start() + 1 # start next part at the 'z.'
        
    remainder = text[last_index:].strip()
    if remainder:
        parts.append(remainder)
    
    return parts

SPLIT_METHODS.append(split_paragraph_on_z_b)


def split_paragraph_on_or_newline_dash(text: str) -> List[str]:
    """
    New Split: space + 'or' + newline + dash + space (' or\n- ').
    ' or' belongs to the end of the first part. '\n- ' belongs to the start of the second part.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Pattern: 
    # 1. Group 1: (\sor) - Space + 'or'.
    # 2. Group 2: (\n-\s) - Newline + dash + space.
    pattern = r'(\sor)(\n-\s)'

    parts = []
    last_index = 0
    for m in re.finditer(pattern, normalized):
        # Split index includes ' or' in the first part (Group 1)
        split_index = m.end(1)
        parts.append(normalized[last_index:split_index].strip())
        
        # New start index is the start of '\n- ' (Group 2)
        last_index = m.start(2)
        
    remainder = normalized[last_index:].strip()
    if remainder:
        parts.append(remainder)
        
    return parts

SPLIT_METHODS.append(split_paragraph_on_or_newline_dash) # Added here


def split_paragraph_on_punctuation_list_item(text: str) -> List[str]:
    """
    Fallback split: punctuation (., ; :) + newline + list item marker.
    The punctuation stays at the end of the first part. The list item marker stays with the second part.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Pattern: 
    # 1. Group 1: ([.,:;]) - Punctuation
    # 2. \n        - Newline
    # 3. Group 2: (\(?[0-9]{1,2}\)?\.?) - List item marker
    pattern = r'([.,:;])\n(\(?[0-9]{1,2}\)?\.?)'

    parts = []
    last_index = 0
    for m in re.finditer(pattern, normalized):
        # Split index includes the punctuation in the first part (Group 1)
        split_index = m.start(1) + 1 
        parts.append(normalized[last_index:split_index].strip())
        
        # New start index is the start of the list item marker (Group 2)
        last_index = m.start(2)
        
    remainder = normalized[last_index:].strip()
    if remainder:
        parts.append(remainder)
        
    return parts

SPLIT_METHODS.append(split_paragraph_on_punctuation_list_item)


def split_paragraph_on_figure_enumeration(text: str) -> List[str]:
    """
    Fallback Split: punctuation (., ; :) + newline + 'Fig', 'FIG', or 'FIGURE' + optional dot + space + 1-3 digits.
    The punctuation stays at the end of the first part. The figure enumeration stays with the second part.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Updated Pattern: 
    # 1. Group 1: ([.,:;]) - Punctuation
    # 2. \n        - Newline
    # 3. Group 2: ((FIG|FIGURE|Fig)\.?\s[0-9]{1,3}) 
    #    - Matches FIG, FIGURE, or Fig (case-sensitive) 
    #    - followed by an optional dot, a space, and 1-3 digits.
    pattern = r'([.,:;])\n((FIG|FIGURE|Fig)\.?\s[0-9]{1,3})'

    parts = []
    last_index = 0
    for m in re.finditer(pattern, normalized):
        # Split index includes the punctuation in the first part (Group 1)
        split_index = m.start(1) + 1 
        parts.append(normalized[last_index:split_index].strip())
        
        # New start index is the start of the figure enumeration (Group 2)
        last_index = m.start(2)
        
    remainder = normalized[last_index:].strip()
    if remainder:
        parts.append(remainder)
        
    return parts

SPLIT_METHODS.append(split_paragraph_on_figure_enumeration)


def split_paragraph_on_punctuation_letter_bracket(text: str) -> List[str]:
    """
    Fallback Split: punctuation (., ; :) + newline + single letter (a-z/A-Z) + closing bracket ')'.
    The punctuation stays at the end of the first part. The list item marker stays with the second part.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Pattern: 
    # 1. Group 1: ([.,:;]) - Punctuation
    # 2. \n+ - One or more Newlines (CR/LF)
    # 3. Group 2: ([a-zA-Z]\)) - One letter + closing bracket
    pattern = r'([.,:;])\n+([a-zA-Z]\))'

    parts = []
    last_index = 0
    for m in re.finditer(pattern, normalized):
        # Split index includes the punctuation in the first part (Group 1)
        split_index = m.start(1) + 1 
        parts.append(normalized[last_index:split_index].strip())
        
        # New start index is the start of the list item marker (Group 2)
        # We start at m.start(2) to skip the punctuation and newlines
        last_index = m.start(2)
        
    remainder = normalized[last_index:].strip()
    if remainder:
        parts.append(remainder)
        
    return parts

SPLIT_METHODS.append(split_paragraph_on_punctuation_letter_bracket)

# --- Recursive Splitting Logic (Unchanged) ---

def recursively_split_long_part(part: str, split_methods: List[Callable[[str], List[str]]]) -> Tuple[List[str], bool]:
    """
    Recursively applies fallback split methods to a text part until its length 
    is below THRESHOLD or all methods fail.

    Returns:
        A tuple: (List of resulting parts, whether any split successfully occurred)
    """
    if len(part) <= THRESHOLD:
        return [part], False # No split needed

    # Try all fallback methods in order
    for split_func in split_methods:
        sub_parts = split_func(part)

        # Check if the split actually occurred (i.e., resulted in multiple parts)
        if len(sub_parts) > 1:
            final_parts = []
            successful_split = True
            
            # Now, check if any of the new sub-parts are *still* too long, and recurse
            for sub_part in sub_parts:
                recursed_parts, _ = recursively_split_long_part(sub_part, split_methods)
                final_parts.extend(recursed_parts)
                
            return final_parts, successful_split

    # If all methods failed and the part is still too long
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
            # print(f"paragraph {num} length : {length}")
            continue

        # --- Initial Splitting Strategy ---
        
        # 1️⃣ Primary split: dot + double newline (This is often the best split)
        parts = split_paragraph_on_dot_double_newline(clean_text)
        
        # 2️⃣ Secondary/Recursive check: For *every* resulting part, 
        #    apply all fallback methods recursively if it's too long.
        final_parts = []
        # Flag to track if the paragraph was ever successfully split at any level
        was_split = len(parts) > 1 

        for part in parts:
            # The recursive function applies all methods in SPLIT_METHODS
            recursed_parts, part_was_split = recursively_split_long_part(part, SPLIT_METHODS)
            final_parts.extend(recursed_parts)
            if part_was_split:
                was_split = True
        
        # If the primary split failed (len(parts) <= 1), treat the whole paragraph 
        # as a single long part and apply the recursive fallback splits directly.
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
            # Continue printing the split parts despite the warning
        
        # We have multiple parts — print summary and each part
        lengths = [len(p) for p in final_parts]
        print(f"paragraph {num} lengths : {', '.join(map(str, lengths))}")
        for j, part in enumerate(final_parts, start=1):
            print(f"--- paragraph {num}.{j} ---")
            print(part)
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