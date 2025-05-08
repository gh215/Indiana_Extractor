import sys
import time
import shutil
from pathlib import Path
from gradio_client import Client, handle_file
from audio_conf import Config

# --- ОСНОВНЫЕ НАСТРОЙКИ ИЗ КОНФИГА ---
AUDIO_INPUT_DIR = Config.S1_ENHANCER_INPUT_VOICES_DIR
ENHANCED_RAW_DIR = Config.S1_ENHANCER_OUTPUT_ENHANCED_RAW_DIR
BASE_DIR = ENHANCED_RAW_DIR.parent

# --- Настройки Gradio для Resemble Enhance из конфига ---
HF_SPACE_URL = Config.S1_RESEMBLE_ENHANCE_HF_SPACE_URL
API_NAME = Config.S1_RESEMBLE_ENHANCE_API_NAME

# --- Параметры для Resemble Enhance API из конфига ---
CFM_ODE_SOLVER = Config.S1_RESEMBLE_CFM_ODE_SOLVER
CFM_NUM_EVALS = Config.S1_RESEMBLE_CFM_NUM_EVALS
CFM_PRIOR_TEMP = Config.S1_RESEMBLE_CFM_PRIOR_TEMP
DENOISE_BEFORE = Config.S1_RESEMBLE_DENOISE_BEFORE

# --- Общие настройки из конфига ---
QUOTA_ERROR_PHRASE = Config.S1_RESEMBLE_QUOTA_ERROR_PHRASE
API_PAUSE_DURATION = Config.S1_RESEMBLE_API_PAUSE_DURATION_SECONDS
SUPPORTED_AUDIO_EXTENSIONS_GLOB = [f"*{ext}" for ext in Config.SUPPORTED_AUDIO_EXTENSIONS] # Для rglob

def setup_directories():
    """Проверяет и создает необходимые директории."""
    print("\n1. Проверка/создание необходимых папок...")
    if not AUDIO_INPUT_DIR.exists() or not AUDIO_INPUT_DIR.is_dir():
        print(f"   КРИТИЧЕСКАЯ ОШИБКА: Исходная папка НЕ НАЙДЕНА или не является папкой:")
        print(f"   {AUDIO_INPUT_DIR}")
        sys.exit(1)
    else:
        print(f"   Папка с исходными аудио: {AUDIO_INPUT_DIR}")

    ENHANCED_RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для улучшенных (raw) аудио: {ENHANCED_RAW_DIR}")
    print("   Папки проверены/созданы.")

def find_audio_files():
    """Находит все поддерживаемые аудиофайлы рекурсивно в AUDIO_INPUT_DIR."""
    print("\n2. Поиск аудиофайлов для обработки...")
    # Используем SUPPORTED_AUDIO_EXTENSIONS_GLOB из конфига
    audio_files = []
    for ext_glob in SUPPORTED_AUDIO_EXTENSIONS_GLOB:
        audio_files.extend(list(AUDIO_INPUT_DIR.rglob(ext_glob)))

    if not audio_files:
        print(f"   Не найдено аудиофайлов в {AUDIO_INPUT_DIR} (расширения: {', '.join(Config.SUPPORTED_AUDIO_EXTENSIONS)}). Нечего обрабатывать.")
        return []
    print(f"   Найдено {len(audio_files)} аудиофайлов.")
    return sorted(audio_files)

def initialize_gradio_client(url):
    """Инициализирует и возвращает клиент Gradio."""
    print(f"\n3. Подключение к Hugging Face Space: {url}...")
    try:
        client = Client(url, verbose=False)
        print("   Подключение успешно.")
        return client
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к {url}. Ошибка: {e}")
        sys.exit(1)

