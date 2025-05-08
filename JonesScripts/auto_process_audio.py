import os
import sys
import time
import os
import shutil
from pathlib import Path
from gradio_client import Client, handle_file
from pydub import AudioSegment
import pydub.exceptions
from audio_conf import Config

gradio_client = None # Глобальная переменная для клиента

def setup_directories():
    print("\n1. Проверка/создание выходных папок...")
    # Используем GENERAL_AUDIO_INPUT_DIR, GENERAL_AUDIO_OUTPUT_DIR, GENERAL_AUDIO_SKIPPED_LONG_DIR
    if not Config.GENERAL_AUDIO_INPUT_DIR.is_dir():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с исходными аудио ({Config.GENERAL_AUDIO_INPUT_DIR}) не найдена!")
        sys.exit(1)
    Config.GENERAL_AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    Config.GENERAL_AUDIO_SKIPPED_LONG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для обработанных: {Config.GENERAL_AUDIO_OUTPUT_DIR}")
    print(f"   Папка для пропущенных (длинных): {Config.GENERAL_AUDIO_SKIPPED_LONG_DIR}")
    print("   Папки проверены/созданы.")

def find_audio_files():
    print("\n2. Поиск аудиофайлов для обработки...")
    audio_files = []
    # Используем SUPPORTED_AUDIO_EXTENSIONS и GENERAL_AUDIO_INPUT_DIR
    for ext in Config.SUPPORTED_AUDIO_EXTENSIONS:
        audio_files.extend(list(Config.GENERAL_AUDIO_INPUT_DIR.rglob(f"*{ext}")))
        # audio_files.extend(list(Config.GENERAL_AUDIO_INPUT_DIR.rglob(f"*{ext.upper()}"))) # Опционально для регистрозависимых ФС
    unique_audio_files = sorted(list(set(audio_files)))
    if not unique_audio_files:
        print(f"   Не найдено аудиофайлов с расширениями {Config.SUPPORTED_AUDIO_EXTENSIONS} в {Config.GENERAL_AUDIO_INPUT_DIR} и подпапках.")
        return []
    print(f"   Найдено {len(unique_audio_files)} аудиофайлов для обработки или проверки.")
    return unique_audio_files

def initialize_gradio_client():
    global gradio_client
    # Используем GENERAL_AUDIO_GRADIO_APP_URL
    print(f"\n3. Подключение к локальному Gradio приложению: {Config.GENERAL_AUDIO_GRADIO_APP_URL}...")
    try:
        # Создаем нового клиента или переиспользуем, если уже есть (хотя здесь он обычно None при первом вызове)
        gradio_client = Client(Config.GENERAL_AUDIO_GRADIO_APP_URL, verbose=False)
        print("   Подключение успешно. Убедись, что app.py запущен!")
        return True
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к {Config.GENERAL_AUDIO_GRADIO_APP_URL}. Ошибка: {e}")
        gradio_client = None # Сбрасываем клиента при ошибке
        return False

def run_ai_processing(input_audio_path):
    global gradio_client
    if gradio_client is None: # Попытка инициализации, если клиент не был создан
        print("   Клиент Gradio не инициализирован. Попытка подключения...")
        if not initialize_gradio_client():
            return None, "api_init_failed_before_call"

    temp_result_path_str = None
    # Используем параметры AI GENERAL_AUDIO_...
    print(f"  Отправка {input_audio_path.name} на обработку AI...")
    print(f"  Параметры: Model='{Config.GENERAL_AUDIO_MODEL_NAME}', Guidance={Config.GENERAL_AUDIO_GUIDANCE_SCALE}, Steps={Config.GENERAL_AUDIO_DDIM_STEPS}, Seed={Config.GENERAL_AUDIO_SEED}")
    start_time = time.time()
    try:
        api_result = gradio_client.predict(
            handle_file(str(input_audio_path.resolve())), # Передаем абсолютный путь
            Config.GENERAL_AUDIO_MODEL_NAME,
            Config.GENERAL_AUDIO_GUIDANCE_SCALE,
            Config.GENERAL_AUDIO_DDIM_STEPS,
            Config.GENERAL_AUDIO_SEED,
            api_name=Config.GENERAL_AUDIO_API_ENDPOINT_NAME
        )
        end_time = time.time()
        print(f"  Обработка AI завершена за {end_time - start_time:.2f} сек.")

        if isinstance(api_result, str) and api_result:
            if os.path.exists(api_result): temp_result_path_str = api_result
            else: print(f"  ОШИБКА: API вернул путь '{api_result}', но файл не найден."); return None, "api_file_not_found"
        elif api_result is None: print(f"  ОШИБКА: API вернул None."); return None, "api_returned_none"
        else: print(f"  ОШИБКА: API вернул неожиданный результат типа {type(api_result)}: {api_result}"); return None, "api_unexpected_result_type"

        if not temp_result_path_str: print(f"  ОШИБКА: Не удалось получить путь к результату от API."); return None, "api_path_processing_failed"

        print(f"  AI создал временный файл: {temp_result_path_str}")
        return Path(temp_result_path_str), None

    except Exception as e:
        print(f"  ОШИБКА при взаимодействии с API {Config.GENERAL_AUDIO_GRADIO_APP_URL} ({Config.GENERAL_AUDIO_API_ENDPOINT_NAME}): {e}")
        # Попытка переподключения, если это была ошибка связи
        if "Connection" in str(e) or "Network" in str(e): # Очень упрощенная проверка
            print("  Попытка переподключения к Gradio...")
            time.sleep(2)
            if initialize_gradio_client():
                print("  Переподключение успешно, попробуйте отправить файл снова (текущий пропущен).")
                return None, "api_error_reconnected_retry_manually" # Сигнал, что можно попробовать еще раз
            else:
                print("  КРИТИЧЕСКАЯ ОШИБКА: Не удалось переподключиться к Gradio.")
                return None, "api_reconnect_failed"
        return None, "api_other_error" # Другая ошибка API

