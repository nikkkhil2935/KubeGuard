import os
import shutil

readme_path = r'c:\Users\Nikhil\Desktop\S8UL\README.md'
new_readme_path = r'c:\Users\Nikhil\Desktop\S8UL\README_NEW.md'

# Delete old README.md
if os.path.exists(readme_path):
    os.remove(readme_path)
    print(f"Deleted: {readme_path}")

# Rename README_NEW.md to README.md
if os.path.exists(new_readme_path):
    os.rename(new_readme_path, readme_path)
    print(f"Renamed: {new_readme_path} -> {readme_path}")
    print("README.md updated successfully!")
else:
    print(f"Error: {new_readme_path} not found")
