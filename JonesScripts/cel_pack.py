import sys
import subprocess
import re
import shutil
from pathlib import Path
import time
# import os # os.path.splitext не нужен, используем pathlib

# --- НАСТРОЙКИ ---
BASE_DIR = Path(r"C:\Users\yaros\Desktop\in")
ORIGINAL_CEL_MAT_DIR = BASE_DIR / "used_manual_mat" # Откуда берем инфо/оригиналы MAT
PROCESSED_PNG_DIR = BASE_DIR / "processed_png"     # Откуда берем апскейлнутые CEL PNG
FINAL_MAT_DIR = BASE_DIR / "final_mat"           # Куда кладем результат
USED_PNG_DIR = BASE_DIR / "used"                 # Сюда перемещаем апскейл PNG после использования
EXTRACTED_DIR = BASE_DIR / "extracted"             # Папка с оригинальными извлеченными (для справки)
MATOOL_EXE = BASE_DIR / "matool.exe"

# --- Папки форматов (нужны для get_mat_info) ---
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
        if alt_matool_path.exists(): matool_executable = alt_matool_path
        else:
            print(f"ОШИБКА: matool.exe не найден ни в {MATOOL_EXE}, ни в {alt_matool_path}")
            return None, f"matool.exe не найден"

    # В create может быть много аргументов, выводим только начало
    cmd_str_display = f"'{matool_executable}' {command}"
    if command.lower() == 'create' and len(args) > 3:
         # Показываем формат, имя вых. файла, первый PNG и кол-во остальных
         cmd_str_display += f" {args[0]} '{args[1].name}' '{args[2].name}' ... ({len(args) - 3} more PNGs)"
    else:
         # Используем .name для путей Path
         cmd_str_display += ' '.join(f"'{p.name if isinstance(p, Path) else str(p)}'" if isinstance(p, Path) or ' ' in str(p) else str(p) for p in args)

    print(f"  Запуск команды: {cmd_str_display} (в папке {cwd})")

    # Полная команда для subprocess
    cmd = [str(matool_executable), command] + [str(arg) for arg in args]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False,
                                encoding='utf-8', errors='ignore', cwd=cwd)

        # Выводим stdout/stderr только для create и info
        if command.lower() in ['create', 'info']:
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
            print(error_msg)
            # Выводим stderr при любой ошибке
            if result.stderr:
                 stderr_lines = result.stderr.strip().splitlines()
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
    if error: return None, None, False, None # format_raw, format_std, has_alpha, count
    if not stdout:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Получен пустой stdout от matool info для {mat_path.name}.")
        return None, None, False, None

    color_format_raw = None
    color_format_standardized = None
    has_alpha = False
    texture_count = None

    format_match = re.search(r"Encoding:\.*?\s*([A-Za-z0-9\-]+)", stdout, re.IGNORECASE)
    if format_match:
        color_format_raw = format_match.group(1).lower()
        color_format_standardized = color_format_raw.replace('-', '')
        if color_format_standardized in ["rgba4444", "rgba5551", "rgba"]: has_alpha = True
    else:
        mode_match = re.search(r"Color mode:\.*?\s*(RGBA)", stdout, re.IGNORECASE)
        if mode_match:
            has_alpha = True
            color_format_standardized = "rgba" # Неясный, но с альфой

    if color_format_standardized is None:
        color_format_standardized = "rgba" if has_alpha else "unknown"

    texture_count_match = re.search(r"Total textures:\.*?\s*(\d+)", stdout)
    if texture_count_match:
        texture_count = int(texture_count_match.group(1))
    else: print(f"    ПРЕДУПРЕЖДЕНИЕ ({mat_path.name}): Не удалось определить количество текстур.")

    return color_format_raw, color_format_standardized, has_alpha, texture_count

def get_cel_index(path):
    """Извлекает числовой индекс из имени файла __cel_N.png"""
    match = re.search(r'__cel_(\d+)\.png$', path.name, re.IGNORECASE)
    # Возвращаем большое число, если индекс не найден, чтобы они оказались в конце при ошибке
    return int(match.group(1)) if match else float('inf')

# --- НОВЫЕ Структурные Функции ---

