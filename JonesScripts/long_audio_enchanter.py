import sys
import time
import os
import shutil
from pathlib import Path
from gradio_client import Client, handle_file
from pydub import AudioSegment
import pydub.exceptions
import math
from conf import Config # Предполагаем, что conf.py находится рядом

gradio_client = None

def initialize_gradio_client():
    """Инициализирует клиент Gradio, используя URL из Config."""
    global gradio_client
    print(f"\n{'(Пере)подключение' if gradio_client else 'Подключение'} к локальному Gradio приложению: {Config.AUDIO_GRADIO_APP_URL}...")
    try:
        gradio_client = Client(Config.AUDIO_GRADIO_APP_URL, verbose=False)
        print("   Подключение успешно. Убедись, что app.py запущен!")
        return True
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к {Config.AUDIO_GRADIO_APP_URL}. Ошибка: {e}")
        gradio_client = None
        return False

def run_ai_processing(input_audio_path):
    """Запускает обработку AI, используя параметры из Config."""
    global gradio_client
    temp_result_path_str = None
    print(f"    Отправка {input_audio_path.name} на обработку AI...")
    print(f"    Параметры: Model='{Config.AUDIO_MODEL_NAME}', Guidance={Config.AUDIO_GUIDANCE_SCALE}, Steps={Config.AUDIO_DDIM_STEPS}, Seed={Config.AUDIO_SEED}")
    start_time = time.time()
    try:
        # Убедимся, что передаем абсолютный путь в виде строки
        api_result = gradio_client.predict(
            handle_file(str(input_audio_path.resolve())),
            Config.AUDIO_MODEL_NAME,
            Config.AUDIO_GUIDANCE_SCALE,
            Config.AUDIO_DDIM_STEPS,
            Config.AUDIO_SEED,
            api_name=Config.AUDIO_API_NAME
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
        print(f"    ОШИБКА при взаимодействии с API {Config.AUDIO_GRADIO_APP_URL} ({Config.AUDIO_API_NAME}): {e}")
        print("    Попытка переподключения к Gradio...")
        time.sleep(2)
        if not initialize_gradio_client(): print("    КРИТИЧЕСКАЯ ОШИБКА: Не удалось переподключиться к Gradio."); return None, "api_reconnect_failed"
        else: print("    Переподключение успешно, но текущий файл пропущен из-за предыдущей ошибки."); return None, "api_error_needs_retry"

def trim_to_duration(processed_audio_path, target_duration_ms, final_output_path):
    """Обрезает/выравнивает аудио. Логика не меняется."""
    try:
        print(f"    Обрезка/выравнивание AI-файла до {target_duration_ms / 1000.0:.3f} сек...")
        file_format = processed_audio_path.suffix.lower().replace('.', '')
        if file_format == 'ogg': file_format = 'oga'
        elif not file_format: file_format = 'wav'

        if not processed_audio_path.exists(): print(f"    ОШИБКА: Файл для обрезки не найден: {processed_audio_path}"); return False, "trim_file_not_found_before_load"

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
        if not output_format: output_format = 'wav'
        print(f"    Сохранение результата в: {final_output_path} (формат: {output_format})")
        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        trimmed_audio.export(final_output_path, format=output_format)
        return True, None

    except FileNotFoundError: print(f"    ОШИБКА: Файл не найден при попытке обрезки: {processed_audio_path}"); return False, "trim_file_not_found"
    except pydub.exceptions.CouldntDecodeError: print(f"    ОШИБКА pydub: Не удалось декодировать файл {processed_audio_path} для обрезки."); return False, "trim_decode_error"
    except Exception as e:
        print(f"    ОШИБКА: Не удалось обрезать/выровнять или сохранить файл {final_output_path.name}: {e}")
        if final_output_path.exists():
            try: final_output_path.unlink()
            except OSError: pass
        return False, "trim_error"

def setup_directories():
    """Проверяет и создает директории для длинных файлов из Config."""
    print("\n1. Проверка/создание папок для длинных файлов...")
    # Используем пути для длинных и временных файлов из Config
    dirs_to_check = {
        "Исходные (длинные)": Config.AUDIO_SKIPPED_LONG_DIR,
        "Результаты (длинные)": Config.AUDIO_OUTPUT_LONG_DIR,
        "Временные (чанки)": Config.AUDIO_TEMP_CHUNK_DIR
    }
    all_ok = True
    for desc, dir_path in dirs_to_check.items():
        if desc == "Исходные (длинные)":
            if not dir_path.is_dir(): print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка '{desc}' ({dir_path}) не найдена!"); all_ok = False
            else: print(f"   Папка '{desc}': {dir_path} [Найдена]")
        else:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"   Папка '{desc}': {dir_path} [OK/Создана]")
                if dir_path == Config.AUDIO_TEMP_CHUNK_DIR: # Очищаем временную папку по имени из Config
                    print(f"   Очистка временной папки: {dir_path}")
                    for item in dir_path.iterdir():
                        if item.is_dir(): shutil.rmtree(item)
                        else: item.unlink()
            except Exception as e: print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось создать/очистить папку '{desc}' ({dir_path}): {e}"); all_ok = False
    if not all_ok: sys.exit("Ошибка при подготовке директорий. Скрипт остановлен.")
    print("   Папки проверены/созданы/очищены.")

