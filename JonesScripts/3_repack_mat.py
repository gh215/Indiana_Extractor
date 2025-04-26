import sys
import subprocess
import re
import shutil
from pathlib import Path
import time

# --- НАСТРОЙКИ ---
BASE_DIR = Path(r"C:\Users\yaros\Desktop\in")
OLD_MAT_DIR = BASE_DIR / "used_mat"         # <-- Отсюда берем инфо для MAT
USED_PNG_DIR = BASE_DIR / "used"            # <-- Сюда перемещаем апскейл PNG после использования
EXTRACTED_DIR = BASE_DIR / "extracted"      # <-- Отсюда удаляем оригинальный извлеченный PNG
PROCESSED_PNG_DIR = BASE_DIR / "processed_png" # <-- Откуда берем PNG для запаковки
FINAL_MAT_DIR = BASE_DIR / "final_mat"       # <-- Сюда кладем результат
MATOOL_EXE = BASE_DIR / "matool.exe"

FORMAT_DIRS = {
    "rgb565": EXTRACTED_DIR / "rgb565",
    "rgba4444": EXTRACTED_DIR / "rgba4444",
    "rgba5551": EXTRACTED_DIR / "rgba5551",
    "unknown": EXTRACTED_DIR / "unknown_format",
    "rgba": EXTRACTED_DIR / "rgba_unknown"
}

