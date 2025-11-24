# FPGA Documentation PDFs

This directory contains 55 Microchip PolarFire FPGA documentation PDFs (147MB total) required for the RAG system.

**PDFs are NOT included in this repository due to size constraints.**

## Quick Start

Download all PDFs automatically:

```bash
python scripts/download_pdfs.py
```

This will download 47 PDFs from official Microchip URLs. The remaining 8 IP core handbooks must be manually obtained from your Libero SoC installation.

## Manual Download: IP Core Handbooks

8 IP core handbooks must be copied from your Libero SoC installation:

### Location
```
~/Microchip/Common/vault/Components/Actel/DirectCore/
```

### Required Files
1. `CoreAPB3_HB.pdf` - From `CoreAPB3/*/docs/`
2. `CoreAXI4DMAController_HB.pdf` - From `COREAXI4DMACONTROLLER/*/`
3. `CoreAXI4Interconnect_HB.pdf` - From `CoreAXI4Interconnect/*/docs/`
4. `CoreGPIO_HB.pdf` - From `CoreGPIO/*/docs/`
5. `CoreI2C_HB.pdf` - From `COREI2C/*/docs/`
6. `CoreSPI_HB.pdf` - From `CORESPI/*/docs/docs/`
7. `CoreUARTapb_HB.pdf` - From `CoreUARTapb/*/docs/`
8. `coreahblite_ug.pdf` - From `CoreAHBLite/*/docs/`

### Alternative: Export from Libero

If you don't have direct file system access:

1. Open Libero SoC
2. Go to **IP Catalog**
3. Select desired core (e.g., CoreUARTapb)
4. Click **View Handbook**
5. **File → Save PDF** to this directory

## Documentation Catalog

### Core IP Handbooks (8 files)
- CoreAPB3, CoreAXI4DMAController, CoreAXI4Interconnect
- CoreGPIO, CoreI2C, CoreSPI, CoreUARTapb, CoreAHBLite

### TCL & Tool Documentation (8 files)
- Libero TCL Commands Reference Guide
- PolarFire PDC Commands User Guide
- SmartTime STA User Guide
- SmartDesign User Guide
- Timing Constraints Editor User Guide
- Synplify Pro User Guide, Command Reference, Attribute Reference

### PolarFire FPGA Documentation (39 files)
- Datasheets (PolarFire FPGA, PolarFire SoC, RT PolarFire)
- User Guides (Clocking, Fabric, User I/O, Memory Controller, Transceivers)
- Application Notes (Security, Low Power, Safety Critical, etc.)
- Board/Kit Documentation (Eval Kit, Discovery Kit, etc.)

## Verification

After downloading, verify you have all 55 PDFs:

```bash
ls -1 *.pdf | wc -l
# Should output: 55
```

## License & Redistribution

All PDFs are copyrighted by Microchip Technology Inc. and are provided for reference purposes only. **Do not redistribute these PDFs** - users should download from official Microchip sources or their Libero installation.

## Need Help?

- **Microchip Documentation Portal**: https://www.microchip.com/en-us/products/fpgas-and-plds
- **Libero SoC Download**: https://www.microchip.com/en-us/products/fpgas-and-plds/fpga-and-soc-design-tools/fpga/libero-software-later-versions

## File Sizes

Total size: ~147 MB
- Largest: Synplify Pro Command Reference (504 pages, ~6.5 MB)
- Smallest: IP Core Handbooks (~400-800 KB each)
