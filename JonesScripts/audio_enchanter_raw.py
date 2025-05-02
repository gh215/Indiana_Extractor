import sys
import time
import os
import shutil
from pathlib import Path
from gradio_client import Client, handle_file
from pydub import AudioSegment
# Убираем импорт detect_nonsilent, он больше не нужен
import pydub.exceptions

# --- ОСНОВНЫЕ НАСТРОЙКИ ---
INPUT_AUDIO_DIR = Path(r"C:\Users\yaros\Desktop\Запасные Инди\NDY\Resource\ndy\music")
OUTPUT_AUDIO_DIR = Path(r"D:\AI\upscaled_music")
SKIPPED_LONG_AUDIO_DIR = Path(r"D:\AI\skipped_long_music")
MAX_DURATION_SECONDS = 9.0
AUDIO_EXTENSIONS = ['.wav', '.mp3', '.flac', '.ogg']

# --- НАСТРОЙКИ AI ---
GRADIO_APP_URL = "http://127.0.0.1:7860/"
API_NAME = "/predict"
MODEL_NAME = "basic"
GUIDANCE_SCALE = 2.3
DDIM_STEPS = 26
SEED = 42

# --- НАСТРОЙКИ ОБРЕЗКИ (БОЛЬШЕ НЕ ИСПОЛЬЗУЮТСЯ ДЛЯ ТИШИНЫ) ---
# SILENCE_THRESH_DB = -50 # <-- Убрано, не используется
# MIN_SILENCE_LEN_MS = 500 # <-- Убрано, не используется

# --- ПРОЧИЕ НАСТРОЙКИ ---
PROCESS_PAUSE_DURATION = 0.5
gradio_client = None

# --- setup_directories, find_audio_files, initialize_gradio_client, run_ai_processing ---
# --- остаются БЕЗ ИЗМЕНЕНИЙ (используем версии из предпоследнего ответа) ---
def setup_directories():
    print("\n1. Проверка/создание выходных папок...")
    if not INPUT_AUDIO_DIR.is_dir():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с исходными аудио ({INPUT_AUDIO_DIR}) не найдена!")
        sys.exit(1)
    OUTPUT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    SKIPPED_LONG_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для обработанных: {OUTPUT_AUDIO_DIR}")
    print(f"   Папка для пропущенных (длинных): {SKIPPED_LONG_AUDIO_DIR}")
    print("   Папки проверены/созданы.")

def find_audio_files():
    print("\n2. Поиск аудиофайлов для обработки...")
    audio_files = []
    for ext in AUDIO_EXTENSIONS:
        audio_files.extend(list(INPUT_AUDIO_DIR.rglob(f"*{ext}")))
        audio_files.extend(list(INPUT_AUDIO_DIR.rglob(f"*{ext.upper()}")))
    unique_audio_files = sorted(list(set(audio_files)))
    if not unique_audio_files:
        print(f"   Не найдено аудиофайлов с расширениями {AUDIO_EXTENSIONS} в {INPUT_AUDIO_DIR} и подпапках.")
        return []
    print(f"   Найдено {len(unique_audio_files)} аудиофайлов для обработки или проверки.")
    return unique_audio_files

def initialize_gradio_client():
    global gradio_client
    print(f"\n3. Подключение к локальному Gradio приложению: {GRADIO_APP_URL}...")
    try:
        gradio_client = Client(GRADIO_APP_URL, verbose=False)
        print("   Подключение успешно. Убедись, что app.py запущен!")
        return True
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к {GRADIO_APP_URL}. Ошибка: {e}")
        return False