def trim_to_duration(processed_audio_path, target_duration_ms, final_output_path):
    # Логика этой функции не зависит от Config, оставляем как есть (аналогично скрипту 1)
    try:
        print(f"  Обрезка/выравнивание AI-файла до {target_duration_ms / 1000.0:.3f} сек (длительность оригинала)...")
        file_format = processed_audio_path.suffix.lower().replace('.', '')
        if file_format == 'ogg': file_format = 'oga'
        elif not file_format: file_format = 'wav'

        if not processed_audio_path.exists():
             print(f"  ОШИБКА: Файл для обрезки не найден: {processed_audio_path}"); return False, "trim_file_not_found_before_load"

        processed_audio = AudioSegment.from_file(processed_audio_path, format=file_format)
        processed_duration_ms = len(processed_audio)

        if processed_duration_ms > target_duration_ms:
            trimmed_audio = processed_audio[:target_duration_ms]
            print(f"  Файл обрезан с {processed_duration_ms} мс до {len(trimmed_audio)} мс.")
        elif processed_duration_ms < target_duration_ms:
            needed_silence_ms = target_duration_ms - processed_duration_ms
            print(f"  ПРЕДУПРЕЖДЕНИЕ: AI-файл ({processed_duration_ms} мс) короче оригинала ({target_duration_ms} мс). Добавляем {needed_silence_ms} мс тишины.")
            padding = AudioSegment.silent(duration=needed_silence_ms)
            trimmed_audio = processed_audio + padding
        else:
            trimmed_audio = processed_audio
            print(f"  Длительность AI-файла ({processed_duration_ms} мс) уже совпадает с оригиналом.")

        output_format = final_output_path.suffix.lower().replace('.', '')
        if not output_format: output_format = 'wav'
        print(f"  Сохранение результата в: {final_output_path} (формат: {output_format})")
        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        trimmed_audio.export(final_output_path, format=output_format)
        return True, None
    except FileNotFoundError: print(f"  ОШИБКА: Файл не найден при попытке обрезки/выравнивания: {processed_audio_path}"); return False, "trim_file_not_found"
    except pydub.exceptions.CouldntDecodeError: print(f"  ОШИБКА pydub: Не удалось декодировать файл {processed_audio_path} для обрезки."); return False, "trim_decode_error"
    except Exception as e:
        print(f"  ОШИБКА: Не удалось обрезать/выровнять или сохранить файл {final_output_path.name}: {e}")
        if final_output_path.exists():
            try: final_output_path.unlink()
            except OSError: pass
        return False, "trim_error"

