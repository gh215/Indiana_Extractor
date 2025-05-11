from pathlib import Path

class Config:
    BASE_DIR = Path(r"D:\Test jones\Resource\mat")

    MAT_DIR = BASE_DIR
    EXTRACTED_DIR = BASE_DIR / "extracted"
    USED_DIR = BASE_DIR / "used"
    USED_MAT_DIR = BASE_DIR / "used_mat"
    MANUAL_CEL_DIR = BASE_DIR / "manual_cel_processing"
    USED_MANUAL_MAT_DIR = BASE_DIR / "used_manual_mat"
    PROCESSED_PNG_DIR = BASE_DIR / "processed_png"
    FINAL_MAT_DIR = BASE_DIR / "final_mat"
    RENAME_TARGET_DIR = BASE_DIR / "cel_ready_scripts"
    RENAME_SUBSTRING_TO_REMOVE = '__cel_0'

    # --- Исполняемый файл matool.exe ---
    MATOOL_EXE_PRIMARY = BASE_DIR / "matool.exe"
    MATOOL_EXE_ALT = EXTRACTED_DIR / "matool.exe"
    MATOOL_FILENAME = "matool.exe"

    FORMAT_DIRS = {
        "rgb565": EXTRACTED_DIR / "rgb565",
        "rgba4444": EXTRACTED_DIR / "rgba4444",
        "rgba5551": EXTRACTED_DIR / "rgba5551",
        "unknown": EXTRACTED_DIR / "unknown_format",
        "rgba": EXTRACTED_DIR / "rgba_unknown"
    }

    HF_SPACE_URL = "Phips/Upscaler"
    TARGET_MODEL_NAME = "4xNomosWebPhoto_RealPLKSR"
    API_NAME = "/upscale_image"
    QUOTA_ERROR_PHRASE = "exceeded your gpu quota" #
    API_PAUSE_DURATION = 1
    VALID_EXTENSIONS = {".png", ".webp"}