def run_matool(command, *args, cwd=BASE_DIR):
    """Запускает matool.exe с заданной командой и аргументами."""
    matool_executable = MATOOL_EXE

    if not MATOOL_EXE.exists():
        alt_matool_path = BASE_DIR / "extracted" / "matool.exe"
        if alt_matool_path.exists():
            matool_executable = alt_matool_path
        else:
            print(f"ОШИБКА: matool.exe не найден ни в {MATOOL_EXE}, ни в {alt_matool_path}")
            return None, f"matool.exe не найден"

    cmd = [str(matool_executable), command] + [str(arg) for arg in args]
    cmd_str_list = [f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in cmd]
    # Выводим команду только для create для чистоты лога
    if command.lower() == 'create':
        print(f"  Запуск команды: {' '.join(cmd_str_list)} (в папке {cwd})")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False,
                                encoding='utf-8', errors='ignore', cwd=cwd)

        # Выводим stdout/stderr только для create
        if command.lower() == 'create':
            stdout_lines = result.stdout.strip().splitlines() if result.stdout else []
            stderr_lines = result.stderr.strip().splitlines() if result.stderr else []
            if stdout_lines and any(line.strip() for line in stdout_lines):
                 print("    Stdout:")
                 print('\n'.join(f"      {line}" for line in stdout_lines if line.strip()))
            if stderr_lines and any(line.strip() for line in stderr_lines):
                 print("    Stderr:")
                 print('\n'.join(f"      {line}" for line in stderr_lines if line.strip()))

        if result.returncode != 0:
            error_msg = f"ОШИБКА: Команда matool {command} завершилась с кодом {result.returncode}."
            # Выводим ошибку всегда, если она есть
            print(error_msg)
            if result.stderr:
                 stderr_lines = result.stderr.strip().splitlines()
                 if stderr_lines and any(line.strip() for line in stderr_lines):
                     print("    Stderr:")
                     print('\n'.join(f"      {line}" for line in stderr_lines if line.strip()))

            return (result.stdout, result.stderr), error_msg

        return (result.stdout, result.stderr), None

    except FileNotFoundError:
        error_msg = f"ОШИБКА: Не удалось запустить команду {command}. Убедитесь, что {matool_executable} существует и доступен."
        print(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f"ОШИБКА: Непредвиденная ошибка при запуске matool {command}: {e}"
        print(error_msg)
        return None, error_msg

def get_mat_info(mat_path):
    """Получает информацию из matool info и парсит формат, наличие альфы и кол-во текстур."""
    (stdout, stderr), error = run_matool("info", mat_path)

    if error:
        # Сообщение об ошибке уже выведено run_matool
        return None, None, False, None # Возвращаем None для форматов

    if not stdout:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Получен пустой stdout от matool info для {mat_path.name}, хотя код возврата 0.")
        return None, None, False, None

    color_format_raw = None
    color_format_standardized = None
    has_alpha = False

    # Парсинг Encoding
    format_match = re.search(r"Encoding:\.*?\s*([A-Za-z0-9\-]+)", stdout, re.IGNORECASE)
    if format_match:
        color_format_raw = format_match.group(1).lower()
        color_format_standardized = color_format_raw.replace('-', '')
        if color_format_standardized in ["rgba4444", "rgba5551", "rgba"]:
            has_alpha = True
    else:
        # Парсинг Color mode, если Encoding не найден
        mode_match = re.search(r"Color mode:\.*?\s*(RGBA)", stdout, re.IGNORECASE)
        if mode_match:
            has_alpha = True
            color_format_standardized = "rgba" # Неясный формат для create
            color_format_raw = None # Не было найдено
        else:
             color_format_standardized = "unknown"
             color_format_raw = None

    # Если формат не определился, ставим unknown
    if color_format_standardized is None:
         color_format_standardized = "unknown"

    # Парсинг количества текстур
    texture_count_match = re.search(r"Total textures:\.*?\s*(\d+)", stdout)
    texture_count = None
    if texture_count_match:
        texture_count = int(texture_count_match.group(1))
    else:
         # Если не найдено, предполагаем 1, т.к. сюда должны попадать только такие
         texture_count = 1
         print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось определить количество текстур для {mat_path.name}. Предполагаем 1.")

    # Возвращаем оба формата: raw (для возможного использования) и standardized (для команды create)
    return color_format_raw, color_format_standardized, has_alpha, texture_count


def setup_directories_phase3():
    """Проверяет и создает необходимые директории для фазы 3."""
    print("\n1. Проверка/создание необходимых папок...")
    FINAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    OLD_MAT_DIR.mkdir(parents=True, exist_ok=True)
    USED_PNG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для финальных MAT: {FINAL_MAT_DIR}")
    print(f"   Папка с исходными MAT для инфо: {OLD_MAT_DIR}")
    print(f"   Папка для использованных PNG: {USED_PNG_DIR}")
    if not PROCESSED_PNG_DIR.exists() or not PROCESSED_PNG_DIR.is_dir():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с обработанными PNG ({PROCESSED_PNG_DIR}) не найдена или не является папкой!")
        sys.exit(1)
    if not OLD_MAT_DIR.exists() or not OLD_MAT_DIR.is_dir():
         print(f"КРИТИЧЕСКАЯ ОШИБКА: Не найдена папка с исходными MAT ({OLD_MAT_DIR}), необходимая для получения формата!")
         sys.exit(1)
    print("   Папки проверены/созданы.")

def find_processed_pngs():
    """Находит PNG файлы в папке PROCESSED_PNG_DIR."""
    print(f"\n2. Поиск обработанных PNG файлов в {PROCESSED_PNG_DIR.name}...")
    processed_png_files = sorted(list(PROCESSED_PNG_DIR.glob('*.png')))
    if not processed_png_files:
        print(f"   Папка {PROCESSED_PNG_DIR.name} пуста. Нет PNG файлов для запаковки.")
        return []
    print(f"   Найдено {len(processed_png_files)} .png файлов для запаковки.")
    return processed_png_files

def check_if_already_packed(final_mat_path, processed_png_path, used_png_target_path):
    """Проверяет, существует ли финальный MAT, и перемещает PNG, если да."""
    if final_mat_path.exists():
        print(f"  Пропуск: Финальный файл {final_mat_path.name} уже существует в {FINAL_MAT_DIR.name}.")
        # Перемещаем PNG в used_png, т.к. работа для него завершена
        if processed_png_path.exists():
            try:
                print(f"    Перемещение существующего PNG {processed_png_path.name} -> {used_png_target_path.relative_to(BASE_DIR)}...")
                USED_PNG_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(processed_png_path), str(used_png_target_path))
            except OSError as e:
                print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось переместить PNG {processed_png_path.name}: {e}")
        return True # Да, пропущено
    return False # Нет, не пропущено

def get_packing_format_from_original(original_mat_path):
    """Проверяет наличие исходного MAT и возвращает формат для запаковки."""
    if not original_mat_path.exists():
        print(f"  ОШИБКА: Исходный MAT файл ({original_mat_path.name}) не найден в {OLD_MAT_DIR.name}.")
        print(f"           Невозможно получить формат для запаковки. Пропускаем.")
        return None # Ошибка: MAT не найден

    print(f"  Получение формата из {original_mat_path.name}...")
    _, std_format, _, _ = get_mat_info(original_mat_path)

    # Проверяем, удалось ли получить валидный формат для create
    if std_format is None or std_format == "unknown" or std_format == "rgba":
         print(f"  ОШИБКА: Не удалось определить корректный формат ({std_format}) из {original_mat_path.name}.")
         print(f"           Невозможно выполнить 'matool create'. Пропускаем.")
         return None # Ошибка: формат не подходит

    print(f"    Определен формат для запаковки: {std_format}")
    return std_format

