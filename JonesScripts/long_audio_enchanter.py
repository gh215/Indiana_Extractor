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

gradio_client = None

def initialize_gradio_client():
    global gradio_client
    # Используем настройки для ОБЩЕГО Gradio AI
    print(f"\n{'(Пере)подключение' if gradio_client else 'Подключение'} к локальному Gradio приложению: {Config.GENERAL_AUDIO_GRADIO_APP_URL}...")
    try:
        gradio_client = Client(Config.GENERAL_AUDIO_GRADIO_APP_URL, verbose=False)
        print("   Подключение успешно. Убедись, что app.py запущен!")
        return True
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к {Config.GENERAL_AUDIO_GRADIO_APP_URL}. Ошибка: {e}")
        gradio_client = None
        return False

def run_ai_processing(input_audio_path):
    global gradio_client
    temp_result_path_str = None
    print(f"    Отправка {input_audio_path.name} на обработку AI...")
    # Используем параметры для ОБЩЕГО Gradio AI
    print(f"    Параметры: Model='{Config.GENERAL_AUDIO_MODEL_NAME}', Guidance={Config.GENERAL_AUDIO_GUIDANCE_SCALE}, Steps={Config.GENERAL_AUDIO_DDIM_STEPS}, Seed={Config.GENERAL_AUDIO_SEED}")
    start_time = time.time()
    try:
        api_result = gradio_client.predict(
            handle_file(str(input_audio_path.resolve())),
            Config.GENERAL_AUDIO_MODEL_NAME,
            Config.GENERAL_AUDIO_GUIDANCE_SCALE,
            Config.GENERAL_AUDIO_DDIM_STEPS,
            Config.GENERAL_AUDIO_SEED,
            api_name=Config.GENERAL_AUDIO_API_ENDPOINT_NAME # Используем имя эндпоинта
        )
        end_time = time.time()
        print(f"    Обработка AI завершена за {end_time - start_time:.2f} сек.")

        if isinstance(api_result, str) and api_result:
            if os.path.exists(api_result): temp_result_path_str = api_result
            else: print(f"    ОШИБКА: API вернул путь '{api_result}', но файл не найден."); return None, "api_file_not_found"
        elif api_result is None: print(f"    ОШИБКА: API вернул None."); return None, "api_returned_none"
        else: print(f"    ОШИБКА: API вернул неожиданный результат типа {type(api_result)}: {api_result}"); return None, "api_unexpected_result_type"
        if not temp_result_path_str: print(f"    ОШИБКА: Не удалось получить путь к результату от API."); return None, "api_path_processing_failed"

        print(f"    AI создал временный файл: {temp_result_path_str}")
        return Path(temp_result_path_str), None
    except Exception as e:
        print(f"    ОШИБКА при взаимодействии с API {Config.GENERAL_AUDIO_GRADIO_APP_URL} ({Config.GENERAL_AUDIO_API_ENDPOINT_NAME}): {e}")
        print("    Попытка переподключения к Gradio...")
        time.sleep(2)
        if not initialize_gradio_client(): print("    КРИТИЧЕСКАЯ ОШИБКА: Не удалось переподключиться к Gradio."); return None, "api_reconnect_failed"
        else: print("    Переподключение успешно, но текущий файл пропущен из-за предыдущей ошибки."); return None, "api_error_needs_retry"