def setup_directories_cel_pack():
    """Проверяет и создает необходимые директории для фазы 4."""
    print("1. Проверка/создание необходимых папок...")
    FINAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    ORIGINAL_CEL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    USED_PNG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для финальных MAT: {FINAL_MAT_DIR.name}")
    print(f"   Папка с исходными CEL MAT: {ORIGINAL_CEL_MAT_DIR.name}")
    print(f"   Папка для использованных PNG: {USED_PNG_DIR.name}")
    if not PROCESSED_PNG_DIR.exists() or not PROCESSED_PNG_DIR.is_dir():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с обработанными PNG ({PROCESSED_PNG_DIR}) не найдена!")
        sys.exit(1)
    if not ORIGINAL_CEL_MAT_DIR.exists() or not ORIGINAL_CEL_MAT_DIR.is_dir():
         print(f"КРИТИЧЕСКАЯ ОШИБКА: Не найдена папка с исходными CEL MAT ({ORIGINAL_CEL_MAT_DIR})!")
         sys.exit(1)
    print("   Папки проверены/созданы.")

def find_and_group_cel_pngs():
    """Находит CEL PNG в PROCESSED_PNG_DIR и группирует их по базовому имени."""
    print(f"\n2. Поиск и группировка CEL PNG файлов в {PROCESSED_PNG_DIR.name}...")
    cel_png_files = list(PROCESSED_PNG_DIR.glob('*__cel_*.png'))
    if not cel_png_files:
        print(f"   Папка {PROCESSED_PNG_DIR.name} не содержит файлов с '__cel_' в имени.")
        return {} # Возвращаем пустой словарь

    cel_groups = {}
    for png_path in cel_png_files:
        # Извлекаем базовое имя до "__cel_"
        base_name_match = re.match(r'(.+)__cel_\d+', png_path.stem, re.IGNORECASE)
        if base_name_match:
            base_name = base_name_match.group(1)
            if base_name not in cel_groups:
                cel_groups[base_name] = []
            cel_groups[base_name].append(png_path)
        else:
             print(f"   ПРЕДУПРЕЖДЕНИЕ: Не удалось извлечь базовое имя из {png_path.name}")

    print(f"   Найдено {len(cel_png_files)} CEL PNG файлов, сгруппированных по {len(cel_groups)} базовым именам.")
    return cel_groups

def check_if_cel_packed(final_mat_path, png_group):
    """Проверяет, существует ли финальный MAT, и перемещает PNG, если да."""
    if final_mat_path.exists():
        print(f"  Пропуск: Финальный файл {final_mat_path.name} уже существует в {FINAL_MAT_DIR.name}.")
        # Перемещаем связанные PNG в used_png
        print(f"    Перемещение {len(png_group)} связанных PNG -> {USED_PNG_DIR.name}...")
        moved_png_count = 0
        USED_PNG_DIR.mkdir(parents=True, exist_ok=True) # Убедимся, что папка есть
        for png_to_move in png_group:
            if png_to_move.exists():
                try:
                    used_target = USED_PNG_DIR / png_to_move.name
                    shutil.move(str(png_to_move), str(used_target))
                    moved_png_count += 1
                except OSError as e: print(f"      Не удалось переместить {png_to_move.name}: {e}")
        print(f"    Перемещено: {moved_png_count} PNG.")
        return True # Да, пропущено
    return False # Нет, не пропущено

def get_original_cel_mat_info(original_mat_path):
    """Проверяет наличие исходного MAT и возвращает формат и кол-во текстур."""
    if not original_mat_path.exists():
        print(f"  ОШИБКА: Исходный CEL MAT ({original_mat_path.name}) не найден в {ORIGINAL_CEL_MAT_DIR.name}.")
        return None, None # Формат, Кол-во

    print(f"  Получение инфо из {original_mat_path.name}...")
    _, std_format, _, original_texture_count = get_mat_info(original_mat_path)

    if std_format is None or std_format == "unknown" or std_format == "rgba":
         print(f"  ОШИБКА: Не удалось определить корректный формат ({std_format}) для запаковки.")
         return None, None
    if original_texture_count is None:
         print(f"  ОШИБКА: Не удалось определить исходное количество текстур.")
         return None, None

    print(f"    Формат для create: {std_format}, Ожидаемое кол-во текстур: {original_texture_count}")
    return std_format, original_texture_count