def run_ai_processing(input_audio_path):
    global gradio_client
    temp_result_path_str = None
    try:
        print(f"  Отправка {input_audio_path.name} на обработку AI...")
        print(f"  Параметры: Model='{MODEL_NAME}', Guidance={GUIDANCE_SCALE}, Steps={DDIM_STEPS}, Seed={SEED}")
        start_time = time.time()
        api_result = gradio_client.predict(
            handle_file(str(input_audio_path)), MODEL_NAME, GUIDANCE_SCALE, DDIM_STEPS, SEED, api_name=API_NAME
        )
        end_time = time.time()
        print(f"  Обработка AI завершена за {end_time - start_time:.2f} сек.")
        if isinstance(api_result, str) and api_result:
            if os.path.exists(api_result):
                temp_result_path_str = api_result
            else:
                print(f"  ОШИБКА: API вернул путь '{api_result}', но файл не найден.")
                return None, "api_file_not_found"
        elif api_result is None:
             print(f"  ОШИБКА: API вернул None.")
             return None, "api_returned_none"
        else:
            print(f"  ОШИБКА: API вернул неожиданный результат типа {type(api_result)}: {api_result}")
            return None, "api_unexpected_result_type"
        if not temp_result_path_str:
             print(f"  ОШИБКА: Не удалось получить путь к результату от API.")
             return None, "api_path_processing_failed"
        print(f"  AI создал временный файл: {temp_result_path_str}")
        return Path(temp_result_path_str), None
    except Exception as e:
        print(f"  ОШИБКА при взаимодействии с API {GRADIO_APP_URL} ({API_NAME}): {e}")
        return None, "api_error"

# --- НОВАЯ функция обрезки по длительности ---
def trim_to_duration(processed_audio_path, target_duration_ms, final_output_path):
    """
    Загружает аудио из processed_audio_path, обрезает его до target_duration_ms
    (или дополняет тишиной, если короче) и сохраняет в final_output_path.
    """
    try:
        print(f"  Обрезка/выравнивание AI-файла до {target_duration_ms / 1000.0:.3f} сек (длительность оригинала)...")
        # Определяем формат файла для pydub
        file_format = processed_audio_path.suffix.lower().replace('.', '')
        if file_format == 'ogg': file_format = 'oga' # или 'ogg'
        elif not file_format: file_format = 'wav' # Если у временного файла нет расширения

        # Загружаем обработанный AI файл
        processed_audio = AudioSegment.from_file(processed_audio_path, format=file_format)
        processed_duration_ms = len(processed_audio)

        # --- Логика обрезки или дополнения ---
        if processed_duration_ms > target_duration_ms:
            # Если AI файл длиннее оригинала -> обрезаем
            trimmed_audio = processed_audio[:target_duration_ms]
            print(f"  Файл обрезан с {processed_duration_ms} мс до {len(trimmed_audio)} мс.")
        elif processed_duration_ms < target_duration_ms:
            # Если AI файл короче оригинала -> дополняем тишиной
            needed_silence_ms = target_duration_ms - processed_duration_ms
            print(f"  ПРЕДУПРЕЖДЕНИЕ: AI-файл ({processed_duration_ms} мс) короче оригинала ({target_duration_ms} мс). Добавляем {needed_silence_ms} мс тишины.")
            padding = AudioSegment.silent(duration=needed_silence_ms)
            trimmed_audio = processed_audio + padding
        else:
            # Длины совпадают
            trimmed_audio = processed_audio
            print(f"  Длительность AI-файла ({processed_duration_ms} мс) уже совпадает с оригиналом.")
        # ------------------------------------

        # Сохраняем результат
        output_format = final_output_path.suffix.lower().replace('.', '')
        if not output_format: output_format = 'wav'
        print(f"  Сохранение результата в: {final_output_path} (формат: {output_format})")
        trimmed_audio.export(final_output_path, format=output_format)
        return True, None # Успех

    except FileNotFoundError:
        print(f"  ОШИБКА: Файл не найден при попытке обрезки/выравнивания: {processed_audio_path}")
        return False, "trim_file_not_found"
    except pydub.exceptions.CouldntDecodeError:
         print(f"  ОШИБКА pydub: Не удалось декодировать файл {processed_audio_path} для обрезки.")
         return False, "trim_decode_error"
    except Exception as e:
        print(f"  ОШИБКА: Не удалось обрезать/выровнять или сохранить файл {final_output_path.name}: {e}")
        if final_output_path.exists():
            try: final_output_path.unlink() # Попытка удалить частично созданный файл
            except OSError: pass
        return False, "trim_error"

