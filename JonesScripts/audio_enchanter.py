import sys
import time
import os
import shutil
from pathlib import Path
from gradio_client import Client, handle_file
from pydub import AudioSegment
import pydub.exceptions
from conf import Config

gradio_client = None

def setup_directories():
    """Проверяет и создает необходимые директории, используя Config."""
    print("\n1. Проверка/создание выходных папок...")
    # Используем пути из Config
    if not Config.AUDIO_INPUT_DIR.is_dir():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с исходными аудио ({Config.AUDIO_INPUT_DIR}) не найдена!")
        sys.exit(1)
    Config.AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    Config.AUDIO_SKIPPED_LONG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для обработанных: {Config.AUDIO_OUTPUT_DIR}")
    print(f"   Папка для пропущенных (длинных): {Config.AUDIO_SKIPPED_LONG_DIR}")
    print("   Папки проверены/созданы.")

def find_audio_files():
    """Ищет аудиофайлы, используя пути и расширения из Config."""
    print("\n2. Поиск аудиофайлов для обработки...")
    audio_files = []
    # Используем расширения и путь из Config
    for ext in Config.AUDIO_EXTENSIONS:
        audio_files.extend(list(Config.AUDIO_INPUT_DIR.rglob(f"*{ext}")))
        audio_files.extend(list(Config.AUDIO_INPUT_DIR.rglob(f"*{ext.upper()}")))
    unique_audio_files = sorted(list(set(audio_files)))
    if not unique_audio_files:
        print(f"   Не найдено аудиофайлов с расширениями {Config.AUDIO_EXTENSIONS} в {Config.AUDIO_INPUT_DIR} и подпапках.")
        return []
    print(f"   Найдено {len(unique_audio_files)} аудиофайлов для обработки или проверки.")
    return unique_audio_files

def initialize_gradio_client():
    """Инициализирует клиент Gradio, используя URL из Config."""
    global gradio_client
    # Используем URL из Config
    print(f"\n3. Подключение к локальному Gradio приложению: {Config.AUDIO_GRADIO_APP_URL}...")
    try:
        gradio_client = Client(Config.AUDIO_GRADIO_APP_URL, verbose=False)
        print("   Подключение успешно. Убедись, что app.py запущен!")
        return True
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к {Config.AUDIO_GRADIO_APP_URL}. Ошибка: {e}")
        return False

def run_ai_processing(input_audio_path):
    """Запускает обработку AI, используя параметры из Config."""
    global gradio_client
    temp_result_path_str = None
    # Используем параметры AI из Config
    print(f"  Отправка {input_audio_path.name} на обработку AI...")
    print(f"  Параметры: Model='{Config.AUDIO_MODEL_NAME}', Guidance={Config.AUDIO_GUIDANCE_SCALE}, Steps={Config.AUDIO_DDIM_STEPS}, Seed={Config.AUDIO_SEED}")
    start_time = time.time()
    try:
        api_result = gradio_client.predict(
            handle_file(str(input_audio_path)),
            Config.AUDIO_MODEL_NAME,
            Config.AUDIO_GUIDANCE_SCALE,
            Config.AUDIO_DDIM_STEPS,
            Config.AUDIO_SEED,
            api_name=Config.AUDIO_API_NAME # Используем имя API для аудио
        )
        end_time = time.time()
        print(f"  Обработка AI завершена за {end_time - start_time:.2f} сек.")

        # Логика обработки результата остается прежней
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
        # Используем URL из Config в сообщении об ошибке
        print(f"  ОШИБКА при взаимодействии с API {Config.AUDIO_GRADIO_APP_URL} ({Config.AUDIO_API_NAME}): {e}")
        return None, "api_error"

def trim_to_duration(processed_audio_path, target_duration_ms, final_output_path):
    """Обрезает/выравнивает аудио. Логика не меняется, параметры приходят извне."""
    try:
        print(f"  Обрезка/выравнивание AI-файла до {target_duration_ms / 1000.0:.3f} сек (длительность оригинала)...")
        file_format = processed_audio_path.suffix.lower().replace('.', '')
        if file_format == 'ogg': file_format = 'oga'
        elif not file_format: file_format = 'wav'

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
        # Убедимся, что родительская папка существует перед сохранением
        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        trimmed_audio.export(final_output_path, format=output_format)
        return True, None

    except FileNotFoundError:
        print(f"  ОШИБКА: Файл не найден при попытке обрезки/выравнивания: {processed_audio_path}")
        return False, "trim_file_not_found"
    except pydub.exceptions.CouldntDecodeError:
         print(f"  ОШИБКА pydub: Не удалось декодировать файл {processed_audio_path} для обрезки.")
         return False, "trim_decode_error"
    except Exception as e:
        print(f"  ОШИБКА: Не удалось обрезать/выровнять или сохранить файл {final_output_path.name}: {e}")
        if final_output_path.exists():
            try: final_output_path.unlink()
            except OSError: pass
        return False, "trim_error"

