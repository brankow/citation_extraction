import os
import tkinter as tk
from tkinter import filedialog
from typing import List, Tuple

# --- Configuration ---
TARGET_TAG = "<nplcit"
FILE_EXTENSION = ".xml"

def count_nplcit_in_xmls():
    """
    Opens a directory selection dialog, reads all XML files in the selected
    directory, counts the occurrences of the TARGET_TAG, and prints a
    formatted table of the results.
    """
    # 1. Initialize Tkinter and prompt for directory selection
    print("Initializing directory selection dialog...")
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Open the dialog to select a directory
    directory_path = filedialog.askdirectory(
        title="Select Directory Containing XML Files"
    )

    if not directory_path:
        print("\nNo directory selected. Exiting.")
        return

    print(f"\nSelected Directory: {directory_path}")
    
    # List to store results: (filename, count)
    results: List[Tuple[str, int]] = []
    total_count = 0

    # 2. Iterate through files and count the tags
    try:
        # Get a list of all items in the directory
        all_files = os.listdir(directory_path)

        # Filter and process only XML files
        xml_files = [f for f in all_files if f.lower().endswith(FILE_EXTENSION)]

        if not xml_files:
            print(f"No {FILE_EXTENSION} files found in the directory.")
            return

        print(f"Found {len(xml_files)} XML file(s). Processing...")

        for filename in xml_files:
            file_path = os.path.join(directory_path, filename)
            
            # Skip directories if os.listdir returned any (though askdirectory suggests a flat list)
            if os.path.isdir(file_path):
                continue
            
            try:
                # Read the file content
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Count the occurrences of the opening tag string
                count = content.count(TARGET_TAG)
                results.append((filename, count))
                total_count += count
                print(f"  -> Processed {filename}: Found {count} instances.")

            except IOError as e:
                print(f"Error reading file {filename}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred while processing {filename}: {e}")

    except Exception as e:
        print(f"An error occurred during file traversal: {e}")
        return

    # 3. Print the final results in a formatted table
    if not results:
        return

    print("\n" + "=" * 50)
    print("NPLCIT TAG COUNT SUMMARY")
    print("=" * 50)
    
    # Calculate column widths for clean formatting
    max_filename_len = max(len(name) for name, _ in results) if results else 15
    filename_width = max(max_filename_len, len("Filename"))
    count_width = max(len(str(total_count)), len("Count"))

    # Define table header format
    header_format = f"| {{:<{filename_width}}} | {{:>{count_width}}} |"
    divider = "-" * (filename_width + count_width + 7) # 7 for spaces and separators

    print(divider)
    print(header_format.format("Filename", "Count"))
    print(divider)

    # Print individual file counts
    for filename, count in results:
        print(header_format.format(filename, count))
    
    print(divider)
    
    # Print the total count
    print(header_format.format("TOTAL", total_count))
    print(divider)


if __name__ == "__main__":
    count_nplcit_in_xmls()