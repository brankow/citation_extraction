
import sys
import os 
import time
import constants # Contains Regexes and API settings
from File_Citation_Extraction import extract_paragraphs
from llm_client import call_lm_studio_api_with_retry
from utils import select_xml_folder
import constants 

from llm_client import call_lm_studio_api_with_retry # Needed for the main connection check


# --- Constants for Connection Check ---
LM_STUDIO_URL = constants.LM_STUDIO_URL
MODEL_NAME = constants.MODEL_NAME 
# -------------------------------------

def process_folder():
    """
    Handles user input for folder selection and iterates over all XML files.
    """
    print("--- LLM Citation Batch Processor ---")
    
    # 1. API Connection Check (reused from original main)
    try:
        call_lm_studio_api_with_retry({
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.0,
            "stream": False,
            "max_tokens": 1 
        })
        print(f"✓ Connected to LLM server at {LM_STUDIO_URL}")
        
    except Exception: 
        print(f"✗ ERROR: Could not connect to LLM server at {LM_STUDIO_URL}.")
        print("Please ensure the server is running with a model loaded.")
        sys.exit(1)

    # 2. Folder Selection
    folder_path = select_xml_folder()
    
    if not folder_path:
        print("\nFolder selection cancelled. Exiting.")
        return

    print(f"\nProcessing files in folder: {folder_path}")
    
    # 3. File Iteration and Processing
    xml_files = [
        os.path.join(folder_path, f) 
        for f in os.listdir(folder_path) 
        # Check if the filename, converted to lowercase, ends with '.xml'
        if f.lower().endswith('.xml') and os.path.isfile(os.path.join(folder_path, f))
    ]

    if not xml_files:
        print("No XML files found in the selected folder.")
        return

    total_files = len(xml_files)

    # --- BATCH DURATION START ---
    batch_start_time = time.time()
    # ----------------------------
    
    for i, file_path in enumerate(xml_files):
        print(f"\n--- [FILE {i + 1}/{total_files}] Starting processing: {os.path.basename(file_path)} ---")
        
        # Call the existing, robust core logic function
        start_time = time.time()
        extract_paragraphs(file_path)
        end_time = time.time()
        if constants.terminal_feedback:
            print(f"--- [FILE {i + 1}/{total_files}] Finished in {end_time - start_time:.2f} seconds. ---")
        
    # --- BATCH DURATION END ---
    batch_end_time = time.time()
    total_duration = batch_end_time - batch_start_time
    # --------------------------

    print(f"\n✅ Batch processing complete. Total files processed: {total_files}")
    print(f"⏱️ Total processing time for directory: {total_duration:.2f} seconds.")


if __name__ == "__main__":
    process_folder()