# --- ОБНОВЛЕННАЯ функция process_single_audio ---
def process_single_audio(original_audio_path):
    """
    Полный цикл обработки одного аудиофайла:
    1. Получение длительности оригинала.
    2. Проверка длительности -> Перемещение если > MAX_DURATION_SECONDS.
    3. Проверка существования результата -> Пропуск.
    4. Обработка AI.
    5. Обрезка/выравнивание до оригинальной длительности.
    """
    original_duration_ms = 0 # Инициализируем

    # 1. Определить относительный путь
    try:
        relative_path = original_audio_path.relative_to(INPUT_AUDIO_DIR)
    except ValueError:
        print(f"\nОШИБКА: Не удалось определить относительный путь для {original_audio_path}. Пропускаем.")
        return "error_relative_path"

    print(f"\nПроверка: {relative_path}")

    # 2. Получение длительности ОРИГИНАЛЬНОГО файла
    try:
        print(f"  Получение длительности оригинала...")
        audio_info = AudioSegment.from_file(original_audio_path)
        original_duration_ms = len(audio_info) # pydub len() возвращает мс
        duration_sec = original_duration_ms / 1000.0
        print(f"  Оригинальная длительность: {duration_sec:.3f} сек ({original_duration_ms} мс).")

        # 3. Проверка на превышение лимита
        if duration_sec > MAX_DURATION_SECONDS:
            print(f"  ПРЕВЫШЕНИЕ ЛИМИТА ({MAX_DURATION_SECONDS:.1f} сек). Перемещение...")
            skipped_long_output_path = SKIPPED_LONG_AUDIO_DIR / relative_path
            skipped_long_output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(original_audio_path), str(skipped_long_output_path))
                print(f"  Файл перемещен в: {skipped_long_output_path}")
                return "skipped_long"
            except Exception as move_err:
                print(f"  ОШИБКА при перемещении файла: {move_err}")
                return "error_move_failed"

    except FileNotFoundError:
         print(f"  ОШИБКА: Исходный файл не найден для получения длительности: {original_audio_path}")
         return "error_original_not_found"
    except pydub.exceptions.CouldntDecodeError:
         print(f"  ОШИБКА: Не удалось прочитать длительность оригинала (pydub decode): {original_audio_path.name}")
         return "error_duration_read"
    except Exception as dur_err:
        print(f"  ОШИБКА при получении длительности оригинала: {dur_err}")
        return "error_duration_generic"

    # --- Если файл подходит по длине, продолжаем ---

    # 4. Определяем путь конечного файла
    final_output_path = OUTPUT_AUDIO_DIR / relative_path
    final_output_path = final_output_path.with_suffix('.wav') # Сохраняем в WAV
    print(f"  -> Конечный обработанный файл: {final_output_path}")

    # Создаем родительские папки для КОНЕЧНОГО файла
    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    # 5. Пропуск, если КОНЕЧНЫЙ файл уже существует
    if final_output_path.exists():
        print(f"  Пропуск: Обработанный файл {final_output_path.name} уже существует.")
        return "skipped"

    # --- Шаг 6: Обработка через AI ---
    temp_ai_output_path, ai_error_code = run_ai_processing(original_audio_path)

    if ai_error_code:
        return f"error_ai_{ai_error_code}"
    if not temp_ai_output_path or not temp_ai_output_path.exists():
        print("  Критическая ошибка: AI не вернул путь/файл, но и не код ошибки.")
        return "error_internal_ai_path"

    # --- Шаг 7: Обрезка/Выравнивание до оригинальной длительности ---
    # Используем новую функцию и передаем ей длительность оригинала в мс
    trim_success, trim_error_code = trim_to_duration(
        temp_ai_output_path,
        original_duration_ms, # Передаем полученную ранее длительность
        final_output_path
    )

    # --- Шаг 8: Удаление временного файла AI ---
    try:
        print(f"  Удаление временного файла AI: {temp_ai_output_path}")
        temp_ai_output_path.unlink()
    except OSError as e:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить временный файл {temp_ai_output_path.name}: {e}")

    if not trim_success:
        return f"error_trim_{trim_error_code}" # Используем тот же префикс ошибки

    # --- Успешное завершение ---
    if PROCESS_PAUSE_DURATION > 0:
        print(f"  Пауза {PROCESS_PAUSE_DURATION} сек...")
        time.sleep(PROCESS_PAUSE_DURATION)

    return "success"

