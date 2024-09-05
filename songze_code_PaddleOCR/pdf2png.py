import os
import argparse
from PyPDF2 import PdfFileReader
from pdf2image import convert_from_path
from PIL import Image

def convert_pdf_to_images(pdf_path, output_dir, resolution):
    """
    Convert PDF to images, increase resolution, and save each page as a PNG file.
    
    Args:
        pdf_path (str): Path to the input PDF file.
        output_dir (str): Directory to save the output images.
        resolution (int): Resolution (DPI) to increase the image quality.
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Convert PDF to images
    images = convert_from_path(pdf_path, dpi=resolution)
    
    # Extract base name and directory name for the output files
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    
    # Save each page as a PNG file
    for i, image in enumerate(images):
        # Construct filename with zero-padding
        filename = f"{base_name}{i+1:02d}.png"
        image_path = os.path.join(output_dir, filename)
        image.save(image_path, "PNG")
        print(f"Saved: {image_path}")

def process_directory(input_dir, output_dir, resolution):
    """
    Process all PDF files in the given directory and convert them to images.
    
    Args:
        input_dir (str): Directory containing PDF files.
        output_dir (str): Base directory to save the converted images.
        resolution (int): Resolution (DPI) to increase the image quality.
    """
    # Process each PDF file in the directory
    for file_name in os.listdir(input_dir):
        if file_name.lower().endswith(".pdf"):
            pdf_path = os.path.join(input_dir, file_name)
            pdf_output_dir = os.path.join(output_dir, os.path.splitext(file_name)[0])
            convert_pdf_to_images(pdf_path, pdf_output_dir, resolution)

def main():
    parser = argparse.ArgumentParser(description="Convert PDF files to images with increased resolution.")
    parser.add_argument("input_dir", type=str, help="Directory containing PDF files to convert.")
    parser.add_argument("output_dir", type=str, help="Base directory to save the converted images.")
    parser.add_argument("--resolution", type=int, default=300, help="Resolution (DPI) for the images.")
    
    args = parser.parse_args()
    
    process_directory(args.input_dir, args.output_dir, args.resolution)

if __name__ == "__main__":
    main()
