import os
from tkinter import Tk
from tkinter.filedialog import askdirectory

# Check if ANSI escape codes are supported
supports_colors = os.name != 'nt' or os.getenv('ANSICON') or os.getenv('WT_SESSION')

# Define colors
if supports_colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"
else:
    GREEN = ""
    RED = ""
    RESET = ""

# Create a pop-up window to select the main directory
Tk().withdraw()  # Hide the root window
main_directory = askdirectory(title="Select the Directory with Subfolders and/or Files Containing Siesta Outputs")

if not main_directory:  # If no directory is selected, exit the program
    print("No directory selected. Exiting program.")
    exit()

# Normalize the main directory path based on the operating system
main_directory = os.path.normpath(main_directory)

folders = []

# Listing the folders in the main directory
for directory in os.listdir(main_directory):
    d = os.path.normpath(os.path.join(main_directory, directory))
    if os.path.isdir(d):
        folders.append(d)

# If no subfolders are found, add the main directory itself
if not folders:
    folders.append(main_directory)


# Detect relaxation status in the .out file
def detect_relaxation_status(file_path):
    with open(file_path, 'r') as out_file:
        for line in out_file:
            if 'unrelaxed' in line.lower():
                return "unrelaxed"
            elif 'relaxed' in line.lower():
                return "relaxed"
    return "unknown"


# Extract atomic coordinates and only the last set of unit cell vectors
def extract_atomic_data(file_path):
    coordinates, unit_cell = [], []
    capture_coordinates, capture_unit_cell = False, False

    with open(file_path, 'r') as file:
        for line in file:
            # Capture atomic coordinates
            if "outcoor: Final (unrelaxed) atomic coordinates" in line:
                capture_coordinates = True
                coordinates = []  # Reset to capture the last set
                continue
            if capture_coordinates and line.strip() == "":
                capture_coordinates = False
            if capture_coordinates:
                coordinates.append(line.strip())

            # Capture the last unit cell vectors
            if "outcell: Unit cell" in line:
                capture_unit_cell = True
                unit_cell = []  # Reset to capture the last set
                continue
            if capture_unit_cell and "outcell: Cell vector modules" in line:
                capture_unit_cell = False
            if capture_unit_cell:
                unit_cell.append(line.strip())

    return coordinates, unit_cell


# Helper function to format rows neatly
def format_row(values, col_widths):
    return "  ".join(f"{value:>{width}.8f}" if isinstance(value, float) else f"{value:>{width}}" 
                     for value, width in zip(values, col_widths))


# Function to format and print atomic coordinates and unit cell data
def format_and_print_data(coordinates, unit_cell):
    print("\nAtomic Coordinates:")
    # Define column widths for proper alignment
    atomic_col_widths = [12, 12, 12, 4, 6, 2]  # Adjust widths as needed
    formatted_coordinates = [
        format_row([float(x) if i < 3 else int(x) if i < 5 else x for i, x in enumerate(line.split())], atomic_col_widths)
        for line in coordinates
    ]
    print("\n".join(formatted_coordinates))

    print("\nUnit Cell Vectors:")
    cell_col_widths = [12, 12, 12]  # Adjust widths as needed
    formatted_unit_cell = [
        format_row([float(x) for x in line.split()], cell_col_widths) for line in unit_cell
    ]
    print("\n".join(formatted_unit_cell))

    return formatted_coordinates, formatted_unit_cell


# Updating .fdf file with formatted data
def update_fdf_file(file_path, formatted_coordinates, formatted_unit_cell):
    
    with open(file_path, 'r') as fdf_file:
        fdf_lines = fdf_file.readlines()

    # Initialize variables to track sections
    start_atomic, end_atomic = None, None
    start_cell, end_cell = None, None
    lattice_constant_line = None
    
    # Normalize labels by removing - _ . and converting to lowercase
    def normalize_label(label):
        return label.replace('-', '').replace('_', '').replace('.', '').lower()

    # Locate relevant sections and LatticeConstant
    for i, line in enumerate(fdf_lines):
        normalized_line = normalize_label(line.split()[0]) if line.strip() else ""
        if normalized_line == "latticeconstant":
            lattice_constant_line = i
        if "%block AtomicCoordinatesAndAtomicSpecies" in line:
            start_atomic = i
        if "%endblock AtomicCoordinatesAndAtomicSpecies" in line:
            end_atomic = i
        if "%block LatticeVectors" in line:
            start_cell = i
        if "%endblock LatticeVectors" in line:
            end_cell = i

    # Update atomic coordinates
    if start_atomic is not None and end_atomic is not None:
        fdf_lines[start_atomic + 1:end_atomic] = [f"{line}\n" for line in formatted_coordinates]

    # Update unit cell vectors
    if start_cell is not None and end_cell is not None:
        fdf_lines[start_cell + 1:end_cell] = [f"{line}\n" for line in formatted_unit_cell]

    # Replace the LatticeConstant line with "LatticeConstant 1 Ang"
    if lattice_constant_line is not None:
        fdf_lines[lattice_constant_line] = "LatticeConstant 1 Ang\n"

    # Write back to the .fdf file
    with open(file_path, 'w') as fdf_file:
        fdf_file.writelines(fdf_lines)

    print(f"File '{file_path}' has been updated successfully.")


# Process each folder
for folder in folders:
    output_file_found = False

    # Changing the working directory
    try:
        os.chdir(folder)
    except (NotADirectoryError, PermissionError) as e:
        print(e)
        continue

    for file in os.listdir(folder):
        # Search for the file with ".out" extension
        if file.lower().endswith(".out"):
            output_file_found = True
            file_path = os.path.normpath(os.path.join(folder, file))
            status = detect_relaxation_status(file_path)
            if status == "relaxed":
                print(f"\n{GREEN}{file} in {folder} folder is relaxed.{RESET}")
                continue  # Skip relaxed files

            print(f"\n{RED}{file} in {folder} folder is UNRELAXED!{RESET}")

            # Extract atomic coordinates and unit cell vectors
            coordinates, unit_cell = extract_atomic_data(file_path)

            if not coordinates or not unit_cell:
                print(f"Failed to extract data from {file}.")
                continue

            # Format and print data
            formatted_coordinates, formatted_unit_cell = format_and_print_data(coordinates, unit_cell)

            # Process .fdf files
            for fdf_file in os.listdir(folder):
                if fdf_file.lower().endswith(".fdf"):
                    fdf_path = os.path.join(folder, fdf_file)
                    user_response = input(f"Do you want to update the file '{fdf_file}'? [Y/n]: ").strip().lower()
                    if user_response == 'y':
                        update_fdf_file(fdf_path, formatted_coordinates, formatted_unit_cell)
                    elif user_response == 'n':
                        print(f"Skipping file: {fdf_file}.")
                    else:
                        print(f"Invalid input. Please enter 'Y' or 'N'. Skipping file: {fdf_file}.")

    if not output_file_found:
        print(f"\nNo output file was found in {folder}.")
