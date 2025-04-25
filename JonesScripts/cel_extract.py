import sys
import subprocess
import re
import shutil
from pathlib import Path

# --- НАСТРОЙКИ ---
BASE_DIR = Path(r"D:\Test jones\Resource\mat")
MANUAL_CEL_DIR = BASE_DIR / "manual_cel_processing" # Откуда берем MAT
EXTRACTED_DIR = BASE_DIR / "extracted"             # Куда извлекаем PNG (в папки форматов)
USED_MANUAL_MAT_DIR = BASE_DIR / "used_manual_mat" # Куда перемещаем MAT после извлечения
MATOOL_EXE = BASE_DIR / "matool.exe"

# --- Папки форматов внутри EXTRACTED_DIR ---
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
            print(f"ПРЕДУПРЕЖДЕНИЕ: matool.exe не найден в {MATOOL_EXE}, но найден в {alt_matool_path}.")
            matool_executable = alt_matool_path
        else:
            print(f"ОШИБКА: matool.exe не найден ни в {MATOOL_EXE}, ни в {alt_matool_path}")
            return None, f"matool.exe не найден"

    cmd = [str(matool_executable), command] + [str(arg) for arg in args]
    cmd_str_list = [f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in cmd]
    # Выводим команду extract
    if command.lower() == 'extract':
        print(f"  Запуск команды: {' '.join(cmd_str_list)} (в папке {cwd})")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False,
                                encoding='utf-8', errors='ignore', cwd=cwd)

        stdout_lines = result.stdout.strip().splitlines() if result.stdout else []
        stderr_lines = result.stderr.strip().splitlines() if result.stderr else []

        # Скрываем пустой вывод
        if command.lower() == 'extract': # Показываем вывод для extract
            if stdout_lines and any(line.strip() for line in stdout_lines):
                 print("    Stdout:")
                 print('\n'.join(f"      {line}" for line in stdout_lines if line.strip()))
            if stderr_lines and any(line.strip() for line in stderr_lines):
                 print("    Stderr:")
                 print('\n'.join(f"      {line}" for line in stderr_lines if line.strip()))

        if result.returncode != 0:
            error_msg = f"ОШИБКА: Команда matool {command} завершилась с кодом {result.returncode}."
            print(error_msg)
            # Выводим stderr всегда при ошибке
            if stderr_lines and any(line.strip() for line in stderr_lines):
                 print("    Stderr:")
                 print('\n'.join(f"      {line}" for line in stderr_lines if line.strip()))
            return (result.stdout, result.stderr), error_msg

        return (result.stdout, result.stderr), None

    except FileNotFoundError:
        error_msg = f"ОШИБКА: Не удалось запустить команду {command}. Убедитесь, что {matool_executable} доступен."
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
        # Сообщение выведено в run_matool
        return None, False, None
    if not stdout:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Получен пустой stdout от matool info для {mat_path.name}, хотя код возврата 0.")
        return None, False, None

    color_format_standardized = "unknown"
    has_alpha = False
    texture_count = None

    format_match = re.search(r"Encoding:\.*?\s*([A-Za-z0-9\-]+)", stdout, re.IGNORECASE)
    if format_match:
        color_format_raw = format_match.group(1).lower()
        color_format_standardized = color_format_raw.replace('-', '')
        if color_format_standardized in ["rgba4444", "rgba5551", "rgba"]:
            has_alpha = True
    else:
        mode_match = re.search(r"Color mode:\.*?\s*(RGBA)", stdout, re.IGNORECASE)
        if mode_match:
            has_alpha = True
            color_format_standardized = "rgba" # Неясный формат, но альфа есть

    texture_count_match = re.search(r"Total textures:\.*?\s*(\d+)", stdout)
    if texture_count_match:
        texture_count = int(texture_count_match.group(1))
    else:
         print(f"    ПРЕДУПРЕЖДЕНИЕ ({mat_path.name}): Не удалось определить количество текстур.")

    # Если формат не определен, но альфа есть, ставим 'rgba', иначе 'unknown'
    if color_format_standardized is None:
        color_format_standardized = "rgba" if has_alpha else "unknown"

    return color_format_standardized, has_alpha, texture_count

