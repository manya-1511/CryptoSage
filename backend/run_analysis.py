from pathlib import Path

from analysis.firmware import extract_firmware
from analysis.binary import discover_binaries
from analysis.features import extract_features, save_feature_vector


FIRMWARE_ID = 6

BASE_DIR = Path(__file__).resolve().parent
FIRMWARE_PATH = BASE_DIR / "uploads" / str(FIRMWARE_ID) / "openwrt-24.10.8-ramips-mt7621-belkin_rt1800-squashfs-factory.bin"
OUTPUT_ROOT = BASE_DIR / "analysis_output"


def main():
    print("=" * 60)
    print("CryptoSage Firmware Analysis")
    print("=" * 60)

    # ---------------------------------------------------------
    # 1. Check firmware
    # ---------------------------------------------------------
    if not FIRMWARE_PATH.exists():
        print(f"[ERROR] Firmware not found: {FIRMWARE_PATH}")
        return

    print(f"[OK] Firmware: {FIRMWARE_PATH}")

    # ---------------------------------------------------------
    # 2. Firmware extraction
    # ---------------------------------------------------------
    print("\n[1/3] Running firmware extraction...")

    extraction = extract_firmware(
        firmware_path=FIRMWARE_PATH,
        firmware_id=FIRMWARE_ID,
        output_root=OUTPUT_ROOT,
    )

    print(f"[Extraction] {extraction.message}")

    if extraction.output_dir is None:
        print("[ERROR] No analysis output directory created.")
        return

    analysis_dir = extraction.output_dir

    print(f"[OK] Analysis directory: {analysis_dir}")

    # ---------------------------------------------------------
    # 3. Find ELF binaries
    # ---------------------------------------------------------
    print("\n[2/3] Discovering ELF binaries...")

    binaries = discover_binaries(analysis_dir)

    # The original firmware is copied to:
    # analysis_output/2/original/aes_fw.bin
    #
    # If Binwalk did not extract anything, discovery should
    # still find the original ELF.

    if not binaries:
        print("[ERROR] No ELF binaries discovered.")
        print(f"Search directory: {analysis_dir}")
        return

    print(f"[OK] Found {len(binaries)} binary/binaries:")

    for binary in binaries:
        print(f"   - {binary}")

    # ---------------------------------------------------------
    # 4. Feature extraction
    # ---------------------------------------------------------
    print("\n[3/3] Extracting feature vectors...")

    for binary in binaries:

        print(f"\nAnalyzing: {binary}")

        try:
            features = extract_features(binary)

            output_dir = analysis_dir / "features"
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = (
                output_dir
                / f"{binary.stem}_feature_vector.json"
            )

            save_feature_vector(
                features,
                output_file,
            )

            print(f"[OK] Feature vector saved:")
            print(f"     {output_file}")

        except Exception as exc:
            print(f"[ERROR] Feature extraction failed:")
            print(f"        {exc}")

    print("\n" + "=" * 60)
    print("Analysis completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