def pack_png_to_mat(std_format, final_mat_path, processed_png_path, actual_output_path):
    """Выполняет matool create, проверяет результат и перемещает его."""
    pack_and_move_successful = False
    try:
        (stdout, stderr), error = run_matool("create", std_format, final_mat_path, processed_png_path)
        if error:
            print(f"  ОШИБКА: matool create завершился с ошибкой.")
            # Сообщение об ошибке уже выведено run_matool
            return False # Запаковка не удалась

        time.sleep(0.2)

        # Проверяем, появился ли файл в BASE_DIR (предполагаемое поведение matool)
        if actual_output_path.exists():
            print(f"  Успех: matool создал новый {actual_output_path.name} в {BASE_DIR.name}.")
            print(f"  Перемещение нового {actual_output_path.name} -> {final_mat_path.relative_to(BASE_DIR)}...")
            try:
                FINAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(actual_output_path), str(final_mat_path))
                print("    Перемещение нового файла успешно завершено.")
                pack_and_move_successful = True
            except Exception as move_error:
                print(f"  ОШИБКА при перемещении НОВОГО файла {actual_output_path.name} в {final_mat_path.parent.name}: {move_error}")
                # Новый MAT остался в BASE_DIR, это проблема
                pack_and_move_successful = False # Считаем неудачей, т.к. файл не там где должен
        else:
            # Проверим, не создал ли matool файл сразу в final_mat_path
            if final_mat_path.exists():
                print(f"  Информация: matool создал файл сразу в {FINAL_MAT_DIR.name}.")
                pack_and_move_successful = True
            else:
                print(f"  ОШИБКА: matool сообщил об успехе (код 0), но новый файл не найден ни в {BASE_DIR.name}, ни в {FINAL_MAT_DIR.name}!")
                pack_and_move_successful = False # Считаем это ошибкой

    except Exception as e:
        print(f"  КРИТИЧЕСКАЯ ОШИБКА во время вызова matool create для {processed_png_path.name}: {e}")
        pack_and_move_successful = False

    return pack_and_move_successful

def cleanup_after_packing(processed_png_path, used_png_target_path, std_format, base_name):
    """Перемещает использованный PNG и удаляет оригинальный извлеченный PNG."""
    print("  Запаковка и перемещение нового файла прошли успешно. Начинаем очистку...")
    cleanup_error = False
    try:
        # 1. Перемещаем использованный PNG в USED_PNG_DIR
        if processed_png_path.exists():
            print(f"    Перемещение обработанного PNG: {processed_png_path.name} -> {used_png_target_path.relative_to(BASE_DIR)}...")
            USED_PNG_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(processed_png_path), str(used_png_target_path))
        else:
            print(f"    ПРЕДУПРЕЖДЕНИЕ: Обработанный PNG {processed_png_path.name} не найден для перемещения.")

        # 2. Удаляем оригинальный извлеченный PNG из папки формата в EXTRACTED_DIR
        if std_format and std_format != "unknown" and std_format != "rgba":
            original_format_dir = FORMAT_DIRS.get(std_format)
            if original_format_dir and original_format_dir.exists():
                original_extracted_png_path = original_format_dir / f"{base_name}.png"
                if original_extracted_png_path.exists():
                    print(f"    Удаление оригинального извлеченного PNG: {original_extracted_png_path.relative_to(BASE_DIR)}...")
                    try:
                        original_extracted_png_path.unlink()
                    except OSError as e:
                        print(f"      ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {original_extracted_png_path.name}: {e}")
                        cleanup_error = True # Считаем ошибкой очистки

    except Exception as e:
        print(f"  ОШИБКА при очистке файлов для {base_name}: {e}")
        cleanup_error = True

    if cleanup_error:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Запаковка {base_name} завершена, но возникли ошибки при очистке.")
    else:
        print(f"  Очистка для {base_name} завершена успешно.")

    return not cleanup_error # Возвращаем True если очистка успешна, False если были ошибки

def process_single_png_for_packing(processed_png_path):
    """Полный цикл обработки одного PNG для запаковки."""
    base_name = processed_png_path.stem
    print(f"\nОбработка: {processed_png_path.name}")

    original_mat_path = OLD_MAT_DIR / f"{base_name}.mat"
    final_mat_path = FINAL_MAT_DIR / f"{base_name}.mat"
    actual_output_path = BASE_DIR / f"{base_name}.mat" # Куда matool create обычно выводит
    used_png_target_path = USED_PNG_DIR / processed_png_path.name

    # 1. Проверить, не запакован ли уже
    if check_if_already_packed(final_mat_path, processed_png_path, used_png_target_path):
        return "skipped"

    # 2. Получить формат из исходного MAT
    std_format = get_packing_format_from_original(original_mat_path)
    if std_format is None:
        return "error_format" # Ошибка получения/валидации формата

    # 3. Запаковать PNG в MAT
    pack_ok = pack_png_to_mat(std_format, final_mat_path, processed_png_path, actual_output_path)

    if not pack_ok:
        return "error_packing" # Ошибка запаковки или перемещения нового MAT

    # 4. Очистить исходные файлы (PNG)
    cleanup_ok = cleanup_after_packing(processed_png_path, used_png_target_path, std_format, base_name)
    if not cleanup_ok:
        # Основная работа сделана, но логируем проблему с очисткой
        return "success_with_cleanup_issue"

    return "success"