def setup_directories_cel_extract():
    """Проверяет и создает необходимые директории для извлечения CEL MAT."""
    print("1. Проверка/создание необходимых папок...")
    MANUAL_CEL_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    USED_MANUAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    for fmt_dir in FORMAT_DIRS.values():
        fmt_dir.mkdir(parents=True, exist_ok=True)
    print(f"   Папка с CEL MAT для извлечения: {MANUAL_CEL_DIR.name}")
    print(f"   Папка для извлеченных PNG: {EXTRACTED_DIR.name} (с подпапками форматов)")
    print(f"   Папка для использованных CEL MAT: {USED_MANUAL_MAT_DIR.name}")
    print("   Папки проверены/созданы.")

def find_cel_mats_to_extract():
    """Находит MAT файлы в папке MANUAL_CEL_DIR."""
    print(f"\n2. Поиск MAT файлов в {MANUAL_CEL_DIR.name}...")
    mat_files = sorted(list(MANUAL_CEL_DIR.glob('*.mat')))
    if not mat_files:
        print(f"   Папка {MANUAL_CEL_DIR.name} пуста. Нет MAT файлов для извлечения.")
        return []
    print(f"   Найдено {len(mat_files)} .mat файлов для извлечения.")
    return mat_files

def cleanup_previous_cel_pngs(base_name, target_format_dir, actual_extract_output_dir):
    """Удаляет старые PNG файлы для данного base_name из папки формата и корня extracted."""
    print(f"  Очистка предыдущих PNG для {base_name}__cel_*...")
    # В папке формата
    existing_format_pngs = list(target_format_dir.glob(f"{base_name}__cel_*.png"))
    if existing_format_pngs:
        print(f"    Удаление {len(existing_format_pngs)} старых PNG из {target_format_dir.name}...")
        for old_png in existing_format_pngs:
            try: old_png.unlink()
            except OSError as e: print(f"      Не удалось удалить {old_png.name}: {e}")
    # В корне extracted
    existing_root_pngs = list(actual_extract_output_dir.glob(f"{base_name}__cel_*.png"))
    if existing_root_pngs:
        print(f"    Удаление {len(existing_root_pngs)} старых PNG из {actual_extract_output_dir.name}...")
        for old_png in existing_root_pngs:
            try: old_png.unlink()
            except OSError as e: print(f"      Не удалось удалить {old_png.name}: {e}")

def extract_cel_mat(mat_path):
    """Выполняет matool extract для указанного MAT файла."""
    print(f"  Извлечение PNG из {mat_path.name}...")
    (stdout, stderr), error = run_matool("extract", mat_path)
    if error:
        print(f"  ОШИБКА: matool extract завершился с ошибкой.")
        return False # Неудачно
    return True # Успешно

def find_and_move_extracted_cels(base_name, actual_extract_output_dir, target_format_dir):
    """Находит извлеченные PNG в корне extracted и перемещает их в папку формата."""
    extracted_pngs_in_root = list(actual_extract_output_dir.glob(f"{base_name}__cel_*.png"))

    if not extracted_pngs_in_root:
        print(f"  ПРЕДУПРЕЖДЕНИЕ/ОШИБКА: matool extract завершился (код 0), но PNG файлы для {base_name}__cel_*.png не найдены в {actual_extract_output_dir.name}.")
        return False # Ошибка: файлы не найдены

    print(f"  Найдено {len(extracted_pngs_in_root)} извлеченных PNG в {actual_extract_output_dir.name}.")
    moved_count = 0
    move_errors = 0
    target_format_dir.mkdir(parents=True, exist_ok=True) # Убедимся, что папка есть

    for png_path in extracted_pngs_in_root:
        target_png_path = target_format_dir / png_path.name
        try:
            shutil.move(str(png_path), str(target_png_path))
            moved_count += 1
        except Exception as e:
            print(f"    ОШИБКА при перемещении {png_path.name} -> {target_format_dir.name}: {e}")
            move_errors += 1

    if move_errors > 0:
        print(f"  ОШИБКА: Не удалось переместить {move_errors} из {len(extracted_pngs_in_root)} PNG файлов.")
        return False # Ошибка: перемещены не все

    print(f"  Успешно перемещено {moved_count} PNG файлов в {target_format_dir.name}.")
    return True # Успешно перемещены все

