#!/usr/bin/env python3
import yaml
from jinja2 import Environment, FileSystemLoader
import sys

# Load variables
with open('config/vars.yml', 'r') as f:
    vars_data = yaml.safe_load(f)

# Set up Jinja2 environment
env = Environment(loader=FileSystemLoader('templates'), trim_blocks=True, lstrip_blocks=True)

# Render template
template = env.get_template('firewall.nft.j2')
rendered = template.render(**vars_data)

# Write output
with open('firewall.rendered.nft', 'w') as f:
    f.write(rendered)

print("Template rendered successfully to firewall.rendered.nft")
print("\n--- First 50 lines ---")
print('\n'.join(rendered.split('\n')[:50]))