def find_long_audio_files():
    """Ищет аудиофайлы в папке длинных файлов из Config."""
    print("\n2. Поиск аудиофайлов для обработки (из папки длинных)...")
    audio_files = []
    # Используем путь и расширения из Config
    for ext in Config.AUDIO_EXTENSIONS:
        audio_files.extend(list(Config.AUDIO_SKIPPED_LONG_DIR.rglob(f"*{ext}")))
        audio_files.extend(list(Config.AUDIO_SKIPPED_LONG_DIR.rglob(f"*{ext.upper()}")))
    unique_audio_files = sorted(list(set(audio_files)))
    if not unique_audio_files:
        print(f"   Не найдено аудиофайлов с расширениями {Config.AUDIO_EXTENSIONS} в {Config.AUDIO_SKIPPED_LONG_DIR}.")
        return []
    print(f"   Найдено {len(unique_audio_files)} аудиофайлов для обработки или проверки.")
    return unique_audio_files

def split_audio(original_audio_path: Path, temp_work_dir: Path) -> list[tuple[Path, int]] | None:
    """Нарезает аудио, используя пороги длительности из Config."""
    print("  Нарезка файла на части...")
    try:
        audio = AudioSegment.from_file(original_audio_path)
        total_ms = len(audio)
        # Используем параметры нарезки из Config
        target_chunk_ms = int(Config.AUDIO_TARGET_CHUNK_SECONDS * 1000)
        split_decision_threshold_ms = int(Config.AUDIO_SPLIT_THRESHOLD_SECONDS * 1000) # Используем порог разделения

        chunk_definitions = []
        start_ms = 0
        # Пока оставшаяся длина БОЛЬШЕ порога для разделения, режем стандартный кусок
        while (total_ms - start_ms) > split_decision_threshold_ms:
             if start_ms + target_chunk_ms <= total_ms:
                 end_ms = start_ms + target_chunk_ms
                 chunk_definitions.append((start_ms, end_ms))
                 start_ms = end_ms
             else: # Оставшийся кусок меньше target_chunk_ms, но больше порога не был, берем остаток
                 break

        # Добавляем последний кусок (все, что осталось)
        if start_ms < total_ms:
            chunk_definitions.append((start_ms, total_ms))

        print(f"  Файл будет разделен на {len(chunk_definitions)} частей.")

        output_chunks_info = []
        for i, (start, end) in enumerate(chunk_definitions):
            chunk_duration_ms = end - start
            # Проверка минимальной длины (хотя логика выше должна это обеспечивать)
            if chunk_duration_ms < Config.AUDIO_MIN_CHUNK_SECONDS * 1000:
                 print(f"  ПРЕДУПРЕЖДЕНИЕ: Чанк {i} слишком короткий ({chunk_duration_ms} мс). Проверьте логику нарезки или настройки.")
            chunk = audio[start:end]
            chunk_filename = temp_work_dir / f"chunk_{i:03d}_orig_{chunk_duration_ms}ms.wav"
            print(f"    Сохранение оригинального чанка {i}: {chunk_filename.name} ({chunk_duration_ms / 1000.0:.3f} сек)")
            chunk.export(chunk_filename, format="wav")
            output_chunks_info.append((chunk_filename, chunk_duration_ms))

        return output_chunks_info

    except FileNotFoundError: print(f"  ОШИБКА: Исходный файл не найден для нарезки: {original_audio_path}"); return None
    except pydub.exceptions.CouldntDecodeError: print(f"  ОШИБКА pydub: Не удалось декодировать файл {original_audio_path} для нарезки."); return None
    except Exception as e: print(f"  ОШИБКА при нарезке файла {original_audio_path.name}: {e}"); return None

