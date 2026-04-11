rm -rf _build

# Generate the interactive class hierarchy diagram
python generate_class_hierarchy.py

jupyter-book build --keep-going .