def enhance_audio_via_api(client, input_audio_path):
    """Отправляет аудио на улучшение через API, возвращает путь к временному УЛУЧШЕННОМУ файлу."""
    temp_denoised_path_str = None
    temp_enhanced_path_str = None
    try:
        print(f"  Отправка {input_audio_path.relative_to(AUDIO_INPUT_DIR)} на улучшение (API: {API_NAME})...")
        start_time = time.time()

        api_result = client.predict(
            handle_file(str(input_audio_path)),
            CFM_ODE_SOLVER,
            CFM_NUM_EVALS,
            CFM_PRIOR_TEMP,
            DENOISE_BEFORE,
            api_name=API_NAME
        )
        end_time = time.time()
        print(f"  Обработка API завершена за {end_time - start_time:.2f} сек.")

        if isinstance(api_result, (tuple, list)) and len(api_result) == 2:
            temp_denoised_path_str = api_result[0]
            temp_enhanced_path_str = api_result[1]
            print(f"  API вернул: Denoised='{temp_denoised_path_str}', Enhanced='{temp_enhanced_path_str}'")
        else:
            print(f"  ОШИБКА: API вернул неожиданный результат: {type(api_result)} {api_result}")
            return None, "api_unexpected_result"

        if not temp_enhanced_path_str:
            print(f"  ОШИБКА: Путь к улучшенному (Enhanced) аудио от API пуст.")
            if temp_denoised_path_str and Path(temp_denoised_path_str).exists():
                 try: Path(temp_denoised_path_str).unlink(); print("  Удален временный denoised файл.")
                 except OSError: pass
            return None, "api_empty_enhanced_path"

        temp_enhanced_path = Path(temp_enhanced_path_str)
        if not temp_enhanced_path.exists():
            print(f"  ОШИБКА: API вернул путь к Enhanced файлу ({temp_enhanced_path_str}), но файл не найден.")
            if temp_denoised_path_str and Path(temp_denoised_path_str).exists():
                 try: Path(temp_denoised_path_str).unlink(); print("  Удален временный denoised файл.")
                 except OSError: pass
            return None, "api_enhanced_file_not_found"

        if temp_denoised_path_str and Path(temp_denoised_path_str).exists():
            try:
                Path(temp_denoised_path_str).unlink()
                print("  Удален временный denoised файл.")
            except OSError as e:
                print(f"  Предупреждение: Не удалось удалить временный denoised файл {temp_denoised_path_str}: {e}")
                pass

        return temp_enhanced_path, None

    except Exception as e:
        error_message_lower = str(e).lower()
        if QUOTA_ERROR_PHRASE in error_message_lower:
            print(f"\nОШИБКА: Возможно, достигнута квота на Hugging Face Space!")
            print(f"  Сообщение API: {e}")
            return None, "quota_exceeded"
        else:
            print(f"  ОШИБКА при взаимодействии с API {HF_SPACE_URL} (Endpoint: {API_NAME}):")
            print(f"    {e}")
            if temp_denoised_path_str and Path(temp_denoised_path_str).exists():
                 try: Path(temp_denoised_path_str).unlink(); print("  Удален временный denoised файл (при ошибке).")
                 except OSError: pass
            if temp_enhanced_path_str and Path(temp_enhanced_path_str).exists():
                 try: Path(temp_enhanced_path_str).unlink(); print("  Удален временный enhanced файл (при ошибке).")
                 except OSError: pass
            return None, "api_other_error"


def process_single_audio(input_audio_path, client):
    """Обрабатывает один аудиофайл: улучшает и сохраняет БЕЗ реверберации."""
    relative_path = input_audio_path.relative_to(AUDIO_INPUT_DIR)
    target_enhanced_path = ENHANCED_RAW_DIR / relative_path

    print(f"\nОбработка: {relative_path}")
    target_enhanced_path.parent.mkdir(parents=True, exist_ok=True)

    if target_enhanced_path.exists():
        print(f"  Пропуск: Файл {target_enhanced_path.name} уже существует в {target_enhanced_path.parent.relative_to(BASE_DIR)}.")
        return "skipped"

    temp_enhanced_path, api_error_code = enhance_audio_via_api(client, input_audio_path)

    if api_error_code == "quota_exceeded":
        return "quota_exceeded"
    if api_error_code or not temp_enhanced_path:
        return "error_api"

    try:
        shutil.move(str(temp_enhanced_path), str(target_enhanced_path))
        print(f"  Улучшенный файл сохранен: {target_enhanced_path.relative_to(BASE_DIR)}")
        temp_enhanced_path = None
    except Exception as e:
        print(f"  ОШИБКА при перемещении/копировании временного файла {temp_enhanced_path.name if temp_enhanced_path else '??'} в {target_enhanced_path}: {e}")
        if temp_enhanced_path and temp_enhanced_path.exists():
             try: temp_enhanced_path.unlink()
             except OSError: pass
        return "error_copy"

    if API_PAUSE_DURATION > 0:
        print(f"  Пауза {API_PAUSE_DURATION} сек...")
        time.sleep(API_PAUSE_DURATION)

    return "success"

