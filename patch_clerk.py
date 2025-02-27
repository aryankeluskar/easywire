#!/usr/bin/env python3
"""
This script patches the clerk_backend_api library to work with Pydantic 2.10+
by fixing fields with leading underscores.
"""

import os
import sys
import importlib.util
import re
import glob

def find_file(filename, search_path=None):
    """Find a file in the Python package path or a specific search path."""
    if search_path:
        paths = search_path if isinstance(search_path, list) else [search_path]
    else:
        paths = sys.path
    
    for path in paths:
        for root, _, files in os.walk(path):
            if filename in files:
                return os.path.join(root, filename)
    
    return None

def find_clerk_model_files():
    """Find all clerk_backend_api model files that might need patching."""
    try:
        # Find the clerk_backend_api package
        clerk_spec = importlib.util.find_spec("clerk_backend_api")
        if not clerk_spec or not clerk_spec.origin:
            print("Could not find clerk_backend_api package.")
            return []
        
        # Get the package directory
        clerk_dir = os.path.dirname(clerk_spec.origin)
        models_dir = os.path.join(clerk_dir, "models")
        
        # Check if the models directory exists
        if not os.path.isdir(models_dir):
            print(f"Models directory not found at {models_dir}")
            return []
        
        # Return all Python files in the models directory
        return glob.glob(os.path.join(models_dir, "*.py"))
    
    except Exception as e:
        print(f"Error finding clerk model files: {e}")
        return []

def patch_file(file_path):
    """Patch the file to fix leading underscore field names."""
    if not file_path or not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    
    try:
        # Read the file
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Define patterns to look for
        patterns = [
            (r'__pydantic_extra__', 'pydantic_extra'),  # Remove both leading underscores
            (r'_pydantic_extra__', 'pydantic_extra'),   # Remove the remaining leading underscore
            # Add more patterns for other field names with leading underscores
            (r'__annotations__', 'annotations'),
            (r'__module__', 'module'),
            (r'__qualname__', 'qualname'),
            (r'__name__', 'name'),
            (r'__doc__', 'doc'),
        ]
        
        # Track if any replacements were made
        made_replacements = False
        
        # Apply all replacements
        patched_content = content
        for pattern, replacement in patterns:
            if pattern in patched_content:
                patched_content = patched_content.replace(pattern, replacement)
                made_replacements = True
                print(f"Replaced {pattern} with {replacement} in {file_path}")
        
        # If no replacements were made, return early
        if not made_replacements:
            print(f"No patterns found to replace in {file_path}")
            return False
        
        # Write the patched file
        with open(file_path, 'w') as f:
            f.write(patched_content)
        
        print(f"Successfully patched {file_path}")
        return True
    
    except Exception as e:
        print(f"Error patching file {file_path}: {e}")
        return False

def main():
    print("Looking for clerk_backend_api models to patch...")
    
    # Find all model files
    file_paths = find_clerk_model_files()
    if not file_paths:
        print("Could not find any files to patch. Exiting.")
        return False
    
    print(f"Found {len(file_paths)} files to check for patching")
    
    # Track overall success
    success = False
    
    # Patch each file
    for file_path in file_paths:
        print(f"Checking file: {file_path}")
        if patch_file(file_path):
            success = True
    
    if success:
        print("Patching completed successfully for at least one file.")
        return True
    else:
        print("No files were patched.")
        return False

if __name__ == "__main__":
    main() 