def sort_and_validate_pngs(png_group, expected_count, base_name):
    """Сортирует PNG по индексу __cel_N и проверяет их количество."""
    print(f"  Сортировка {len(png_group)} PNG для группы {base_name}...")
    try:
        sorted_png_paths = sorted(png_group, key=get_cel_index)
        # Проверка, что не было ошибок при извлечении индекса (inf)
        if any(get_cel_index(p) == float('inf') for p in sorted_png_paths):
             print(f"  ОШИБКА: Не удалось извлечь числовой индекс __cel_N из одного или нескольких PNG файлов.")
             return None
        print(f"    Отсортированные PNG: {[p.name for p in sorted_png_paths]}")
    except Exception as e_sort:
         print(f"  ОШИБКА при сортировке PNG файлов: {e_sort}")
         return None

    if len(sorted_png_paths) != expected_count:
        print(f"  ОШИБКА: Количество найденных/отсортированных PNG ({len(sorted_png_paths)}) не совпадает с ожидаемым ({expected_count}).")
        print(f"           Проверьте файлы {base_name}__cel_*.png в папке {PROCESSED_PNG_DIR.name}.")
        return None

    print(f"    Количество PNG ({len(sorted_png_paths)}) совпадает с ожидаемым ({expected_count}).")
    return sorted_png_paths

def pack_cel_pngs_to_mat(std_format, final_mat_path, sorted_png_paths, actual_output_path):
    """Выполняет matool create для CEL файлов, проверяет результат и перемещает его."""
    try:
        # Передаем формат, имя вых. файла БЕЗ __cel_, и список PNG
        (stdout, stderr), error = run_matool("create", std_format, final_mat_path, *sorted_png_paths)
        if error:
            print(f"  ОШИБКА: matool create завершился с ошибкой.")
            return False # Запаковка не удалась

        time.sleep(0.2) # Пауза перед проверкой

        # Проверяем, появился ли файл (предполагаем вывод в BASE_DIR)
        if actual_output_path.exists():
            print(f"  Успех: matool создал {actual_output_path.name}. Перемещаем -> {final_mat_path.relative_to(BASE_DIR)}...")
            try:
                FINAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(actual_output_path), str(final_mat_path))
                print("    Перемещение успешно.")
                return True # Успех
            except Exception as move_error:
                print(f"  ОШИБКА при перемещении НОВОГО файла {actual_output_path.name}: {move_error}")
                return False # Неудача
        elif final_mat_path.exists(): # Проверка, не создал ли он сразу в нужном месте
             print(f"  Информация: matool создал файл сразу в {FINAL_MAT_DIR.name}.")
             return True # Успех
        else:
            print(f"  ОШИБКА: matool сообщил об успехе (код 0), но новый файл {final_mat_path.name} не найден!")
            return False # Неудача

    except Exception as e:
        print(f"  КРИТИЧЕСКАЯ ОШИБКА во время вызова matool create: {e}")
        return False # Неудача

def verify_packed_cel_mat(final_mat_path, expected_count):
    """Проверяет количество текстур в созданном MAT файле."""
    print(f"  Проверка количества текстур в новом файле {final_mat_path.name}...")
    _, _, _, new_texture_count = get_mat_info(final_mat_path)

    if new_texture_count is None:
        print(f"  ОШИБКА: Не удалось получить информацию о новом файле {final_mat_path.name}.")
        # Пытаемся удалить некорректный файл
        try: final_mat_path.unlink(); print(f"    Некорректный файл {final_mat_path.name} удален.")
        except OSError: print(f"    Не удалось удалить некорректный файл {final_mat_path.name}.")
        return False # Верификация не пройдена

    if new_texture_count != expected_count:
        print(f"  КРИТИЧЕСКАЯ ОШИБКА: Количество текстур в новом файле ({new_texture_count}) не совпадает с ожидаемым ({expected_count})!")
        # Пытаемся удалить некорректный файл
        try: final_mat_path.unlink(); print(f"    Некорректный файл {final_mat_path.name} удален.")
        except OSError: print(f"    Не удалось удалить некорректный файл {final_mat_path.name}.")
        return False # Верификация не пройдена

    print(f"    Проверка количества текстур пройдена ({new_texture_count}).")
    return True # Верификация успешна