def trim_to_duration(processed_audio_path, target_duration_ms, final_output_path):
    # Логика этой функции не зависит от Config напрямую, она получает все через параметры
    # Поэтому оставляем ее как есть
    try:
        print(f"    Обрезка/выравнивание AI-файла до {target_duration_ms / 1000.0:.3f} сек...")
        file_format = processed_audio_path.suffix.lower().replace('.', '')
        if file_format == 'ogg': file_format = 'oga'
        elif not file_format: file_format = 'wav' # по умолчанию

        if not processed_audio_path.exists():
            print(f"    ОШИБКА: Файл для обрезки не найден: {processed_audio_path}")
            return False, "trim_file_not_found_before_load"

        processed_audio = AudioSegment.from_file(processed_audio_path, format=file_format)
        processed_duration_ms = len(processed_audio)

        if processed_duration_ms > target_duration_ms:
            trimmed_audio = processed_audio[:target_duration_ms]
            print(f"    Файл обрезан с {processed_duration_ms} мс до {len(trimmed_audio)} мс.")
        elif processed_duration_ms < target_duration_ms:
            needed_silence_ms = target_duration_ms - processed_duration_ms
            print(f"    ПРЕДУПРЕЖДЕНИЕ: AI-файл ({processed_duration_ms} мс) короче цели ({target_duration_ms} мс). Добавляем {needed_silence_ms} мс тишины.")
            padding = AudioSegment.silent(duration=needed_silence_ms)
            trimmed_audio = processed_audio + padding
        else:
            trimmed_audio = processed_audio
            print(f"    Длительность AI-файла ({processed_duration_ms} мс) уже совпадает с целью.")

        output_format = final_output_path.suffix.lower().replace('.', '')
        if not output_format: output_format = 'wav' # по умолчанию
        print(f"    Сохранение результата в: {final_output_path} (формат: {output_format})")
        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        trimmed_audio.export(final_output_path, format=output_format)
        return True, None

    except FileNotFoundError:
        print(f"    ОШИБКА: Файл не найден при попытке обрезки: {processed_audio_path}")
        return False, "trim_file_not_found"
    except pydub.exceptions.CouldntDecodeError:
        print(f"    ОШИБКА pydub: Не удалось декодировать файл {processed_audio_path} для обрезки.")
        return False, "trim_decode_error"
    except Exception as e:
        print(f"    ОШИБКА: Не удалось обрезать/выровнять или сохранить файл {final_output_path.name}: {e}")
        if final_output_path.exists():
            try: final_output_path.unlink()
            except OSError: pass
        return False, "trim_error"

def setup_directories():
    print("\n1. Проверка/создание папок для длинных файлов...")
    # Используем пути для длинных и временных файлов из Config
    # Эти пути я назвал GENERAL_... в конфиге, т.к. они кажутся общими для этого типа обработки
    dirs_to_check = {
        "Исходные (длинные)": Config.GENERAL_AUDIO_SKIPPED_LONG_DIR, # В конфиге это теперь общая папка для "пропущенных длинных"
        "Результаты (длинные)": Config.GENERAL_AUDIO_OUTPUT_LONG_DIR,
        "Временные (чанки)": Config.GENERAL_AUDIO_TEMP_CHUNK_DIR
    }
    all_ok = True
    for desc, dir_path in dirs_to_check.items():
        if desc == "Исходные (длинные)":
            if not dir_path.is_dir():
                print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка '{desc}' ({dir_path}) не найдена! Этот скрипт ожидает, что она существует и содержит файлы.")
                all_ok = False
            else:
                print(f"   Папка '{desc}': {dir_path} [Найдена]")
        else:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"   Папка '{desc}': {dir_path} [OK/Создана]")
                if dir_path == Config.GENERAL_AUDIO_TEMP_CHUNK_DIR: # Очищаем временную папку
                    print(f"   Очистка временной папки: {dir_path}")
                    for item in dir_path.iterdir():
                        if item.is_dir(): shutil.rmtree(item)
                        else: item.unlink()
            except Exception as e:
                print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось создать/очистить папку '{desc}' ({dir_path}): {e}")
                all_ok = False
    if not all_ok:
        sys.exit("Ошибка при подготовке директорий. Скрипт остановлен.")
    print("   Папки проверены/созданы/очищены.")

