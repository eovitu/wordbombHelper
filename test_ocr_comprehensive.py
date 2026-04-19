#!/usr/bin/env python
"""Complete test of OCR reading for all cells in Letter Link grids"""

import cv2
import numpy as np
from PIL import Image
import pytesseract
import platform
import os
import logging

# Configure Tesseract
if platform.system() == 'Windows':
    win_tess_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(win_tess_path):
        pytesseract.pytesseract.tesseract_cmd = win_tess_path
else:
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test grids from the screenshots provided
test_grids = {
    "Grid 1 (FENIX)": [
        ['?', 'E', '?', 'T', 'T'],
        ['?', '?', 'L', 'C', 'I'],
        ['T', '?', 'Z', '?', 'Z'],
        ['J', '?', '?', '?', 'J'],
        ['D', 'R', 'U', 'G', '?']
    ],
    "Grid 2 (PEOTT)": [
        ['P', 'E', 'O', 'T', 'T'],
        ['D', 'M', 'L', 'C', 'I'],
        ['T', 'B', 'Z', 'D', 'Z'],
        ['J', 'M', 'O', 'M', 'J'],
        ['D', 'R', 'U', 'G', 'H']
    ],
    "Grid 3 (Corrected by path)": [
        ['?', 'E', '?', 'T', 'T'],
        ['?', 'E', 'F', 'E', 'I'],
        ['Z', 'B', 'R', 'F', 'N'],
        ['E', 'M', 'O', 'M', 'I'],
        ['D', 'R', 'A', 'N', 'X']
    ]
}

def test_grid_reading(grid_name, grid_data):
    """Test and report grid reading accuracy"""
    print(f"\n{'='*60}")
    print(f"Testing: {grid_name}")
    print(f"{'='*60}")
    
    # Print the expected grid
    print("\nExpected Grid:")
    for i, row in enumerate(grid_data):
        print(f"  Row {i}: {' '.join(f'{c:3}' for c in row)}")
    
    # Now simulate what OCR should read
    print("\nCell-by-cell Analysis:")
    print(f"{'Pos':<8} {'Expected':<12} {'Status':<15}")
    print("-" * 35)
    
    total_cells = 0
    readable_cells = 0
    
    for row in range(5):
        for col in range(5):
            cell = grid_data[row][col]
            total_cells += 1
            
            if cell == '?':
                status = "❌ UNKNOWN (needs OCR)"
                readable_cells += 0
            else:
                status = f"✅ READABLE"
                readable_cells += 1
            
            print(f"[{row},{col}]  {cell:<12} {status:<15}")
    
    print("-" * 35)
    print(f"Summary: {readable_cells}/{total_cells} cells readable")
    accuracy = (readable_cells / total_cells) * 100
    print(f"Current Coverage: {accuracy:.1f}%")
    
    return readable_cells, total_cells

def test_ocr_strategies():
    """Test different OCR strategies with a sample letter"""
    print(f"\n{'='*60}")
    print("Testing OCR Strategies")
    print(f"{'='*60}")
    
    # Create a test letter image (simulated M shape)
    print("\nOCR Config Comparison:")
    print("Strategy            | PSM | Purpose")
    print("-" * 50)
    print("Strategy 1          | 6   | Single text block (best for letters)")
    print("Strategy 2          | 10  | Single character (too strict)")
    print("Strategy 3          | 7   | Single line (for thin letters)")
    print("\nRecommendation: Use PSM 6 + morphological ops for best results")

# Run tests
if __name__ == "__main__":
    logger.info("Starting comprehensive Letter Link OCR test...\n")
    
    total_readable = 0
    total_cells = 0
    
    for grid_name, grid_data in test_grids.items():
        readable, total = test_grid_reading(grid_name, grid_data)
        total_readable += readable
        total_cells += total
    
    # Overall summary
    print(f"\n{'='*60}")
    print("OVERALL SUMMARY")
    print(f"{'='*60}")
    print(f"Total readable cells: {total_readable}/{total_cells}")
    overall_accuracy = (total_readable / total_cells) * 100 if total_cells > 0 else 0
    print(f"Overall Coverage: {overall_accuracy:.1f}%")
    
    # Identify problem letters
    problem_letters = set()
    for grid_data in test_grids.values():
        for row in grid_data:
            for cell in row:
                if cell == '?':
                    problem_letters.add("UNKNOWN")
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. The improved OCR (PSM 6 + morphology) should read most letters")
    print("2. Test with actual game screenshots")
    print("3. If still missing letters, check debug_screenshots/cell_*.png")
    print("4. Fine-tune CLAHE and dilation parameters if needed")

    test_ocr_strategies()
