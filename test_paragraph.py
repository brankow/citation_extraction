import tkinter as tk
from tkinter import filedialog
import re

# --- Configuration ---
THRESHOLD = 1000  # maximum characters per paragraph before splitting


def remove_tags(text):
    """Remove all XML/HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)


def split_paragraph_on_dot_double_newline(text):
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
        if not p.endswith('.'):
            p += '.'
        parts.append(p)
    return parts


def split_paragraph_on_punctuation_dash(text):
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


def split_paragraph_on_arrow(text):
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


def process_paragraphs(file_path):
    """Read XML, extract paragraphs, clean, attempt split, and print results/errors."""
    with open(file_path, "r", encoding="utf-8") as f:
        xml_text = f.read()

    paragraph_matches = re.findall(r'<p[^>]*num="([^"]+)"[^>]*>(.*?)</p>', xml_text, flags=re.DOTALL)

    for num, para in paragraph_matches:
        clean_text = remove_tags(para).strip()
        length = len(clean_text)

        if length <= THRESHOLD:
            print(f"paragraph {num} length : {length}")
            continue

        # 1️⃣ Primary split: dot + double newline
        parts = split_paragraph_on_dot_double_newline(clean_text)

        # 2️⃣ Secondary split: punctuation (. , : ;) + newline + dash
        if len(parts) <= 1:
            parts = split_paragraph_on_punctuation_dash(clean_text)

        # 3️⃣ Tertiary split: ' -->'
        if len(parts) <= 1:
            parts = split_paragraph_on_arrow(clean_text)

        # If splitting still did not produce multiple parts -> error
        if len(parts) <= 1:
            print(f"ERROR: paragraph {num} could not be split (length: {length})")
            print("--- Paragraph content for inspection ---")
            print(clean_text)
            print("----------------------------------------\n")
            continue

        # We have multiple parts — print summary and each part
        lengths = [len(p) for p in parts]
        print(f"paragraph {num} lengths : {', '.join(map(str, lengths))}")
        for j, part in enumerate(parts, start=1):
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