def merge_chunks(processed_chunk_paths: list[Path], final_output_path: Path) -> bool:
    """Склеивает части (без изменений в логике)."""
    print(f"  Склейка {len(processed_chunk_paths)} частей в {final_output_path.name}...")
    if not processed_chunk_paths: print("  ОШИБКА: Нет частей для склейки."); return False
    try:
        merged_audio = AudioSegment.empty()
        for i, chunk_path in enumerate(processed_chunk_paths):
            if not chunk_path.exists(): print(f"  ОШИБКА: Обработанный чанк не найден: {chunk_path}"); return False
            print(f"    Добавление чанка {i}: {chunk_path.name}")
            chunk_audio = AudioSegment.from_file(chunk_path)
            merged_audio += chunk_audio

        print(f"  Сохранение склеенного файла: {final_output_path}")
        final_output_path.parent.mkdir(parents=True, exist_ok=True)
        merged_audio.export(final_output_path, format="wav")
        print("  Склейка и сохранение успешно завершены.")
        return True
    except FileNotFoundError: print(f"  КРИТИЧЕСКАЯ ОШИБКА: Файл чанка исчез во время склейки."); return False
    except pydub.exceptions.CouldntDecodeError: print(f"  ОШИБКА pydub: Не удалось декодировать один из чанков для склейки."); return False
    except Exception as e:
        print(f"  ОШИБКА при склейке или сохранении файла {final_output_path.name}: {e}")
        if final_output_path.exists():
            try: final_output_path.unlink()
            except OSError: pass
        return False