def cleanup_after_cel_packing(sorted_png_paths, original_mat_path):
    """Перемещает использованные PNG и удаляет оригинальный MAT."""
    print("  Запаковка и проверка прошли успешно. Начинаем очистку...")
    cleanup_error = False
    USED_PNG_DIR.mkdir(parents=True, exist_ok=True) # Убедимся, что папка есть
    moved_png_count = 0

    # Перемещаем использованные PNG в USED_PNG_DIR
    print(f"    Перемещение {len(sorted_png_paths)} обработанных PNG -> {USED_PNG_DIR.name}...")
    for png_to_move in sorted_png_paths:
        if png_to_move.exists():
            try:
                used_target = USED_PNG_DIR / png_to_move.name
                shutil.move(str(png_to_move), str(used_target))
                moved_png_count += 1
            except OSError as e:
                print(f"      Не удалось переместить {png_to_move.name}: {e}")
                cleanup_error = True # Считаем ошибкой очистки
        else:
             print(f"      ПРЕДУПРЕЖДЕНИЕ: PNG {png_to_move.name} не найден для перемещения.")

    print(f"    Перемещено: {moved_png_count} PNG.")

    # Удаляем оригинальный извлеченный CEL MAT из used_manual_mat
    if original_mat_path.exists():
        print(f"    Удаление оригинального MAT ({original_mat_path.name}) из {ORIGINAL_CEL_MAT_DIR.name}...")
        try:
            original_mat_path.unlink()
        except OSError as e:
            print(f"      ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {original_mat_path.name}: {e}")
            cleanup_error = True # Считаем ошибкой очистки
    else:
         print(f"    ПРЕДУПРЕЖДЕНИЕ: Оригинальный MAT {original_mat_path.name} не найден для удаления.")

    if cleanup_error:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Возникли ошибки при очистке файлов.")
    else:
        print(f"  Очистка завершена успешно.")

    return not cleanup_error # True если успешно, False если были ошибки

def process_cel_group(base_name, png_group):
    """Полный цикл обработки одной группы CEL файлов."""
    print(f"\nОбработка группы: {base_name}")
    print(f"  Найдено PNG для группы: {len(png_group)}")

    original_mat_path = ORIGINAL_CEL_MAT_DIR / f"{base_name}.mat"
    final_mat_path = FINAL_MAT_DIR / f"{base_name}.mat"
    actual_output_path = BASE_DIR / f"{base_name}.mat" # Куда matool может вывести

    # 1. Проверить, не запакован ли уже
    if check_if_cel_packed(final_mat_path, png_group):
        return "skipped"

    # 2. Получить формат и кол-во из исходного MAT
    std_format, original_texture_count = get_original_cel_mat_info(original_mat_path)
    if std_format is None: # original_texture_count проверен внутри
        return "error_mat_info"

    # 3. Отсортировать и проверить кол-во PNG
    sorted_png_paths = sort_and_validate_pngs(png_group, original_texture_count, base_name)
    if sorted_png_paths is None:
        return "error_png_mismatch"

    # 4. Запаковать PNG в MAT
    pack_ok = pack_cel_pngs_to_mat(std_format, final_mat_path, sorted_png_paths, actual_output_path)
    if not pack_ok:
        return "error_packing"

    # 5. Верифицировать созданный MAT
    verify_ok = verify_packed_cel_mat(final_mat_path, original_texture_count)
    if not verify_ok:
        return "error_verification" # Ошибка верификации (файл удален)

    # 6. Очистить исходные файлы (PNG и MAT)
    cleanup_ok = cleanup_after_cel_packing(sorted_png_paths, original_mat_path)
    if not cleanup_ok:
        return "success_with_cleanup_issue" # Основная работа сделана

    return "success" # Полный успех

