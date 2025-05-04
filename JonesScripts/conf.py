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

    AUDIO_INPUT_DIR = Path(r"C:\Users\yaros\Desktop\Запасные Инди\NDY\Resource\ndy\music")
    AUDIO_OUTPUT_DIR = Path(r"D:\AI\upscaled_music")
    AUDIO_SKIPPED_LONG_DIR = Path(r"D:\AI\skipped_long_music")
    AUDIO_OUTPUT_LONG_DIR = Path(r"D:\AI\upscaled_merged_long_music")  # Для склеенных длинных
    AUDIO_TEMP_CHUNK_DIR = Path(r"D:\AI\temp_audio_chunks")  # Для временных чанков

    # Параметры обработки аудио
    AUDIO_MAX_DURATION_SECONDS = 9.0  # Макс. длина для обычной обработки
    AUDIO_SPLIT_THRESHOLD_SECONDS = 12.0  # Порог для начала нарезки (для скрипта 3)
    AUDIO_TARGET_CHUNK_SECONDS = 10.0  # Желаемая длина чанка (для скрипта 3)
    AUDIO_MIN_CHUNK_SECONDS = 2.0  # Мин. длина чанка (информационно для скрипта 3)
    AUDIO_EXTENSIONS = ['.wav', '.mp3', '.flac', '.ogg']  # Расширения аудио

    # Настройки для Audio AI (Gradio)
    AUDIO_GRADIO_APP_URL = "http://127.0.0.1:7860/"
    AUDIO_API_NAME = "/predict"  # Имя API для АУДИО
    AUDIO_MODEL_NAME = "basic"
    AUDIO_GUIDANCE_SCALE = 2.3
    AUDIO_DDIM_STEPS = 26
    AUDIO_SEED = 42

    AUDIO_PROCESS_PAUSE_DURATION = 0.5 # Если нужна отдельная пауза для аудио