def process_single_audio(original_audio_path):
    original_duration_ms = 0
    try:
        # Используем GENERAL_AUDIO_INPUT_DIR
        relative_path = original_audio_path.relative_to(Config.GENERAL_AUDIO_INPUT_DIR)
    except ValueError:
        print(f"\nОШИБКА: Не удалось определить относительный путь для {original_audio_path} относительно {Config.GENERAL_AUDIO_INPUT_DIR}. Пропускаем.")
        return "error_relative_path"

    print(f"\nПроверка: {relative_path}")

    try:
        print(f"  Получение длительности оригинала...")
        input_format = original_audio_path.suffix.lower().replace('.', '')
        if not input_format : input_format = None
        audio_info = AudioSegment.from_file(original_audio_path, format=input_format)
        original_duration_ms = len(audio_info)
        duration_sec = original_duration_ms / 1000.0
        print(f"  Оригинальная длительность: {duration_sec:.3f} сек ({original_duration_ms} мс).")

        # Используем GENERAL_AUDIO_MAX_DURATION_SECONDS_FOR_DIRECT_PROCESSING и GENERAL_AUDIO_SKIPPED_LONG_DIR
        if duration_sec > Config.GENERAL_AUDIO_MAX_DURATION_SECONDS_FOR_DIRECT_PROCESSING:
            print(f"  ПРЕВЫШЕНИЕ ЛИМИТА ({Config.GENERAL_AUDIO_MAX_DURATION_SECONDS_FOR_DIRECT_PROCESSING:.1f} сек). Перемещение...")
            skipped_long_output_path = Config.GENERAL_AUDIO_SKIPPED_LONG_DIR / relative_path
            skipped_long_output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(original_audio_path), str(skipped_long_output_path))
                print(f"  Файл перемещен в: {skipped_long_output_path}")
                return "skipped_long"
            except Exception as move_err:
                print(f"  ОШИБКА при перемещении файла: {move_err}")
                return "error_move_failed" # Файл мог остаться на месте, но обработка его нецелесообразна
    except FileNotFoundError:
         # Эта ошибка может возникнуть, если файл был удален/перемещен другим процессом между find_audio_files и этим моментом.
         print(f"  ОШИБКА: Исходный файл не найден для получения длительности/обработки: {original_audio_path}")
         return "error_original_not_found_at_processing" # Уточненный статус
    except pydub.exceptions.CouldntDecodeError:
         print(f"  ОШИБКА pydub: Не удалось прочитать длительность оригинала: {original_audio_path.name}")
         return "error_duration_read"
    except Exception as dur_err:
        print(f"  ОШИБКА при получении длительности оригинала: {dur_err}")
        return "error_duration_generic"

    # Используем GENERAL_AUDIO_OUTPUT_DIR
    final_output_path = (Config.GENERAL_AUDIO_OUTPUT_DIR / relative_path).with_suffix('.wav') # Результат всегда wav
    print(f"  -> Конечный обработанный файл: {final_output_path}")
    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    if final_output_path.exists():
        print(f"  Пропуск: Обработанный файл {final_output_path.name} уже существует.")
        return "skipped_exists"

    temp_ai_output_path, ai_error_code = run_ai_processing(original_audio_path)
    if ai_error_code:
        return f"error_ai_{ai_error_code}" # Код ошибки уже включает "api_"
    if not temp_ai_output_path or not temp_ai_output_path.exists():
        print("  Критическая ошибка: AI не вернул путь/файл, но и не код ошибки.")
        return "error_internal_ai_path_missing" # Уточненный статус

    trim_success, trim_error_code = trim_to_duration(
        temp_ai_output_path,
        original_duration_ms,
        final_output_path
    )

    if temp_ai_output_path.exists(): # Проверяем перед удалением
        try:
            print(f"  Удаление временного файла AI: {temp_ai_output_path}")
            temp_ai_output_path.unlink()
        except OSError as e:
            print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить временный файл {temp_ai_output_path.name}: {e}")

    if not trim_success:
        return f"error_trim_{trim_error_code}"

    # Используем GENERAL_AUDIO_API_PAUSE_DURATION_SECONDS
    if Config.GENERAL_AUDIO_API_PAUSE_DURATION_SECONDS > 0:
        print(f"  Пауза {Config.GENERAL_AUDIO_API_PAUSE_DURATION_SECONDS} сек...")
        time.sleep(Config.GENERAL_AUDIO_API_PAUSE_DURATION_SECONDS)

    return "success"

def print_summary_report(total_files, status_counts):
    print("\n--- Скрипт Автоматической Обработки Завершен ---")
    print(f"Всего найдено аудиофайлов для проверки/обработки: {total_files}")
    print(f"Успешно обработано (AI + Обрезка до оригинала): {status_counts.get('success', 0)}")
    print(f"Пропущено (обработанный файл уже существовал): {status_counts.get('skipped_exists', 0)}")
    print(f"Пропущено (длительность > {Config.GENERAL_AUDIO_MAX_DURATION_SECONDS_FOR_DIRECT_PROCESSING:.1f} сек, перемещены): {status_counts.get('skipped_long', 0)}")
    print(f"Пропущено (исходный файл отсутствовал при начале обработки): {status_counts.get('skipped_original_missing',0) + status_counts.get('error_original_not_found_at_processing',0) }")


    errors_total = sum(v for k, v in status_counts.items() if k.startswith("error_"))
    print(f"Возникло ошибок при обработке/проверке: {errors_total}")
    if errors_total > 0:
        print("  Детали ошибок:")
        error_summary = {}
        for status, count in status_counts.items():
            if status.startswith("error_"):
                parts = status.split('_', 2)
                error_type = parts[1].upper() if len(parts) > 1 else "UNKNOWN_TYPE"
                error_code = parts[2] if len(parts) > 2 else "general"
                key = f"Ошибка {error_type}" + (f" ({error_code})" if error_code != "general" else "")
                error_summary[key] = error_summary.get(key, 0) + count
        for error_desc, count in sorted(error_summary.items()):
            print(f"    - {error_desc}: {count} раз")
        print("  Просмотрите лог выше для подробной информации по каждому файлу.")

    print(f"\nОбработанные файлы сохранены в: {Config.GENERAL_AUDIO_OUTPUT_DIR}")
    print(f"Слишком длинные файлы перемещены в: {Config.GENERAL_AUDIO_SKIPPED_LONG_DIR}")
    print("Не забудь остановить процесс 'python app.py', если он больше не нужен.")