def process_single_long_audio(original_audio_path: Path):
    """Обрабатывает один длинный файл, используя пути и пороги из Config."""
    try:
        # Используем путь из Config для relative_to
        relative_path = original_audio_path.relative_to(Config.AUDIO_SKIPPED_LONG_DIR)
    except ValueError:
        print(f"\nОШИБКА: Не удалось определить относительный путь для {original_audio_path} относительно {Config.AUDIO_SKIPPED_LONG_DIR}. Пропускаем.")
        return "error_relative_path"

    print(f"\n--- Обработка файла: {relative_path} ---")
    # Используем путь из Config для конечного файла
    final_output_path = (Config.AUDIO_OUTPUT_LONG_DIR / relative_path).with_suffix('.wav')

    if final_output_path.exists():
        print(f"  Пропуск: Финальный файл {final_output_path.name} уже существует.")
        return "skipped_exists"

    original_duration_ms = 0
    try:
        print(f"  Получение длительности оригинала...")
        audio_info = AudioSegment.from_file(original_audio_path)
        original_duration_ms = len(audio_info)
        duration_sec = original_duration_ms / 1000.0
        print(f"  Оригинальная длительность: {duration_sec:.3f} сек ({original_duration_ms} мс).")
    except FileNotFoundError: print(f"  ОШИБКА: Исходный файл не найден: {original_audio_path}"); return "error_original_not_found"
    except pydub.exceptions.CouldntDecodeError: print(f"  ОШИБКА pydub: Не удалось прочитать длительность: {original_audio_path.name}"); return "error_duration_read"
    except Exception as dur_err: print(f"  ОШИБКА при получении длительности: {dur_err}"); return "error_duration_generic"

    # Используем временный путь из Config
    temp_work_dir = Config.AUDIO_TEMP_CHUNK_DIR / original_audio_path.stem
    try:
        temp_work_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e: print(f"  КРИТИЧЕСКАЯ ОШИБКА: Не удалось создать временную папку {temp_work_dir}: {e}"); return "error_temp_dir_create"

    status_code = "unknown_error"
    try:
        # Используем порог из Config для решения о нарезке
        if duration_sec <= Config.AUDIO_SPLIT_THRESHOLD_SECONDS:
            print(f"  Файл короче или равен {Config.AUDIO_SPLIT_THRESHOLD_SECONDS:.1f} сек. Обработка целиком...")
            temp_ai_output_path, ai_error_code = run_ai_processing(original_audio_path)
            if ai_error_code: status_code = f"error_ai_{ai_error_code}"; raise Exception(status_code)
            if not temp_ai_output_path or not temp_ai_output_path.exists(): status_code = "error_internal_ai_path"; raise Exception(status_code)

            trim_success, trim_error_code = trim_to_duration(temp_ai_output_path, original_duration_ms, final_output_path)
            try: temp_ai_output_path.unlink()
            except OSError as e: print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить временный AI файл {temp_ai_output_path.name}: {e}")
            if not trim_success: status_code = f"error_trim_{trim_error_code}"; raise Exception(status_code)

            print(f"  Успешная обработка (целиком): {final_output_path.name}")
            status_code = "success_direct"
        else:
            print(f"  Файл длиннее {Config.AUDIO_SPLIT_THRESHOLD_SECONDS:.1f} сек. Требуется нарезка.")
            original_chunks_info = split_audio(original_audio_path, temp_work_dir)
            if original_chunks_info is None: status_code = "error_split"; raise Exception(status_code)

            processed_trimmed_chunks = []
            all_chunks_processed = True
            for i, (orig_chunk_path, orig_chunk_duration_ms) in enumerate(original_chunks_info):
                print(f"\n  --- Обработка чанка {i+1}/{len(original_chunks_info)} ({orig_chunk_path.name}) ---")
                temp_ai_chunk_path, ai_error_code = run_ai_processing(orig_chunk_path)
                if ai_error_code: print(f"    ОШИБКА AI чанка {i}."); status_code = f"error_chunk_ai_{ai_error_code}"; all_chunks_processed = False; break
                if not temp_ai_chunk_path or not temp_ai_chunk_path.exists(): print(f"    КРИТ ОШИБКА AI: нет пути чанка {i}."); status_code = "error_chunk_ai_path"; all_chunks_processed = False; break

                trimmed_chunk_path = temp_work_dir / f"chunk_{i:03d}_processed_trimmed.wav"
                trim_success, trim_error_code = trim_to_duration(temp_ai_chunk_path, orig_chunk_duration_ms, trimmed_chunk_path)
                try: temp_ai_chunk_path.unlink()
                except OSError as e: print(f"      ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить временный AI файл чанка {temp_ai_chunk_path.name}: {e}")
                if not trim_success: print(f"    ОШИБКА обрезки чанка {i}."); status_code = f"error_chunk_trim_{trim_error_code}"; all_chunks_processed = False; break

                processed_trimmed_chunks.append(trimmed_chunk_path)
                print(f"  --- Чанк {i+1}/{len(original_chunks_info)} успешно обработан ---")
                # Используем паузу из Config
                if Config.API_PAUSE_DURATION > 0 and i < len(original_chunks_info) - 1:
                   print(f"    Пауза {Config.API_PAUSE_DURATION} сек...")
                   time.sleep(Config.API_PAUSE_DURATION)

            # --- НАЧАЛО ИЗМЕНЕНИЙ ---
            if not all_chunks_processed:
                 print(f"\n  Обработка файла {original_audio_path.name} прервана из-за ошибки чанка.")
                 # status_code уже установлен в цикле при ошибке
            else:
                # Все чанки обработаны, приступаем к склейке автоматически
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
                    # Ошибка уже будет напечатана внутри merge_chunks
                    print(f"  Ошибка склейки для {original_audio_path.name}.")
                    status_code = "error_merge"
            # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    except Exception as e:
        print(f"  НЕПРЕДВИДЕННАЯ ОШИБКА файла {original_audio_path.name}: {e}")
        # Если status_code не был установлен ранее (маловероятно, но возможно)
        if status_code == "unknown_error": status_code = "error_unexpected"
    finally:
        # Очистка временной папки в любом случае (успех, ошибка, отмена)
        if temp_work_dir.exists():
            try:
                print(f"\n  Очистка временной папки: {temp_work_dir}")
                shutil.rmtree(temp_work_dir)
            except Exception as e:
                print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось очистить {temp_work_dir}: {e}")
    return status_code

