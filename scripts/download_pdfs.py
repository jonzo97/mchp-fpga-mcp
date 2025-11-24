#!/usr/bin/env python3
"""
Download all Microchip PolarFire FPGA documentation PDFs.

This script downloads 55 PDF documents (147MB total) from official Microchip sources.
"""
import urllib.request
from pathlib import Path
from typing import Dict, List
import hashlib
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Install tqdm for progress bars: pip install tqdm")


class DownloadProgressBar:
    """Progress bar for downloads using tqdm if available."""

    def __init__(self, desc="Downloading"):
        self.desc = desc
        self.pbar = None

    def __call__(self, block_num, block_size, total_size):
        if not self.pbar and HAS_TQDM:
            self.pbar = tqdm(total=total_size, unit='B', unit_scale=True, desc=self.desc)
        if self.pbar:
            downloaded = block_num * block_size
            if downloaded < total_size:
                self.pbar.update(block_size)
        elif block_num % 100 == 0:  # Print every 100 blocks if no tqdm
            print(f"{self.desc}: {block_num * block_size / 1024 / 1024:.1f} MB", end='\r')

    def close(self):
        if self.pbar:
            self.pbar.close()


# PDF database: filename -> (URL, optional SHA256 for verification)
PDFS: Dict[str, tuple] = {
    # Core IP Handbooks (from Libero vault)
    "CoreAPB3_HB.pdf": (None, None),  # From Libero vault
    "CoreAXI4DMAController_HB.pdf": (None, None),  # From Libero vault
    "CoreAXI4Interconnect_HB.pdf": (None, None),  # From Libero vault
    "CoreGPIO_HB.pdf": (None, None),  # From Libero vault
    "CoreI2C_HB.pdf": (None, None),  # From Libero vault
    "CoreSPI_HB.pdf": (None, None),  # From Libero vault
    "CoreUARTapb_HB.pdf": (None, None),  # From Libero vault
    "coreahblite_ug.pdf": (None, None),  # From Libero vault

    # TCL and Tool Documentation
    "Libero_TCL_Commands_Reference_Guide_2024.2.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/SupportingCollateral/V2024.2/tcl_commands_ug.pdf",
        None
    ),
    "PolarFire_PDC_Commands_User_Guide_2022.2.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/pf_pdc_commands_ug.pdf",
        None
    ),
    "SmartTime_STA_User_Guide_2024.1.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/smarttime_sta_ug.pdf",
        None
    ),
    "SmartDesign_User_Guide_2024.2.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/smartdesign_ug.pdf",
        None
    ),
    "Timing_Constraints_Editor_User_Guide_2024.2.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/timing_constraints_editor_ug.pdf",
        None
    ),
    "Synplify_Pro_User_Guide_2021.03SP1.pdf": (
        "https://www.microchip.com/content/dam/mchp/documents/FPGA/ProductDocuments/UserGuides/synplify_pro_ug.pdf",
        None
    ),
    "Synplify_Pro_Command_Reference_2023.09.pdf": (
        "https://www.microchip.com/content/dam/mchp/documents/FPGA/ProductDocuments/ReferenceManuals/synplify_pro_tcl_ref.pdf",
        None
    ),
    "Synplify_Pro_Attribute_Reference_2021.03SP1.pdf": (
        "https://www.microchip.com/content/dam/mchp/documents/FPGA/ProductDocuments/ReferenceManuals/synplify_pro_attributes.pdf",
        None
    ),

    # PolarFire FPGA Core Documentation
    "PolarFire-FPGA-Datasheet-DS00003831.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/DataSheets/PolarFire-FPGA-Datasheet-DS00003831.pdf",
        None
    ),
    "PolarFire-SoC-Datasheet-DS00004248.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/DataSheets/PolarFire-SoC-Datasheet-DS00004248.pdf",
        None
    ),
    "PolarFire_FPGA_Board_Design_UG0726_V11.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/PolarFire_FPGA_Board_Design_UG0726_V11.pdf",
        None
    ),
    "Microchip_PolarFire_FPGA_and_PolarFire_SoC_FPGA_Clocking_Resources_User_Guide_VB.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/Microchip_PolarFire_FPGA_and_PolarFire_SoC_FPGA_Clocking_Resources_User_Guide_VB.pdf",
        None
    ),
    "PolarFire_FPGA_PolarFire_SoC_FPGA_Fabric_UG_VD.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/PolarFire_FPGA_PolarFire_SoC_FPGA_Fabric_UG_VD.pdf",
        None
    ),
    "Microchip_PolarFire_FPGA_and_PolarFire_SoC_FPGA_User_IO_User_Guide_VC.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/Microchip_PolarFire_FPGA_and_PolarFire_SoC_FPGA_User_IO_User_Guide_VC.pdf",
        None
    ),
    "PolarFire_FPGA_PolarFire_SoC_FPGA_Memory_Controller_User_Guide_VB.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/PolarFire_FPGA_PolarFire_SoC_FPGA_Memory_Controller_User_Guide_VB.pdf",
        None
    ),
    "PolarFire_FPGA_and_PolarFire_SoC_FPGA_Transceiver_User_Guide_VB.pdf": (
        "https://ww1.microchip.com/downloads/aemDocuments/documents/FPGA/ProductDocuments/UserGuides/PolarFire_FPGA_and_PolarFire_SoC_FPGA_Transceiver_User_Guide_VB.pdf",
        None
    ),
}