def process_single_audio(original_audio_path):
    """Обрабатывает один файл, используя пути и лимиты из Config."""
    original_duration_ms = 0
    try:
        # Используем путь из Config для relative_to
        relative_path = original_audio_path.relative_to(Config.AUDIO_INPUT_DIR)
    except ValueError:
        print(f"\nОШИБКА: Не удалось определить относительный путь для {original_audio_path} относительно {Config.AUDIO_INPUT_DIR}. Пропускаем.")
        return "error_relative_path"

    print(f"\nПроверка: {relative_path}")

    try:
        print(f"  Получение длительности оригинала...")
        audio_info = AudioSegment.from_file(original_audio_path)
        original_duration_ms = len(audio_info)
        duration_sec = original_duration_ms / 1000.0
        print(f"  Оригинальная длительность: {duration_sec:.3f} сек ({original_duration_ms} мс).")

        # Используем лимит и путь для пропуска из Config
        if duration_sec > Config.AUDIO_MAX_DURATION_SECONDS:
            print(f"  ПРЕВЫШЕНИЕ ЛИМИТА ({Config.AUDIO_MAX_DURATION_SECONDS:.1f} сек). Перемещение...")
            skipped_long_output_path = Config.AUDIO_SKIPPED_LONG_DIR / relative_path
            skipped_long_output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                # Перемещаем исходный файл
                shutil.move(str(original_audio_path), str(skipped_long_output_path))
                print(f"  Файл перемещен в: {skipped_long_output_path}")
                return "skipped_long"
            except Exception as move_err:
                print(f"  ОШИБКА при перемещении файла: {move_err}")
                # Важно вернуть ошибку, чтобы не продолжать обработку несуществующего файла
                return "error_move_failed"

    except FileNotFoundError:
         # Эта ошибка может возникнуть, если файл был перемещен в предыдущем блоке
         # или если он изначально отсутствовал.
         print(f"  ОШИБКА: Исходный файл не найден для получения длительности/обработки: {original_audio_path}")
         return "error_original_not_found"
    except pydub.exceptions.CouldntDecodeError:
         print(f"  ОШИБКА pydub: Не удалось прочитать длительность оригинала: {original_audio_path.name}")
         return "error_duration_read"
    except Exception as dur_err:
        print(f"  ОШИБКА при получении длительности оригинала: {dur_err}")
        return "error_duration_generic"

    # Определяем путь конечного файла, используя Config
    final_output_path = (Config.AUDIO_OUTPUT_DIR / relative_path).with_suffix('.wav')
    print(f"  -> Конечный обработанный файл: {final_output_path}")
    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    if final_output_path.exists():
        print(f"  Пропуск: Обработанный файл {final_output_path.name} уже существует.")
        return "skipped_exists" # Изменил статус для ясности

    temp_ai_output_path, ai_error_code = run_ai_processing(original_audio_path)
    if ai_error_code:
        return f"error_ai_{ai_error_code}"
    if not temp_ai_output_path or not temp_ai_output_path.exists():
        print("  Критическая ошибка: AI не вернул путь/файл, но и не код ошибки.")
        return "error_internal_ai_path"

    trim_success, trim_error_code = trim_to_duration(
        temp_ai_output_path,
        original_duration_ms,
        final_output_path
    )

    try:
        print(f"  Удаление временного файла AI: {temp_ai_output_path}")
        temp_ai_output_path.unlink()
    except OSError as e:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить временный файл {temp_ai_output_path.name}: {e}")

    if not trim_success:
        return f"error_trim_{trim_error_code}"

    # Используем паузу из Config (API_PAUSE_DURATION)
    if Config.API_PAUSE_DURATION > 0:
        print(f"  Пауза {Config.API_PAUSE_DURATION} сек...")
        time.sleep(Config.API_PAUSE_DURATION)

    return "success"