def find_long_audio_files():
    print("\n2. Поиск аудиофайлов для обработки (из папки длинных)...")
    audio_files = []
    # Используем путь GENERAL_AUDIO_SKIPPED_LONG_DIR и общие расширения SUPPORTED_AUDIO_EXTENSIONS
    for ext in Config.SUPPORTED_AUDIO_EXTENSIONS: # Общие расширения
        audio_files.extend(list(Config.GENERAL_AUDIO_SKIPPED_LONG_DIR.rglob(f"*{ext}")))
        # rglob по умолчанию регистронезависим в Windows, но для кроссплатформенности можно добавить upper()
        # audio_files.extend(list(Config.GENERAL_AUDIO_SKIPPED_LONG_DIR.rglob(f"*{ext.upper()}")))
    unique_audio_files = sorted(list(set(audio_files))) # Удаляем дубликаты, если .rglob сработало дважды на одно и то же
    if not unique_audio_files:
        print(f"   Не найдено аудиофайлов с расширениями {Config.SUPPORTED_AUDIO_EXTENSIONS} в {Config.GENERAL_AUDIO_SKIPPED_LONG_DIR}.")
        return []
    print(f"   Найдено {len(unique_audio_files)} аудиофайлов для обработки или проверки.")
    return unique_audio_files

def split_audio(original_audio_path: Path, temp_work_dir: Path) -> list[tuple[Path, int]] | None:
    print("  Нарезка файла на части...")
    try:
        audio = AudioSegment.from_file(original_audio_path)
        total_ms = len(audio)
        # Используем параметры нарезки из Config
        target_chunk_ms = int(Config.GENERAL_AUDIO_TARGET_CHUNK_SECONDS * 1000)
        split_decision_threshold_ms = int(Config.GENERAL_AUDIO_SPLIT_THRESHOLD_SECONDS * 1000)
        min_chunk_ms = int(Config.GENERAL_AUDIO_MIN_CHUNK_SECONDS * 1000)

        chunk_definitions = []
        start_ms = 0
        while (total_ms - start_ms) > split_decision_threshold_ms:
             if start_ms + target_chunk_ms <= total_ms:
                 end_ms = start_ms + target_chunk_ms
                 chunk_definitions.append((start_ms, end_ms))
                 start_ms = end_ms
             else:
                 break
        if start_ms < total_ms:
            chunk_definitions.append((start_ms, total_ms))

        print(f"  Файл будет разделен на {len(chunk_definitions)} частей.")
        if not chunk_definitions and total_ms > 0 : # Если файл есть, но нарезать не получилось (например, короче порога)
            print("  Файл не будет разделен, т.к. его длина меньше или равна порогу нарезки, но больше 0.")
            # Это не ошибка, просто файл будет обработан целиком позже, но split_audio должен вернуть что-то
            # Если эта функция вызывается только для файлов длиннее порога, то этот блок не нужен.
            # По логике process_single_long_audio, split_audio вызывается только для длинных.
            # Так что если список пуст - это может быть проблемой в логике нарезки или очень специфичный случай.
            # Однако, если файл был > split_decision_threshold_ms, но после первого куска остаток стал < target_chunk_ms,
            # и этот остаток не добавился, то здесь может быть пустой список.
            # Логика `if start_ms < total_ms: chunk_definitions.append((start_ms, total_ms))` должна это покрывать.

        output_chunks_info = []
        for i, (start, end) in enumerate(chunk_definitions):
            chunk_duration_ms = end - start
            if chunk_duration_ms < min_chunk_ms:
                 print(f"  ПРЕДУПРЕЖДЕНИЕ: Чанк {i} ({chunk_duration_ms} мс) короче минимально допустимой длины ({min_chunk_ms} мс). Проверьте логику или настройки.")
            chunk = audio[start:end]
            chunk_filename = temp_work_dir / f"chunk_{i:03d}_orig_{chunk_duration_ms}ms.wav" # Сохраняем в wav
            print(f"    Сохранение оригинального чанка {i}: {chunk_filename.name} ({chunk_duration_ms / 1000.0:.3f} сек)")
            chunk.export(chunk_filename, format="wav")
            output_chunks_info.append((chunk_filename, chunk_duration_ms))

        if not output_chunks_info and total_ms > 0: # Если файл был, но чанков нет
            print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось создать чанки для файла {original_audio_path.name}, хотя его длина {total_ms} мс.")
            return None # Сигнализируем об ошибке

        return output_chunks_info

    except FileNotFoundError: print(f"  ОШИБКА: Исходный файл не найден для нарезки: {original_audio_path}"); return None
    except pydub.exceptions.CouldntDecodeError: print(f"  ОШИБКА pydub: Не удалось декодировать файл {original_audio_path} для нарезки."); return None
    except Exception as e: print(f"  ОШИБКА при нарезке файла {original_audio_path.name}: {e}"); return None