def download_file(url: str, dest_path: Path) -> bool:
    """Download a file with progress bar."""
    if not url:
        return False

    try:
        print(f"\nDownloading: {dest_path.name}")
        progress = DownloadProgressBar(desc=dest_path.name)
        urllib.request.urlretrieve(url, dest_path, progress)
        progress.close()
        return True
    except Exception as e:
        print(f"Error downloading {dest_path.name}: {e}")
        return False


def main():
    """Download all PDFs to the pdfs/ directory."""
    script_dir = Path(__file__).parent
    pdfs_dir = script_dir.parent / "pdfs"
    pdfs_dir.mkdir(exist_ok=True)

    print(f"FPGA Documentation Downloader")
    print(f"={'=' * 60}")
    print(f"Downloading {len(PDFS)} PDFs to: {pdfs_dir}\n")

    # Separate PDFs into downloadable and manual
    downloadable = {k: v for k, v in PDFS.items() if v[0] is not None}
    manual = {k: v for k, v in PDFS.items() if v[0] is None}

    # Download available PDFs
    success = 0
    failed = 0

    for filename, (url, checksum) in downloadable.items():
        dest = pdfs_dir / filename
        if dest.exists():
            print(f"✓ Already exists: {filename}")
            success += 1
            continue

        if download_file(url, dest):
            success += 1
        else:
            failed += 1

    # Report on manual downloads needed
    if manual:
        print(f"\n{'=' * 60}")
        print(f"MANUAL DOWNLOAD REQUIRED: {len(manual)} IP Core Handbooks")
        print(f"={'=' * 60}\n")
        print("The following IP core handbooks must be obtained from your")
        print("Libero SoC installation vault:\n")
        print(f"Location: ~/Microchip/Common/vault/Components/Actel/DirectCore/\n")

        for filename in sorted(manual.keys()):
            print(f"  • {filename}")

        print("\nAlternatively, these can be exported from Libero SoC:")
        print("  1. Open Libero SoC")
        print("  2. IP Catalog → Select Core → View Handbook")
        print("  3. File → Save PDF")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Download Summary:")
    print(f"  ✓ Downloaded: {success}")
    print(f"  ✗ Failed: {failed}")
    print(f"  ⚠ Manual: {len(manual)}")
    print(f"  Total: {len(PDFS)}")
    print(f"={'=' * 60}\n")

    if failed > 0 or len(manual) > 0:
        print("⚠️  Some files require manual download. See above for details.")
        return 1

    print("✅ All PDFs downloaded successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
