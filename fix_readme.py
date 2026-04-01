#!/usr/bin/env python3
# Read the file
with open('README.md', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Find and remove the problematic trailing text
# Search backwards to find "#   K u b e G u a r d"
index_to_remove = -1
for i in range(len(lines) - 1, -1, -1):
    if "#   K u b e G u a r d" in lines[i]:
        index_to_remove = i
        break

# Remove from this line onwards
if index_to_remove > 0:
    lines = lines[:index_to_remove]

# Remove trailing empty lines
while lines and lines[-1].strip() == '':
    lines.pop()

# Now add the proper footer
footer = """---

If you want, the next step can be splitting this into:
- a contributor-focused `CONTRIBUTING.md`
- a security-focused `SECURITY.md`
- and per-folder `README.md` docs (`watcher`, `chaos`, `k8s`) for even cleaner navigation.

---

<p align="center">
  <strong>Built with ❤️ by Team S8UL</strong>
</p>"""

new_content = '\n'.join(lines) + '\n\n' + footer + '\n'

# Write back
with open('README.md', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✓ README.md updated successfully")
print("  - Removed trailing '#   K u b e G u a r d' text")
print("  - Added proper footer with Team S8UL branding")