def merge_chunks(processed_chunk_paths: list[Path], final_output_path: Path) -> bool:
    # Логика этой функции не зависит от Config, оставляем как есть
    print(f"  Склейка {len(processed_chunk_paths)} частей в {final_output_path.name}...")
    if not processed_chunk_paths:
        print("  ОШИБКА: Нет частей для склейки.")
        return False
    try:
        merged_audio = AudioSegment.empty()
        for i, chunk_path in enumerate(processed_chunk_paths):
            if not chunk_path.exists():
                print(f"  ОШИБКА: Обработанный чанк не найден: {chunk_path}")
                return False
            print(f"    Добавление чанка {i}: {chunk_path.name}")
            # Определяем формат чанка по расширению, если это не wav (хотя мы сохраняем в wav)
            chunk_format = chunk_path.suffix.lower().replace('.', '')
            if not chunk_format: chunk_format = 'wav'
            chunk_audio = AudioSegment.from_file(chunk_path, format=chunk_format)
            merged_audio += chunk_audio

        print(f"  Сохранение склеенного файла: {final_output_path}")
        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        # Определяем формат выходного файла по расширению
        output_format = final_output_path.suffix.lower().replace('.', '')
        if not output_format: output_format = 'wav' # По умолчанию wav, если расширение не указано
        merged_audio.export(final_output_path, format=output_format)
        print("  Склейка и сохранение успешно завершены.")
        return True
    except FileNotFoundError:
        print(f"  КРИТИЧЕСКАЯ ОШИБКА: Файл чанка исчез во время склейки.")
        return False
    except pydub.exceptions.CouldntDecodeError:
        print(f"  ОШИБКА pydub: Не удалось декодировать один из чанков для склейки.")
        return False
    except Exception as e:
        print(f"  ОШИБКА при склейке или сохранении файла {final_output_path.name}: {e}")
        if final_output_path.exists():
            try: final_output_path.unlink()
            except OSError: pass
        return False