def print_summary_report(total_files, status_counts):
    """Печатает отчет, используя порог и пути из Config."""
    print("\n--- Скрипт Завершен ---")
    print(f"Всего найдено аудиофайлов для проверки/обработки: {total_files}")
    print("-" * 30)
    print("Успешно обработано:")
    print(f"  - Целиком (<= {Config.AUDIO_SPLIT_THRESHOLD_SECONDS:.1f} сек): {status_counts.get('success_direct', 0)}")
    print(f"  - Склеено из частей (> {Config.AUDIO_SPLIT_THRESHOLD_SECONDS:.1f} сек): {status_counts.get('success_merged', 0)}")
    print("-" * 30)
    print("Пропущено:")
    print(f"  - Финальный файл уже существовал: {status_counts.get('skipped_exists', 0)}")
    # --- ИЗМЕНЕНИЕ: Убрана строка про отмену склейки, т.к. она теперь автоматическая ---
    # print(f"  - Склейка отменена пользователем: {status_counts.get('cancelled_merge', 0)}")
    print("-" * 30)

    errors_total = sum(v for k, v in status_counts.items() if k.startswith("error_"))
    print(f"Возникло ошибок при обработке/проверке: {errors_total}")
    if errors_total > 0:
        print("  Детали ошибок:")
        error_summary = {}
        for status, count in status_counts.items():
             if status.startswith("error_"):
                parts = status.split('_')
                etype = parts[1].upper()
                ecode = '_'.join(parts[2:]) if len(parts) > 2 else "general"
                if etype == "CHUNK":
                    # Уточняем тип ошибки чанка (AI, TRIM и т.д.)
                    etype = f"CHUNK_{parts[2].upper()}"
                    ecode = '_'.join(parts[3:]) if len(parts) > 3 else "general"
                key = f"Ошибка {etype}" + (f" ({ecode})" if ecode != "general" else "")
                error_summary[key] = error_summary.get(key, 0) + count
        for error_desc, count in sorted(error_summary.items()): print(f"    - {error_desc}: {count} раз")
        print("  Просмотрите лог выше для подробной информации по каждому файлу.")
    print("-" * 30)
    # Используем пути из Config
    print(f"Обработанные файлы сохранены в: {Config.AUDIO_OUTPUT_LONG_DIR}")
    print(f"Временные файлы создавались в: {Config.AUDIO_TEMP_CHUNK_DIR} (должна быть пустой)")
    print("Не забудь остановить процесс 'python app.py', если он больше не нужен.")

def check_dependencies():
    """Проверяет наличие необходимых библиотек (без изменений)."""
    print("Проверка зависимостей...")
    ok = True
    try: import gradio_client; print("  [OK] gradio_client")
    except ImportError: print("  [ОШИБКА] gradio_client не найден."); ok = False
    try:
        import pydub; print("  [OK] pydub")
        try: AudioSegment.silent(duration=10); print("  [OK] FFmpeg/avconv (предположительно) доступен.")
        except Exception as e: print(f"  [ПРЕДУПРЕЖДЕНИЕ] FFmpeg/avconv недоступен для pydub? Ошибка: {e}")
    except ImportError: print("  [ОШИБКА] pydub не найден."); ok = False
    return ok

# --- Точка входа ---
if __name__ == "__main__":
    if not check_dependencies(): print("\nРабота прервана из-за зависимостей."); sys.exit(1)

    print("\n--- Скрипт Обработки ДЛИННЫХ Аудио (из Config) ---")
    # Используем параметры из Config для вывода
    print(f"Исходные файлы из: {Config.AUDIO_SKIPPED_LONG_DIR}")
    print(f"Результаты в:      {Config.AUDIO_OUTPUT_LONG_DIR}")
    print(f"Временные чанки в: {Config.AUDIO_TEMP_CHUNK_DIR} (будет очищена)")
    print(f"Порог для нарезки: {Config.AUDIO_SPLIT_THRESHOLD_SECONDS:.1f} сек")
    print(f"Целевая длина чанка: {Config.AUDIO_TARGET_CHUNK_SECONDS:.1f} сек")
    print(f"Обработка AI через: {Config.AUDIO_GRADIO_APP_URL} (эндпоинт: {Config.AUDIO_API_NAME})")
    print(f"Параметры AI: Model='{Config.AUDIO_MODEL_NAME}', Guidance={Config.AUDIO_GUIDANCE_SCALE}, Steps={Config.AUDIO_DDIM_STEPS}, Seed={Config.AUDIO_SEED}")
    print("-" * 50)
    print("ВАЖНО: Убедись, что 'python app.py' запущен!")
    print(f"ВАЖНО: Убедись, что FFmpeg/avconv установлен и доступен!")
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
        if not audio_path.exists():
            print(f"Пропуск: Исходный файл {audio_path.name} не найден.")
            # Добавим статус для этого случая, чтобы он не терялся
            status = "skipped_original_missing"
        else:
            status = process_single_long_audio(audio_path)

        # Убедимся, что статус не None, на всякий случай
        status = status if status else "error_unknown_status_returned"
        status_counts[status] = status_counts.get(status, 0) + 1
        print(f">>> Статус файла {audio_path.name}: {status} <<<")

    print_summary_report(total_files, status_counts)