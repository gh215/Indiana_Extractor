from pathlib import Path

class Config:
    # === ОБЩИЕ НАСТРОЙКИ ===
    BASE_AI_PROCESSING_DIR = Path(r"D:\AI")
    SUPPORTED_AUDIO_EXTENSIONS = ['.wav', '.mp3', '.flac', '.ogg', '.aac', '.m4a']

    # === НАСТРОЙКИ ДЛЯ СКРИПТА 1 (Enhancer - ResembleAI) ===
    S1_ENHANCER_INPUT_VOICES_DIR = Path(r"C:\Users\yaros\Desktop\Запасные Инди\NDY\Resource\ndy\music\voices")
    S1_ENHANCER_OUTPUT_ENHANCED_RAW_DIR = BASE_AI_PROCESSING_DIR / "upscaled_music" / "voices_resembleAI"
    S1_RESEMBLE_ENHANCE_HF_SPACE_URL = "ResembleAI/resemble-enhance"
    S1_RESEMBLE_ENHANCE_API_NAME = "/predict"
    S1_RESEMBLE_CFM_ODE_SOLVER = 'Midpoint'
    S1_RESEMBLE_CFM_NUM_EVALS = 128
    S1_RESEMBLE_CFM_PRIOR_TEMP = 0.26
    S1_RESEMBLE_DENOISE_BEFORE = False
    S1_RESEMBLE_QUOTA_ERROR_PHRASE = "exceeded your quota"
    S1_RESEMBLE_API_PAUSE_DURATION_SECONDS = 0.5

    # === НАСТРОЙКИ ДЛЯ СКРИПТА 2 (Normalizer) ===
    S2_NORMALIZER_INPUT_UPSCALED_DIR = BASE_AI_PROCESSING_DIR / "other"
    S2_NORMALIZER_OUTPUT_DIR = BASE_AI_PROCESSING_DIR / "normalized_result"
    S2_NORMALIZER_ORIGINAL_AUDIO_DIR_FOR_MATCHING = Path(r'C:\Users\yaros\Desktop\Запасные Инди\NDY\Resource\ndy\music')
    S2_NORMALIZER_MODE = 'MATCH_ORIGINAL'
    S2_NORMALIZER_TARGET_LOUDNESS_LUFS = -18.0
    S2_NORMALIZER_MAX_TRUE_PEAK_DBFS = 0.0
    S2_NORMALIZER_MIN_DURATION_SEC_FOR_LUFS_MEASUREMENT = 0.5

    # === НАСТРОЙКИ ДЛЯ СКРИПТОВ 3, 4, 5 (ОБЩАЯ ОБРАБОТКА AUDIO AI / СРАВНЕНИЕ) ===
    GENERAL_AUDIO_INPUT_DIR = Path(r"C:\Users\yaros\Desktop\Необработано") # Пример, измени по необходимости
    GENERAL_AUDIO_OUTPUT_DIR = BASE_AI_PROCESSING_DIR / "other_processed" # Пример, измени по необходимости
    GENERAL_AUDIO_SKIPPED_LONG_DIR = BASE_AI_PROCESSING_DIR / "skipped_long_music_general"
    GENERAL_AUDIO_OUTPUT_LONG_DIR = BASE_AI_PROCESSING_DIR / "upscaled_merged_long_music_general" # Для склеенных длинных
    GENERAL_AUDIO_TEMP_CHUNK_DIR = BASE_AI_PROCESSING_DIR / "temp_audio_chunks_general"  # Для временных чанков

    # Общие параметры обработки аудио для скриптов 3 и 4
    GENERAL_AUDIO_API_PAUSE_DURATION_SECONDS = 1 # Пауза между вызовами API (если одна на всех)
    GENERAL_AUDIO_MAX_DURATION_SECONDS_FOR_DIRECT_PROCESSING = 9.0  # Макс. длина для обычной обработки (скрипт 3)
    GENERAL_AUDIO_SPLIT_THRESHOLD_SECONDS = 12.0  # Порог для начала нарезки (скрипт 4 - обработка длинных)
    GENERAL_AUDIO_TARGET_CHUNK_SECONDS = 10.0  # Желаемая длина чанка (скрипт 4)
    GENERAL_AUDIO_MIN_CHUNK_SECONDS = 2.0  # Мин. длина чанка (информационно для скрипта 4)

    # Общие настройки для Audio AI (Gradio) - для скриптов 3 и 4
    GENERAL_AUDIO_GRADIO_APP_URL = "http://127.0.0.1:7860/"
    GENERAL_AUDIO_API_ENDPOINT_NAME = "/predict"  # Имя API эндпоинта для этого АУДИО AI
    GENERAL_AUDIO_MODEL_NAME = "basic"
    GENERAL_AUDIO_GUIDANCE_SCALE = 2.3
    GENERAL_AUDIO_DDIM_STEPS = 38
    GENERAL_AUDIO_SEED = 42

    S5_COMPARISON_SOURCE_DIR = GENERAL_AUDIO_INPUT_DIR
    S5_COMPARISON_TARGET_DIR = GENERAL_AUDIO_OUTPUT_DIR