def move_processed_cel_mat(mat_path):
    """Перемещает исходный CEL MAT в папку USED_MANUAL_MAT_DIR."""
    mat_moved_or_deleted = False
    used_manual_mat_target = USED_MANUAL_MAT_DIR / mat_path.name
    try:
        if not used_manual_mat_target.exists():
            print(f"  Перемещение исходного MAT {mat_path.name} -> {USED_MANUAL_MAT_DIR.name}")
            shutil.move(str(mat_path), str(used_manual_mat_target))
            mat_moved_or_deleted = True
        else:
             print(f"  ПРЕДУПРЕЖДЕНИЕ: MAT {mat_path.name} уже существует в {USED_MANUAL_MAT_DIR.name}.")
             print(f"    Удаляем исходный из {MANUAL_CEL_DIR.name}...")
             try:
                 mat_path.unlink()
                 mat_moved_or_deleted = True # Считаем убранным
                 print(f"    Исходный файл удален.")
             except Exception as e_del:
                 print(f"    ОШИБКА: Не удалось удалить {mat_path.name}: {e_del}")
                 # Оставляем mat_moved_or_deleted = False

    except Exception as e_mat_move:
         print(f"  ОШИБКА при перемещении/удалении исходного MAT {mat_path.name}: {e_mat_move}")
         print(f"  !!! ВНИМАНИЕ: PNG извлечены, но MAT остался в {MANUAL_CEL_DIR.name}!")
         mat_moved_or_deleted = False

    return mat_moved_or_deleted

def process_single_cel_mat(mat_path, actual_extract_output_dir):
    """Полный цикл обработки одного CEL MAT файла."""
    base_name = mat_path.stem
    print(f"\nОбработка: {mat_path.name}")

    # 1. Получение информации
    std_format, has_alpha, texture_count = get_mat_info(mat_path)
    if std_format is None or texture_count is None:
        print(f"  ОШИБКА: Не удалось получить информацию. Пропускаем.")
        return "error_info"

    # 2. Проверка количества текстур
    if texture_count <= 1:
         print(f"  ПРЕДУПРЕЖДЕНИЕ: Файл имеет {texture_count} текстур (ожидалось > 1). Пропускаем извлечение этим скриптом.")
         return "skipped_low_tex_count"

    print(f"    Информация: Формат={std_format}, Альфа={has_alpha}, Текстур={texture_count}")
    target_format_dir = FORMAT_DIRS.get(std_format, FORMAT_DIRS["unknown"])

    # 3. Очистка предыдущих результатов
    cleanup_previous_cel_pngs(base_name, target_format_dir, actual_extract_output_dir)

    # 4. Извлечение
    extract_ok = extract_cel_mat(mat_path)
    if not extract_ok:
        return "error_extract"

    # 5. Перемещение извлеченных PNG
    move_png_ok = find_and_move_extracted_cels(base_name, actual_extract_output_dir, target_format_dir)
    if not move_png_ok:
        # Ошибка произошла, но MAT пока не трогаем, т.к. PNG могли быть частично перемещены или вообще не найдены
        return "error_move_png"

    # 6. Перемещение исходного MAT (только если PNG успешно перемещены)
    move_mat_ok = move_processed_cel_mat(mat_path)
    if not move_mat_ok:
        return "error_move_mat" # PNG извлечены, но MAT остался

    return "success" # Все шаги успешно завершены

