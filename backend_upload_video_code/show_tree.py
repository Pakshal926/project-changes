import os


def display_tree(
    directory, prefix="", output_file=None, exclude=(".git", "__pycache__")
):
    # Get all items in the directory, filter out those in the exclude list, and sort
    items = [item for item in sorted(os.listdir(directory)) if item not in exclude]
    total_items = len(items)

    for index, item in enumerate(items):
        path = os.path.join(directory, item)
        is_last = index == (
            total_items - 1
        )  # Check if this is the last item in the current directory

        # Determine which prefix to use for the current item
        connector = "└── " if is_last else "├── "
        output_file.write(
            prefix + connector + item + ("/" if os.path.isdir(path) else "") + "\n"
        )

        # Prepare new prefix for sub-items
        new_prefix = prefix + ("    " if is_last else "│   ")

        # Recurse into the directory if the item is a folder
        if os.path.isdir(path):
            display_tree(path, new_prefix, output_file, exclude)


# Define the output file and directory to display
output_file_path = "directory_structure.txt"  # Choose your output file name
with open(output_file_path, "w") as output_file:
    display_tree(".", output_file=output_file)

print(f"Directory structure saved to {output_file_path}")