def process_single_long_audio(original_audio_path: Path):
    try:
        # Используем GENERAL_AUDIO_SKIPPED_LONG_DIR
        relative_path = original_audio_path.relative_to(Config.GENERAL_AUDIO_SKIPPED_LONG_DIR)
    except ValueError:
        print(f"\nОШИБКА: Не удалось определить относительный путь для {original_audio_path} относительно {Config.GENERAL_AUDIO_SKIPPED_LONG_DIR}. Пропускаем.")
        return "error_relative_path"

    print(f"\n--- Обработка файла: {relative_path} ---")
    # Используем GENERAL_AUDIO_OUTPUT_LONG_DIR
    final_output_path = (Config.GENERAL_AUDIO_OUTPUT_LONG_DIR / relative_path).with_suffix('.wav') # Результат всегда wav

    if final_output_path.exists():
        print(f"  Пропуск: Финальный файл {final_output_path.name} уже существует.")
        return "skipped_exists"

    original_duration_ms = 0
    try:
        print(f"  Получение длительности оригинала...")
        # Определяем формат входного файла по расширению
        input_format = original_audio_path.suffix.lower().replace('.', '')
        if not input_format : input_format = None # pydub сам определит
        audio_info = AudioSegment.from_file(original_audio_path, format=input_format)
        original_duration_ms = len(audio_info)
        duration_sec = original_duration_ms / 1000.0
        print(f"  Оригинальная длительность: {duration_sec:.3f} сек ({original_duration_ms} мс).")
    except FileNotFoundError: print(f"  ОШИБКА: Исходный файл не найден: {original_audio_path}"); return "error_original_not_found"
    except pydub.exceptions.CouldntDecodeError: print(f"  ОШИБКА pydub: Не удалось прочитать длительность: {original_audio_path.name}"); return "error_duration_read"
    except Exception as dur_err: print(f"  ОШИБКА при получении длительности: {dur_err}"); return "error_duration_generic"

    # Используем GENERAL_AUDIO_TEMP_CHUNK_DIR
    temp_work_dir = Config.GENERAL_AUDIO_TEMP_CHUNK_DIR / original_audio_path.stem
    try:
        temp_work_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e: print(f"  КРИТИЧЕСКАЯ ОШИБКА: Не удалось создать временную папку {temp_work_dir}: {e}"); return "error_temp_dir_create"

    status_code = "unknown_error"
    try:
        # Используем GENERAL_AUDIO_SPLIT_THRESHOLD_SECONDS
        if duration_sec <= Config.GENERAL_AUDIO_SPLIT_THRESHOLD_SECONDS:
            print(f"  Файл короче или равен {Config.GENERAL_AUDIO_SPLIT_THRESHOLD_SECONDS:.1f} сек. Обработка целиком...")
            temp_ai_output_path, ai_error_code = run_ai_processing(original_audio_path)
            if ai_error_code: status_code = f"error_ai_{ai_error_code}"; raise Exception(status_code) # Поднимаем исключение для блока finally
            if not temp_ai_output_path or not temp_ai_output_path.exists(): status_code = "error_internal_ai_path"; raise Exception(status_code)

            trim_success, trim_error_code = trim_to_duration(temp_ai_output_path, original_duration_ms, final_output_path)
            if temp_ai_output_path.exists(): # Проверяем перед удалением
                try: temp_ai_output_path.unlink()
                except OSError as e: print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить временный AI файл {temp_ai_output_path.name}: {e}")
            if not trim_success: status_code = f"error_trim_{trim_error_code}"; raise Exception(status_code)

            print(f"  Успешная обработка (целиком): {final_output_path.name}")
            status_code = "success_direct"
        else:
            print(f"  Файл длиннее {Config.GENERAL_AUDIO_SPLIT_THRESHOLD_SECONDS:.1f} сек. Требуется нарезка.")
            original_chunks_info = split_audio(original_audio_path, temp_work_dir)
            if original_chunks_info is None or not original_chunks_info: # Проверяем что список не пустой
                status_code = "error_split_no_chunks"; raise Exception(status_code)

            processed_trimmed_chunks = []
            all_chunks_processed = True
            for i, (orig_chunk_path, orig_chunk_duration_ms) in enumerate(original_chunks_info):
                print(f"\n  --- Обработка чанка {i+1}/{len(original_chunks_info)} ({orig_chunk_path.name}) ---")
                temp_ai_chunk_path, ai_error_code = run_ai_processing(orig_chunk_path)
                if ai_error_code: print(f"    ОШИБКА AI чанка {i}."); status_code = f"error_chunk_ai_{ai_error_code}"; all_chunks_processed = False; break
                if not temp_ai_chunk_path or not temp_ai_chunk_path.exists(): print(f"    КРИТ ОШИБКА AI: нет пути чанка {i}."); status_code = "error_chunk_ai_path"; all_chunks_processed = False; break

                trimmed_chunk_path = temp_work_dir / f"chunk_{i:03d}_processed_trimmed.wav" # Сохраняем в wav
                trim_success, trim_error_code = trim_to_duration(temp_ai_chunk_path, orig_chunk_duration_ms, trimmed_chunk_path)
                if temp_ai_chunk_path.exists(): # Проверяем перед удалением
                    try: temp_ai_chunk_path.unlink()
                    except OSError as e: print(f"      ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить временный AI файл чанка {temp_ai_chunk_path.name}: {e}")

                if not trim_success: print(f"    ОШИБКА обрезки чанка {i}."); status_code = f"error_chunk_trim_{trim_error_code}"; all_chunks_processed = False; break
                processed_trimmed_chunks.append(trimmed_chunk_path)
                print(f"  --- Чанк {i+1}/{len(original_chunks_info)} успешно обработан ---")

                # Используем ОБЩУЮ паузу API
                if Config.GENERAL_AUDIO_API_PAUSE_DURATION_SECONDS > 0 and i < len(original_chunks_info) - 1:
                   print(f"    Пауза {Config.GENERAL_AUDIO_API_PAUSE_DURATION_SECONDS} сек...")
                   time.sleep(Config.GENERAL_AUDIO_API_PAUSE_DURATION_SECONDS)

            if not all_chunks_processed:
                 print(f"\n  Обработка файла {original_audio_path.name} прервана из-за ошибки чанка.")
                 # status_code уже установлен
                 raise Exception(status_code) # Для блока finally
            else:
                print(f"\n  Все {len(processed_trimmed_chunks)} частей '{original_audio_path.name}' обработаны.")
                print(f"  ---> Временные файлы в: {temp_work_dir}")
                print("\n  Обработанные части для склейки:")
                [print(f"    - {p.name}") for p in processed_trimmed_chunks]

                print(f"\n  Автоматическая склейка {len(processed_trimmed_chunks)} частей...")
                merge_success = merge_chunks(processed_trimmed_chunks, final_output_path)
                if merge_success:
                    print(f"  Успешно склеено: {final_output_path.name}")
                    status_code = "success_merged"
                else:
                    print(f"  Ошибка склейки для {original_audio_path.name}.")
                    status_code = "error_merge"
                    raise Exception(status_code) # Для блока finally

    except Exception as e: # Этот блок перехватит исключения из try
        if status_code == "unknown_error": # Если ошибка не была классифицирована ранее
            print(f"  НЕПРЕДВИДЕННАЯ ОШИБКА файла {original_audio_path.name}: {e}")
            status_code = "error_unexpected"
        # Если status_code уже был установлен (например, error_ai_api_file_not_found), он сохранится
    finally:
        if temp_work_dir.exists():
            try:
                print(f"\n  Очистка временной папки: {temp_work_dir}")
                shutil.rmtree(temp_work_dir)
            except Exception as e_clean:
                print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось очистить {temp_work_dir}: {e_clean}")
    return status_code