def print_summary_report_cel_extract(total_files, status_counts):
    """Печатает итоговый отчет для извлечения CEL MAT."""
    print("\n--- Скрипт 1.5 Завершен ---")
    print(f"Всего найдено MAT файлов в {MANUAL_CEL_DIR.name}: {total_files}")

    success_count = status_counts.get('success', 0)
    skipped_low_tex_count = status_counts.get('skipped_low_tex_count', 0)
    error_info = status_counts.get('error_info', 0)
    error_extract = status_counts.get('error_extract', 0)
    error_move_png = status_counts.get('error_move_png', 0)
    error_move_mat = status_counts.get('error_move_mat', 0)
    total_errors = error_info + error_extract + error_move_png + error_move_mat

    print(f"Успешно извлечено PNG и перемещено MAT: {success_count}")
    if skipped_low_tex_count > 0:
        print(f"Пропущено (<= 1 текстуры): {skipped_low_tex_count}")
    print(f"Всего ошибок при обработке: {total_errors}")
    if total_errors > 0:
        print("  Детали ошибок:")
        if error_info > 0: print(f"    - Ошибка получения информации: {error_info}")
        if error_extract > 0: print(f"    - Ошибка выполнения matool extract: {error_extract}")
        if error_move_png > 0: print(f"    - Ошибка поиска/перемещения извлеченных PNG: {error_move_png}")
        if error_move_mat > 0: print(f"    - Ошибка перемещения/удаления исходного MAT (PNG извлечены!): {error_move_mat}")
        print("  Просмотрите лог выше для информации по конкретным файлам.")

    print(f"\nИсходные CEL MAT после обработки перемещены в: {USED_MANUAL_MAT_DIR.name}")
    print(f"Извлеченные PNG файлы находятся в папках форматов внутри: {EXTRACTED_DIR.name}")
    print(f"\nТеперь запустите Скрипт 2 для апскейла извлеченных PNG файлов.")
    print(f"После этого запустите Скрипт 4 (`pack_cel_mats.py`) для запаковки результатов.")


def main():
    """Фаза 1.5: Извлечение CEL MAT в PNG"""
    print("\n--- Скрипт 1.5: Извлечение CEL MAT в PNG ---")

    # 1. Подготовка
    setup_directories_cel_extract()
    mat_files = find_cel_mats_to_extract()
    if not mat_files:
        print("\nРабота скрипта завершена, так как нет файлов для обработки.")
        return

    # Папка, куда matool extract ИЗВЛЕКАЕТ PNG по умолчанию (относительно cwd=BASE_DIR)
    # Важно определить её один раз
    actual_extract_output_dir = BASE_DIR / "extracted"

    # 2. Основной цикл обработки
    print("\n3. Начало извлечения файлов...")
    status_counts = {} # Словарь для подсчета результатов {status: count}
    total_files = len(mat_files)

    for i, mat_path in enumerate(mat_files):
        # Передаем actual_extract_output_dir в функцию обработки
        status = process_single_cel_mat(mat_path, actual_extract_output_dir)
        status_counts[status] = status_counts.get(status, 0) + 1
        # Можно добавить вывод прогресса основного цикла, если нужно
        # print(f"  [{i+1}/{total_files}] Статус обработки {mat_path.name}: {status}")

    # 3. Итоговый отчет
    print_summary_report_cel_extract(total_files, status_counts)


def check_matool_exists_cel_extract():
    """Проверяет наличие matool.exe для извлечения CEL MAT."""
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
     if check_matool_exists_cel_extract():
        main()
     else:
        print("\nРабота скрипта прервана из-за отсутствия matool.exe.")
        sys.exit(1)