def print_summary_report(total_files, status_counts):
    """Печатает итоговый отчет."""
    print("\n--- Скрипт Улучшения (Enhancer Only) Завершен ---")
    print(f"Всего найдено аудиофайлов для обработки: {total_files}")
    print(f"Успешно обработано (только улучшение): {status_counts.get('success', 0)}")
    print(f"Пропущено (уже существовали): {status_counts.get('skipped', 0)}")

    errors_total = sum(v for k, v in status_counts.items() if k.startswith("error_"))
    errors_total += status_counts.get('quota_exceeded', 0)

    print(f"Возникло ошибок при обработке: {errors_total}")
    if errors_total > 0:
        print("  Детали ошибок:")
        if status_counts.get('quota_exceeded', 0) > 0:
            print(f"    - Достигнута квота API: {status_counts['quota_exceeded']} раз (обработка прервана)")
        for status, count in status_counts.items():
            if status.startswith("error_") and count > 0:
                 error_desc = {
                     "error_api": f"Ошибка API {HF_SPACE_URL}{API_NAME} / Неожиданный результат / Файл не найден",
                     "error_copy": "Ошибка копирования/перемещения временного файла",
                 }.get(status, status)
                 print(f"    - {error_desc}: {count} раз")

    print(f"\nУлучшенные файлы (без реверберации) находятся в папке: {ENHANCED_RAW_DIR}")
    print(f"Теперь можно запустить Скрипт 2 (apply_reverb.py или Normalizer), если он есть, для добавления акустики или нормализации.")


def check_dependencies():
    """Проверяет наличие необходимых библиотек."""
    print("Проверка зависимостей...")
    libs_ok = True
    try: import soundfile; print("  [OK] Библиотека soundfile найдена.")
    except ImportError: print("  [ОШИБКА] Библиотека soundfile не найдена. Установите: pip install SoundFile"); libs_ok = False

    try: import gradio_client; print("  [OK] Библиотека gradio_client найдена.")
    except ImportError: print("  [ОШИБКА] Библиотека gradio_client не найдена. Установите: pip install gradio_client"); libs_ok = False

    return libs_ok

def main():
    print("\n--- Скрипт 1: Улучшение Аудио (Только Enhance API) ---")
    if not check_dependencies():
        print("\nРабота скрипта прервана из-за отсутствия зависимостей.")
        sys.exit(1)

    setup_directories()
    audio_files_to_process = find_audio_files()
    if not audio_files_to_process:
        print("\nНет файлов для обработки.")
        return

    client = initialize_gradio_client(HF_SPACE_URL)
    if not client: return

    print("\n4. Начало обработки аудиофайлов...")
    status_counts = {}
    processed_count = 0
    total_to_process = len(audio_files_to_process)
    try:
        for i, audio_path in enumerate(audio_files_to_process):
            print(f"\n--- Файл {i+1} из {total_to_process} ---")
            status = process_single_audio(audio_path, client)
            status_counts[status] = status_counts.get(status, 0) + 1
            processed_count += 1
            if status == "quota_exceeded":
                print("\nРабота скрипта прервана из-за возможной ошибки квоты.")
                break
    except KeyboardInterrupt:
        print("\n--- Обработка прервана пользователем (Ctrl+C) ---")
    finally:
        print_summary_report(total_to_process, status_counts)

if __name__ == "__main__":
     main()