def print_summary_report(total_files, status_counts):
    print("\n--- Скрипт Обработки Длинных Аудио Завершен ---")
    print(f"Всего найдено аудиофайлов для проверки/обработки: {total_files}")
    print("-" * 30)
    print("Успешно обработано:")
    print(f"  - Целиком (<= {Config.GENERAL_AUDIO_SPLIT_THRESHOLD_SECONDS:.1f} сек): {status_counts.get('success_direct', 0)}")
    print(f"  - Склеено из частей (> {Config.GENERAL_AUDIO_SPLIT_THRESHOLD_SECONDS:.1f} сек): {status_counts.get('success_merged', 0)}")
    print("-" * 30)
    print("Пропущено:")
    print(f"  - Финальный файл уже существовал: {status_counts.get('skipped_exists', 0)}")
    print(f"  - Исходный файл отсутствовал при начале обработки: {status_counts.get('skipped_original_missing',0)}") # Новый статус
    print("-" * 30)

    errors_total = sum(v for k, v in status_counts.items() if k.startswith("error_"))
    print(f"Возникло ошибок при обработке/проверке: {errors_total}")
    if errors_total > 0:
        print("  Детали ошибок:")
        error_summary = {}
        for status, count in status_counts.items():
             if status.startswith("error_"):
                parts = status.split('_', 2) # Разделяем максимум на 3 части: error, type, code
                etype = parts[1].upper() if len(parts) > 1 else "UNKNOWN_ERROR_TYPE"
                ecode = parts[2] if len(parts) > 2 else "general"
                if etype == "CHUNK":
                    sub_parts = ecode.split('_', 1)
                    etype = f"CHUNK_{sub_parts[0].upper()}" if len(sub_parts) > 0 else "CHUNK_UNKNOWN"
                    ecode = sub_parts[1] if len(sub_parts) > 1 else "general"
                key = f"Ошибка {etype}" + (f" ({ecode})" if ecode != "general" else "")
                error_summary[key] = error_summary.get(key, 0) + count
        for error_desc, count in sorted(error_summary.items()): print(f"    - {error_desc}: {count} раз")
        print("  Просмотрите лог выше для подробной информации по каждому файлу.")
    print("-" * 30)
    print(f"Обработанные файлы сохранены в: {Config.GENERAL_AUDIO_OUTPUT_LONG_DIR}")
    print(f"Временные файлы создавались в: {Config.GENERAL_AUDIO_TEMP_CHUNK_DIR} (должна быть пустой)")
    print("Не забудь остановить процесс 'python app.py', если он больше не нужен.")