def print_summary_report_phase3(total_files, status_counts):
    """Печатает итоговый отчет для фазы 3."""
    print("\n--- Скрипт 3 Завершен ---")
    print(f"Всего найдено PNG для обработки: {total_files}")

    success_count = status_counts.get('success', 0)
    success_cleanup_issue = status_counts.get('success_with_cleanup_issue', 0)
    skipped_count = status_counts.get('skipped', 0)
    error_format_count = status_counts.get('error_format', 0)
    error_packing_count = status_counts.get('error_packing', 0)
    total_errors = error_format_count + error_packing_count

    print(f"Успешно запаковано и очищено: {success_count}")
    if success_cleanup_issue > 0:
        print(f"Успешно запаковано, но с ошибками очистки: {success_cleanup_issue}")
    print(f"Пропущено (уже существовали в {FINAL_MAT_DIR.name}): {skipped_count}")
    print(f"Всего ошибок (не удалось получить формат / запаковать / переместить): {total_errors}")
    if total_errors > 0:
        print("  Детали ошибок:")
        if error_format_count > 0: print(f"    - Ошибка получения/валидации формата: {error_format_count}")
        if error_packing_count > 0: print(f"    - Ошибка запаковки/перемещения нового MAT: {error_packing_count}")
        print("  Просмотрите лог выше для информации по конкретным файлам.")

    print(f"\nФинальные MAT файлы находятся в: {FINAL_MAT_DIR.name}")
    print(f"Исходные MAT для информации остались в: {OLD_MAT_DIR.name}")
    print(f"Использованные PNG перемещены в: {USED_PNG_DIR.name}")

    # Проверка остатков
    remaining_png_processed = list(PROCESSED_PNG_DIR.glob('*.png'))
    if remaining_png_processed:
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В {PROCESSED_PNG_DIR.name} остались PNG файлы ({len(remaining_png_processed)}), которые не были обработаны из-за ошибок:")
        print(f"  Примеры: {[f.name for f in remaining_png_processed[:5]]}")

    lingering_mats = [p for p in BASE_DIR.glob('*.mat') if p.is_file()]
    if lingering_mats:
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В основной папке ({BASE_DIR.name}) обнаружены MAT файлы ({len(lingering_mats)}), которые могли остаться из-за ошибок перемещения:")
        print(f"  Примеры: {[f.name for f in lingering_mats[:5]]}")


# --- Основная Логика (Структурированный main) ---
def main():
    """Фаза 3: Запаковка PNG в MAT (с использованием MAT из used_mat)"""
    print("\n--- Скрипт 3: Запаковка PNG в MAT ---")

    # 1. Подготовка
    setup_directories_phase3()
    processed_png_files = find_processed_pngs()
    if not processed_png_files:
        print("\nРабота скрипта завершена, так как нет файлов для обработки.")
        return

    # 2. Основной цикл обработки
    print("\n3. Начало запаковки файлов...")
    status_counts = {} # Словарь для подсчета результатов {status: count}

    for png_path in processed_png_files:
        status = process_single_png_for_packing(png_path)
        status_counts[status] = status_counts.get(status, 0) + 1

    # 3. Итоговый отчет
    print_summary_report_phase3(len(processed_png_files), status_counts)


def check_matool_exists_phase3():
    """Проверяет наличие matool.exe для фазы 3."""
    print("Проверка наличия matool.exe...")
    if MATOOL_EXE.exists():
        print(f"  [OK] Найден matool.exe: {MATOOL_EXE}")
        return True
    else:
        alt_matool_path = BASE_DIR / "extracted" / "matool.exe"
        if alt_matool_path.exists():
            print(f"  [ПРЕДУПРЕЖДЕНИЕ] matool.exe не найден в {MATOOL_EXE}, используется: {alt_matool_path}")
            return True
        else:
            print(f"  [КРИТИЧЕСКАЯ ОШИБКА] matool.exe не найден ни в {MATOOL_EXE}, ни в {alt_matool_path}.")
            return False

if __name__ == "__main__":
     if check_matool_exists_phase3():
        main()
     else:
        print("\nРабота скрипта прервана из-за отсутствия matool.exe.")
        sys.exit(1)