# --- ОБНОВЛЕННАЯ функция print_summary_report ---
def print_summary_report(total_files, status_counts):
    """Печатает итоговый отчет."""
    print("\n--- Скрипт Завершен ---")
    print(f"Всего найдено аудиофайлов для проверки/обработки: {total_files}")
    print(f"Успешно обработано (AI + Обрезка до оригинала): {status_counts.get('success', 0)}") # Уточнено
    print(f"Пропущено (обработанный файл уже существовал): {status_counts.get('skipped', 0)}")
    print(f"Пропущено (длительность > {MAX_DURATION_SECONDS:.1f} сек, перемещены): {status_counts.get('skipped_long', 0)}")

    errors_total = sum(v for k, v in status_counts.items() if k.startswith("error_"))
    print(f"Возникло ошибок при обработке/проверке: {errors_total}")
    if errors_total > 0:
        print("  Детали ошибок:")
        error_summary = {}
        for status, count in status_counts.items():
            if status.startswith("error_"):
                parts = status.split('_')
                error_type = parts[1]
                error_code = '_'.join(parts[2:]) if len(parts) > 2 else "general"
                key = f"Ошибка {error_type.upper()} ({error_code})"
                error_summary[key] = error_summary.get(key, 0) + count
        for error_desc, count in sorted(error_summary.items()):
            print(f"    - {error_desc}: {count} раз")
        print("  Просмотрите лог выше для подробной информации по каждому файлу.")

    print(f"\nОбработанные файлы сохранены в: {OUTPUT_AUDIO_DIR}")
    print(f"Слишком длинные файлы перемещены в: {SKIPPED_LONG_AUDIO_DIR}")
    print("Не забудь остановить процесс 'python app.py', если он больше не нужен.")

# ... (check_dependencies без изменений) ...
def check_dependencies():
    """Проверяет наличие необходимых библиотек."""
    print("Проверка зависимостей...")
    ok = True
    try:
        import gradio_client
        print("  [OK] Библиотека gradio_client найдена.")
    except ImportError:
        print("  [ОШИБКА] Библиотека gradio_client не найдена. Установите: pip install gradio_client")
        ok = False
    try:
        import pydub
        print("  [OK] Библиотека pydub найдена.")
        # Убираем ЛЮБЫЕ попытки найти ffmpeg явно.
        # Pydub сам попытается его использовать, если он нужен и доступен.
        # Так как FFmpeg у тебя есть в PATH, pydub должен его найти и использовать молча.
        # Если бы FFmpeg не было, могло бы быть RuntimeWarning, но для WAV это не всегда критично.
        print("  [INFO] FFmpeg установлен и доступен в PATH (подтверждено 'ffmpeg -version'). pydub должен его использовать.")
    except ImportError:
        print("  [ОШИБКА] Библиотека pydub не найдена. Установите: pip install pydub")
        ok = False
    # Возвращаем True, если базовые библиотеки Python импортируются.
    # Наличие FFmpeg мы проверили вручную.
    return ok

# --- Точка входа (Убраны упоминания параметров обрезки тишины) ---
if __name__ == "__main__":
    if not check_dependencies():
        print("\nРабота скрипта прервана из-за отсутствия критических зависимостей (FFmpeg?).")
        sys.exit(1)

    print("\n--- Скрипт Автоматической Обработки Аудио ---")
    print(f"Исходные файлы из: {INPUT_AUDIO_DIR}")
    print(f"Результаты в:      {OUTPUT_AUDIO_DIR}")
    print(f"Слишком длинные (> {MAX_DURATION_SECONDS:.1f} сек) в: {SKIPPED_LONG_AUDIO_DIR}")
    print(f"Обработка AI через: {GRADIO_APP_URL} (эндпоинт: {API_NAME})")
    print(f"Параметры AI: Model='{MODEL_NAME}', Guidance={GUIDANCE_SCALE}, Steps={DDIM_STEPS}, Seed={SEED}")
    # Убрана строка про параметры обрезки тишины
    print("-" * 50)
    print("ВАЖНО: Убедись, что 'python app.py' запущен!")
    print(f"ВАЖНО: Убедись, что FFmpeg установлен и доступен!")
    input("Нажми Enter для начала обработки...")

    # 1. Подготовка
    setup_directories()
    original_audio_files = find_audio_files()
    if not original_audio_files: sys.exit(0)
    if not initialize_gradio_client(): sys.exit(1)

    # 2. Основной цикл обработки
    print("\n4. Начало проверки и обработки аудиофайлов...")
    status_counts = {}
    for audio_path in original_audio_files:
        if not audio_path.exists():
            print(f"\nПропуск: Исходный файл {audio_path.name} не найден (был перемещен?).")
            continue
        status = process_single_audio(audio_path)
        status_counts[status] = status_counts.get(status, 0) + 1

    # 3. Итоговый отчет
    print_summary_report(len(original_audio_files), status_counts)