def print_summary_report(total_files, status_counts):
    """Печатает отчет, используя пути и лимиты из Config."""
    print("\n--- Скрипт Завершен ---")
    print(f"Всего найдено аудиофайлов для проверки/обработки: {total_files}")
    print(f"Успешно обработано (AI + Обрезка до оригинала): {status_counts.get('success', 0)}")
    print(f"Пропущено (обработанный файл уже существовал): {status_counts.get('skipped_exists', 0)}")
    # Используем лимит и пути из Config в сообщении
    print(f"Пропущено (длительность > {Config.AUDIO_MAX_DURATION_SECONDS:.1f} сек, перемещены): {status_counts.get('skipped_long', 0)}")

    # Логика подсчета и вывода ошибок остается прежней
    errors_total = sum(v for k, v in status_counts.items() if k.startswith("error_"))
    print(f"Возникло ошибок при обработке/проверке: {errors_total}")
    if errors_total > 0:
        print("  Детали ошибок:")
        error_summary = {}
        for status, count in status_counts.items():
            if status.startswith("error_"):
                parts = status.split('_')
                error_type = parts[1].upper()
                error_code = '_'.join(parts[2:]) if len(parts) > 2 else "general"
                key = f"Ошибка {error_type}" + (f" ({error_code})" if error_code != "general" else "")
                error_summary[key] = error_summary.get(key, 0) + count
        for error_desc, count in sorted(error_summary.items()):
            print(f"    - {error_desc}: {count} раз")
        print("  Просмотрите лог выше для подробной информации по каждому файлу.")

    # Используем пути из Config в итоговых сообщениях
    print(f"\nОбработанные файлы сохранены в: {Config.AUDIO_OUTPUT_DIR}")
    print(f"Слишком длинные файлы перемещены в: {Config.AUDIO_SKIPPED_LONG_DIR}")
    print("Не забудь остановить процесс 'python app.py', если он больше не нужен.")

def check_dependencies():
    """Проверяет наличие необходимых библиотек (без изменений)."""
    print("Проверка зависимостей...")
    ok = True
    try: import gradio_client; print("  [OK] gradio_client")
    except ImportError: print("  [ОШИБКА] gradio_client не найден. Установите: pip install gradio_client"); ok = False
    try:
        import pydub; print("  [OK] pydub")
        try:
            AudioSegment.silent(duration=10)
            print("  [OK] FFmpeg/avconv (предположительно) доступен для pydub.")
        except Exception as e:
             print(f"  [ПРЕДУПРЕЖДЕНИЕ] pydub не смог выполнить базовую операцию. Убедитесь, что FFmpeg/avconv установлен и в PATH. Ошибка: {e}")
    except ImportError: print("  [ОШИБКА] pydub не найден. Установите: pip install pydub"); ok = False
    return ok

# --- Точка входа ---
if __name__ == "__main__":
    if not check_dependencies():
        print("\nРабота скрипта прервана из-за отсутствия зависимостей.")
        sys.exit(1)

    print("\n--- Скрипт Автоматической Обработки Аудио (из Config) ---")
    # Используем параметры из Config для вывода информации
    print(f"Исходные файлы из: {Config.AUDIO_INPUT_DIR}")
    print(f"Результаты в:      {Config.AUDIO_OUTPUT_DIR}")
    print(f"Слишком длинные (> {Config.AUDIO_MAX_DURATION_SECONDS:.1f} сек) в: {Config.AUDIO_SKIPPED_LONG_DIR}")
    print(f"Обработка AI через: {Config.AUDIO_GRADIO_APP_URL} (эндпоинт: {Config.AUDIO_API_NAME})")
    print(f"Параметры AI: Model='{Config.AUDIO_MODEL_NAME}', Guidance={Config.AUDIO_GUIDANCE_SCALE}, Steps={Config.AUDIO_DDIM_STEPS}, Seed={Config.AUDIO_SEED}")
    print("-" * 50)
    print("ВАЖНО: Убедись, что 'python app.py' запущен!")
    print(f"ВАЖНО: Убедись, что FFmpeg/avconv установлен и доступен!")
    input("Нажми Enter для начала обработки...")

    setup_directories()
    original_audio_files = find_audio_files()
    if not original_audio_files:
        print("\nНе найдено аудиофайлов для обработки.")
        sys.exit(0)
    if not initialize_gradio_client():
        sys.exit("Не удалось подключиться к Gradio.")

    print("\n4. Начало проверки и обработки аудиофайлов...")
    status_counts = {}
    total_files = len(original_audio_files) # Сохраним общее число для отчета
    for i, audio_path in enumerate(original_audio_files):
        print(f"\n>>> Обработка файла {i+1}/{total_files}: {audio_path.name} <<<") # Добавил прогресс
        if not audio_path.exists():
            print(f"Пропуск: Исходный файл {audio_path.name} не найден (возможно, был перемещен?).")
            status = "skipped_original_missing" # Новый статус
        else:
            status = process_single_audio(audio_path)
        status_counts[status] = status_counts.get(status, 0) + 1
        print(f">>> Статус файла {audio_path.name}: {status} <<<") # Добавил вывод статуса

    print_summary_report(total_files, status_counts)