def check_dependencies():
    # Аналогично предыдущим скриптам
    print("Проверка зависимостей...")
    ok = True
    try: import gradio_client; print("  [OK] gradio_client")
    except ImportError: print("  [ОШИБКА] gradio_client не найден. Установите: pip install gradio_client"); ok = False
    try:
        import pydub; print("  [OK] pydub")
        try: AudioSegment.silent(duration=10); print("  [OK] FFmpeg/avconv (предположительно) доступен для pydub.")
        except Exception as e: print(f"  [ПРЕДУПРЕЖДЕНИЕ] pydub не смог выполнить базовую операцию. Убедитесь, что FFmpeg/avconv установлен и в PATH. Ошибка: {e}")
    except ImportError: print("  [ОШИБКА] pydub не найден. Установите: pip install pydub"); ok = False
    return ok

if __name__ == "__main__":
    if not check_dependencies():
        print("\nРабота скрипта прервана из-за отсутствия зависимостей.")
        sys.exit(1)

    print("\n--- Скрипт Автоматической Обработки Аудио (Настройки из Config) ---")
    print(f"Исходные файлы из: {Config.GENERAL_AUDIO_INPUT_DIR}")
    print(f"Результаты в:      {Config.GENERAL_AUDIO_OUTPUT_DIR}")
    print(f"Слишком длинные (> {Config.GENERAL_AUDIO_MAX_DURATION_SECONDS_FOR_DIRECT_PROCESSING:.1f} сек) в: {Config.GENERAL_AUDIO_SKIPPED_LONG_DIR}")
    print(f"Обработка AI через: {Config.GENERAL_AUDIO_GRADIO_APP_URL} (эндпоинт: {Config.GENERAL_AUDIO_API_ENDPOINT_NAME})")
    print(f"Параметры AI: Model='{Config.GENERAL_AUDIO_MODEL_NAME}', Guidance={Config.GENERAL_AUDIO_GUIDANCE_SCALE}, Steps={Config.GENERAL_AUDIO_DDIM_STEPS}, Seed={Config.GENERAL_AUDIO_SEED}")
    print(f"Пауза между API вызовами: {Config.GENERAL_AUDIO_API_PAUSE_DURATION_SECONDS} сек")
    print("-" * 50)
    print("ВАЖНО: Убедись, что 'python app.py' (локальный Gradio сервер) запущен!")
    print(f"ВАЖНО: Убедись, что FFmpeg/avconv установлен и доступен в системном PATH!")
    input("Нажми Enter для начала обработки...")

    setup_directories()
    original_audio_files = find_audio_files()
    if not original_audio_files:
        print("\nНе найдено аудиофайлов для обработки.")
        sys.exit(0)

    # Инициализируем Gradio клиент один раз здесь, если это возможно
    if not initialize_gradio_client():
        sys.exit("Не удалось подключиться к Gradio при запуске. Проверьте URL и доступность сервера.")

    print("\n4. Начало проверки и обработки аудиофайлов...")
    status_counts = {}
    total_files_to_process = len(original_audio_files)
    for i, audio_path in enumerate(original_audio_files):
        print(f"\n>>> Обработка файла {i+1}/{total_files_to_process}: {audio_path.name} <<<")
        if not audio_path.exists(): # Проверка перед непосредственной обработкой
            print(f"Пропуск: Исходный файл {audio_path.name} не найден (возможно, был перемещен или удален).")
            status = "skipped_original_missing"
        else:
            status = process_single_audio(audio_path)
        status = status if status else "error_unknown_status_returned_main"
        status_counts[status] = status_counts.get(status, 0) + 1
        print(f">>> Статус файла {audio_path.name}: {status} <<<")

    print_summary_report(total_files_to_process, status_counts)