def print_summary_report_cel_pack(total_groups, status_counts):
    """Печатает итоговый отчет для фазы 4."""
    print("\n--- Скрипт 4 Завершен ---")
    print(f"Всего найдено групп CEL файлов для обработки: {total_groups}")

    success_count = status_counts.get('success', 0)
    success_cleanup_issue = status_counts.get('success_with_cleanup_issue', 0)
    skipped_count = status_counts.get('skipped', 0)
    error_mat_info = status_counts.get('error_mat_info', 0)
    error_png_mismatch = status_counts.get('error_png_mismatch', 0)
    error_packing = status_counts.get('error_packing', 0)
    error_verification = status_counts.get('error_verification', 0)
    total_errors = error_mat_info + error_png_mismatch + error_packing + error_verification

    print(f"Успешно запаковано, проверено и очищено: {success_count} групп.")
    if success_cleanup_issue > 0:
        print(f"Успешно запаковано, но с ошибками очистки: {success_cleanup_issue} групп.")
    print(f"Пропущено (финальный MAT уже существовал): {skipped_count} групп.")
    print(f"Всего ошибок при обработке: {total_errors} групп.")
    if total_errors > 0:
        print("  Детали ошибок:")
        if error_mat_info > 0: print(f"    - Ошибка получения инфо из оригинального MAT: {error_mat_info}")
        if error_png_mismatch > 0: print(f"    - Ошибка сортировки/количества PNG: {error_png_mismatch}")
        if error_packing > 0: print(f"    - Ошибка запаковки MAT / перемещения результата: {error_packing}")
        if error_verification > 0: print(f"    - Ошибка верификации созданного MAT (файл удален): {error_verification}")
        print("  Просмотрите лог выше для информации по конкретным группам.")

    print(f"\nФинальные MAT файлы находятся в: {FINAL_MAT_DIR.name}")
    print(f"Использованные CEL PNG перемещены в: {USED_PNG_DIR.name}")
    print(f"Оригинальные CEL MAT (успешно обработанные) удалены из: {ORIGINAL_CEL_MAT_DIR.name}")

    # Проверка остатков
    remaining_cel_png = list(PROCESSED_PNG_DIR.glob('*__cel_*.png'))
    if remaining_cel_png:
        remaining_groups = set()
        for p in remaining_cel_png:
            match = re.match(r'(.+)__cel_\d+', p.stem, re.IGNORECASE)
            if match: remaining_groups.add(match.group(1))
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В {PROCESSED_PNG_DIR.name} остались необработанные CEL PNG ({len(remaining_cel_png)}), затрагивающие {len(remaining_groups)} групп:")
        print(f"  Примеры затронутых групп: {list(remaining_groups)[:5]}")

    lingering_mats = [p for p in BASE_DIR.glob('*.mat') if p.is_file() and '__cel_' not in p.name]
    if lingering_mats:
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В основной папке ({BASE_DIR.name}) обнаружены MAT файлы ({len(lingering_mats)}) БЕЗ __cel_, которые могли остаться из-за ошибок перемещения:")
        print(f"  Примеры: {[f.name for f in lingering_mats[:5]]}")

# --- Основная Логика (Структурированный main) ---
def main():
    """Фаза 4: Запаковка CEL PNG в MAT"""
    print("\n--- Скрипт 4: Запаковка CEL файлов ---")

    # 1. Подготовка
    setup_directories_cel_pack()
    cel_groups = find_and_group_cel_pngs()
    if not cel_groups:
        print("\nРабота скрипта завершена, так как нет CEL PNG файлов для обработки.")
        return

    # 2. Основной цикл обработки по группам
    print("\n3. Начало запаковки групп...")
    status_counts = {} # Словарь для подсчета результатов {status: count}
    total_groups = len(cel_groups)

    # Сортируем группы по имени для предсказуемости
    sorted_group_items = sorted(cel_groups.items())

    for i, (base_name, png_group) in enumerate(sorted_group_items):
        status = process_cel_group(base_name, png_group)
        status_counts[status] = status_counts.get(status, 0) + 1
        # Можно добавить вывод прогресса основного цикла, если нужно
        # print(f"  [{i+1}/{total_groups}] Статус обработки группы {base_name}: {status}")

    # 3. Итоговый отчет
    print_summary_report_cel_pack(total_groups, status_counts)

def check_matool_exists_cel_pack():
    """Проверяет наличие matool.exe для фазы 4."""
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
     if check_matool_exists_cel_pack():
        main()
     else:
        print("\nРабота скрипта прервана из-за отсутствия matool.exe.")
        sys.exit(1)