def check_dependencies():
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
    if not check_dependencies(): print("\nРабота прервана из-за зависимостей."); sys.exit(1)

    print("\n--- Скрипт Обработки ДЛИННЫХ Аудио (из Config) ---")
    print(f"Исходные файлы из папки для пропущенных длинных: {Config.GENERAL_AUDIO_SKIPPED_LONG_DIR}")
    print(f"Результаты в:      {Config.GENERAL_AUDIO_OUTPUT_LONG_DIR}")
    print(f"Временные чанки в: {Config.GENERAL_AUDIO_TEMP_CHUNK_DIR} (будет очищена)")
    print(f"Порог для нарезки: {Config.GENERAL_AUDIO_SPLIT_THRESHOLD_SECONDS:.1f} сек")
    print(f"Целевая длина чанка: {Config.GENERAL_AUDIO_TARGET_CHUNK_SECONDS:.1f} сек")
    print(f"Мин. длина чанка (инфо): {Config.GENERAL_AUDIO_MIN_CHUNK_SECONDS:.1f} сек")
    print(f"Обработка AI через: {Config.GENERAL_AUDIO_GRADIO_APP_URL} (эндпоинт: {Config.GENERAL_AUDIO_API_ENDPOINT_NAME})")
    print(f"Параметры AI: Model='{Config.GENERAL_AUDIO_MODEL_NAME}', Guidance={Config.GENERAL_AUDIO_GUIDANCE_SCALE}, Steps={Config.GENERAL_AUDIO_DDIM_STEPS}, Seed={Config.GENERAL_AUDIO_SEED}")
    print(f"Пауза между API вызовами (для чанков): {Config.GENERAL_AUDIO_API_PAUSE_DURATION_SECONDS} сек")
    print("-" * 50)
    print("ВАЖНО: Убедись, что 'python app.py' (локальный Gradio сервер) запущен!")
    print(f"ВАЖНО: Убедись, что FFmpeg/avconv установлен и доступен в системном PATH!")
    input("Нажми Enter для начала обработки...")

    setup_directories()
    long_audio_files_to_process = find_long_audio_files()
    if not long_audio_files_to_process: print("\nНет файлов для обработки."); sys.exit(0)
    if not initialize_gradio_client(): sys.exit("Не удалось подключиться к Gradio.")

    print("\n4. Начало проверки и обработки аудиофайлов...")
    status_counts = {}
    total_files = len(long_audio_files_to_process)
    for i, audio_path in enumerate(long_audio_files_to_process):
        print(f"\n>>> Обработка файла {i+1}/{total_files}: {audio_path.name} <<<")
        if not audio_path.exists(): # Дополнительная проверка перед вызовом основной функции
            print(f"Пропуск: Исходный файл {audio_path.name} не найден перед вызовом process_single_long_audio.")
            status = "skipped_original_missing"
        else:
            status = process_single_long_audio(audio_path)
        status = status if status else "error_unknown_status_returned" # Гарантируем, что статус не None
        status_counts[status] = status_counts.get(status, 0) + 1
        print(f">>> Статус файла {audio_path.name}: {status} <<<")

    print_summary_report(total_files, status_counts)