import ctypes
import argparse
from ctypes import byref, c_int, c_char_p
from PIL import Image
import sys
import os
import gc
from fpdf import FPDF

# Helper function and classes
def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_int), ("cy", ctypes.c_int)]

class BondiDJVUActions:
    def __init__(self):
        self.lib = ctypes.CDLL(bondi_dll)
        self.open_file_name = None
        self.page_count = 0
        self.page_size_array = []

    def open_document(self, file_name: str, username: str, password: str) -> bool:
        if self.open_file_name is not None:
            self.close_document()
        self.open_file_name = file_name
        self.lib.OpenDocument(
            c_char_p(file_name.encode("utf-8")),
            c_char_p(username.encode("utf-8")),
            c_char_p(password.encode("utf-8")),
        )
        self.page_count = self.lib.GetPageCount()
        self.page_size_array = [(0, 0)] * self.page_count
        return True

    def close_document(self):
        if self.open_file_name is None:
            return
        self.lib.CloseDocument()
        self.open_file_name = None
        self.page_count = 0
        self.page_size_array = []

    def get_page_size(self, page_index: int):
        if page_index < 0 or page_index >= self.page_count:
            return (0, 0)
        if self.page_size_array[page_index] != (0, 0):
            return self.page_size_array[page_index]
        size = SIZE()
        self.lib.GetPageSize(c_int(page_index), byref(size))
        self.page_size_array[page_index] = (size.cx, size.cy)
        return self.page_size_array[page_index]

    def save_page_bitmap(self, page_index: int, width: int, height: int):
        bitmap_data = (ctypes.c_byte * (4 * width * height))()
        success = self.lib.GetPageBitmapData(
            c_int(page_index),
            c_int(width),
            c_int(height),
            c_int(0),
            ctypes.byref(bitmap_data),
        )
        if success:
            img = Image.frombuffer(
                "RGBA", (width, height), bitmap_data, "raw", "BGRA", 0, 1
            )
            gc.collect()
            return img

# Configuration and utility code
cwd = os.getcwd()
cwd = resource_path(cwd)
bondi_dll = os.path.join(cwd, "BondiReader.DJVU.dll")
bondi_dll = resource_path(bondi_dll)

# These credentials are hard-coded in the Rolling Stone DJVU files
default_username = "RollingStone"
default_password = "Mhw8FqG2cHRUtsG0J4NxqBcR26mUJtUlzqc6wv51TDM"

# Synchronous version of process_file
def process_file(file_path, actions, output_dir, default_username=default_username, default_password=default_password):
    print(f"Starting to process file: {file_path}")

    if actions.open_document(file_path, default_username, default_password):
        print("Document opened successfully.")
        page_count = actions.page_count
        print(f"Page count: {page_count}")

        pdf = FPDF()
        for page in range(page_count):
            print(f"Processing page {page + 1} of {page_count}")
            size = actions.get_page_size(page)
            print(f"Page size: {size[0]}x{size[1]}")

            img = actions.save_page_bitmap(page, size[0], size[1])
            if img:
                print("Page bitmap saved successfully, converting to RGB.")
                img = img.convert("RGB")
                # Ensure a unique file name for each page's image
                img_file_path = os.path.join(output_dir, f"temp_img_{page}.jpg")
                img.save(img_file_path, "JPEG")

                pdf.add_page()
                # The size and position should be adjusted based on the actual size of your pages and the desired output.
                # Here, 210 and 297 represent an A4 size in mm. Consider adjusting these values based on the image size or desired output.
                pdf.image(img_file_path, 0, 0, 210, 297)
                os.remove(img_file_path)  # Clean up after adding to PDF
                print(f"Page {page + 1} added to PDF and temporary file removed.")

        output_pdf_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(file_path))[0]}.pdf")
        pdf.output(output_pdf_path)
        print(f"Saved PDF at {output_pdf_path}")

        actions.close_document()
        print("Document closed.")
    else:
        print("Failed to open document. Please check the file path and credentials.")


# Main function adjustment
def main():
    parser = argparse.ArgumentParser(description="Process BondiReader (Rolling Stone) DJVU files or directories of DJVU files.")
    parser.add_argument("path", help="The DJVU file or directory to process.")
    parser.add_argument("--output_dir", default=os.path.join(os.getcwd(), "output"), help="Directory to save the processed PDFs.")
    args = parser.parse_args()

    actions = BondiDJVUActions()
    output_dir = args.output_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if os.path.isdir(args.path):
        for file in os.listdir(args.path):
            if file.endswith(".djvu"):
                process_file(os.path.join(args.path, file), actions, output_dir)
    elif os.path.isfile(args.path) and args.path.endswith(".djvu"):
        process_file(args.path, actions, output_dir)
    else:
        print("The specified path is not a .djvu file or a directory.")

if __name__ == "__main__":
    main()
