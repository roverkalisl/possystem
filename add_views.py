#!/usr/bin/env python
"""Script to add logging views to views.py"""

# Read logging views
with open('pos/logging_views.py', 'r') as f:
    content = f.read()

# Skip the docstring and imports that are already in views.py
lines = content.split('\n')
start = 0
for i, line in enumerate(lines):
    if line.startswith('from django.shortcuts'):
        start = i
        break

# Reconstruct
new_content = '\n'.join(lines[start:])

# Append to views.py
with open('pos/views.py', 'a') as f:
    f.write('\n\n# =========================\n# LOGGING VIEWS\n# =========================\n')
    f.write(new_content)

print('Successfully added logging views to views.py')
