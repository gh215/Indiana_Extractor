import sys
import subprocess
import re
import shutil
from pathlib import Path

# --- НАСТРОЙКИ ---
BASE_DIR = Path(r"D:\Test jones\Resource\mat")
MAT_DIR = BASE_DIR
EXTRACTED_DIR = BASE_DIR / "extracted" # Главная папка для извлеченных файлов и подпапок форматов
USED_DIR = BASE_DIR / "used"           # Папка с УЖЕ АПСКЕЙЛЕННЫМИ результатами (PNG)
USED_MAT_DIR = BASE_DIR / "used_mat"     # Папка для ИСХОДНЫХ .mat после обработки (1 текстура)
MANUAL_CEL_DIR = BASE_DIR / "manual_cel_processing" # Папка для ИСХОДНЫХ .mat (> 1 текстуры)
MATOOL_EXE = BASE_DIR / "matool.exe"

# --- Папки форматов внутри EXTRACTED_DIR ---
FORMAT_DIRS = {
    "rgb565": EXTRACTED_DIR / "rgb565",
    "rgba4444": EXTRACTED_DIR / "rgba4444",
    "rgba5551": EXTRACTED_DIR / "rgba5551",
    "unknown": EXTRACTED_DIR / "unknown_format",
    "rgba": EXTRACTED_DIR / "rgba_unknown" # Для случаев, когда альфа есть, но формат неясен
}

# --- Вспомогательные функции ---
def run_matool(command, *args, cwd=BASE_DIR):
    """Запускает matool.exe с заданной командой и аргументами."""
    matool_executable = MATOOL_EXE

    if not MATOOL_EXE.exists():
        alt_matool_path = BASE_DIR / "extracted" / "matool.exe"
        if alt_matool_path.exists():
            print(f"ПРЕДУПРЕЖДЕНИЕ: matool.exe не найден в {MATOOL_EXE}, но найден в {alt_matool_path}. Используем найденный, но рекомендуется переместить его в {BASE_DIR}.")
            matool_executable = alt_matool_path
        else:
            print(f"ОШИБКА: matool.exe не найден ни в {MATOOL_EXE}, ни в {alt_matool_path}")
            return None, f"matool.exe не найден ни в {MATOOL_EXE}, ни в {alt_matool_path}"

    cmd = [str(matool_executable), command] + [str(arg) for arg in args]
    cmd_str_list = [f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in cmd]
    print(f"  Запуск команды: {' '.join(cmd_str_list)} (в папке {cwd})")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False,
                                encoding='utf-8', errors='ignore', cwd=cwd)

        stdout_lines = result.stdout.strip().splitlines() if result.stdout else []
        stderr_lines = result.stderr.strip().splitlines() if result.stderr else []

        # Скрываем вывод stdout/stderr если он пустой или только пробелы
        if stdout_lines and any(line.strip() for line in stdout_lines):
             print("    Stdout:")
             print('\n'.join(f"      {line}" for line in stdout_lines if line.strip()))
        if stderr_lines and any(line.strip() for line in stderr_lines):
             print("    Stderr:")
             print('\n'.join(f"      {line}" for line in stderr_lines if line.strip()))

        if result.returncode != 0:
            error_msg = f"ОШИБКА: Команда matool завершилась с кодом {result.returncode}."
            print(error_msg)
            return (result.stdout, result.stderr), error_msg

        return (result.stdout, result.stderr), None

    except FileNotFoundError:
        error_msg = f"ОШИБКА: Не удалось запустить команду. Убедитесь, что {matool_executable} существует и доступен."
        print(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f"ОШИБКА: Непредвиденная ошибка при запуске matool: {e}"
        print(error_msg)
        return None, error_msg

def get_mat_info(mat_path):
    """Получает информацию о формате, альфа-канале и количестве текстур из .mat файла."""
    (stdout, stderr), error = run_matool("info", mat_path)
    if error:
        print(f"  Не удалось получить информацию для {mat_path.name}.")
        return None, False, None
    if not stdout:
        print(f"  Получен пустой stdout от matool info для {mat_path.name}, хотя код возврата 0. Проверьте файл.")
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
            print(f"    ПРЕДУПРЕЖДЕНИЕ ({mat_path.name}): Encoding не найден, но Color mode=RGBA. Альфа есть, но формат для запаковки неясен.")
            has_alpha = True
            color_format_standardized = "rgba"

    texture_count_match = re.search(r"Total textures:\.*?\s*(\d+)", stdout)
    if texture_count_match:
        texture_count = int(texture_count_match.group(1))
    else:
         print(f"    ПРЕДУПРЕЖДЕНИЕ ({mat_path.name}): Не удалось определить количество текстур.")

    return color_format_standardized, has_alpha, texture_count

def setup_directories():
    """Создает все необходимые директории для работы скрипта."""
    print("--- Скрипт 1: Извлечение MAT в PNG и Сортировка ---")
    print("1. Создание/проверка необходимых папок...")
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    USED_DIR.mkdir(parents=True, exist_ok=True)
    USED_MAT_DIR.mkdir(parents=True, exist_ok=True)
    MANUAL_CEL_DIR.mkdir(parents=True, exist_ok=True)
    for fmt_dir in FORMAT_DIRS.values():
        fmt_dir.mkdir(parents=True, exist_ok=True)
    print(f"   Базовые папки: {EXTRACTED_DIR}, {USED_DIR}, {USED_MAT_DIR}, {MANUAL_CEL_DIR}")
    print(f"   Подпапки форматов в {EXTRACTED_DIR} проверены/созданы.")

def get_processed_bases():
    """Собирает набор базовых имен файлов, которые уже обработаны или отложены."""
    print("\n2. Сбор информации об уже обработанных/отложенных файлах...")
    processed_result_stems_raw = set()
    processed_result_stems_raw.update(f.stem for f in USED_DIR.glob('*.png'))

    processed_result_bases_normalized = set()
    for stem in processed_result_stems_raw:
        base_part = stem.split('__cel_')[0] if '__cel_' in stem else stem
        processed_result_bases_normalized.add(base_part)
    print(f"   Найдено {len(processed_result_stems_raw)} результатов (*.png/webp?) в {USED_DIR.name}, нормализовано до {len(processed_result_bases_normalized)} баз.")

    processed_mat_bases = {f.stem for f in USED_MAT_DIR.glob('*.mat')}
    print(f"   Найдено {len(processed_mat_bases)} обработанных MAT (single texture) в {USED_MAT_DIR.name}")

    manual_cel_bases = {f.stem for f in MANUAL_CEL_DIR.glob('*.mat')}
    print(f"   Найдено {len(manual_cel_bases)} MAT для ручной обработки (__cel_) в {MANUAL_CEL_DIR.name}")

    processed_bases = processed_result_bases_normalized.union(processed_mat_bases).union(manual_cel_bases)
    print(f"   Итого {len(processed_bases)} уникальных базовых имен к пропуску.")
    return processed_bases

def handle_multi_texture_mat(mat_path, base_name):
    """Обрабатывает MAT файлы с несколькими текстурами (перемещает в MANUAL_CEL_DIR)."""
    print(f"  Обнаружено >1 текстур. Перемещаем MAT в {MANUAL_CEL_DIR.name}.")
    target_path = MANUAL_CEL_DIR / mat_path.name
    moved = False
    try:
        if not target_path.exists():
            shutil.move(str(mat_path), str(target_path))
            print(f"  Успешно перемещен.")
            moved = True
        else:
            print(f"  Файл {mat_path.name} уже существует в {MANUAL_CEL_DIR.name}. Удаляем исходный из {MAT_DIR.name}.")
            try:
                mat_path.unlink()
                print(f"  Исходный файл удален.")
                moved = True # Считаем успешной обработкой, т.к. он уже в целевой папке
            except Exception as e_del:
                print(f"  ОШИБКА: Не удалось удалить {mat_path.name} из {MAT_DIR.name}: {e_del}")
    except Exception as e:
        print(f"  ОШИБКА: Не удалось переместить/удалить {mat_path.name}: {e}")
    return moved # Возвращаем True, если файл успешно перемещен ИЛИ удален (т.к. копия уже была)

def cleanup_previous_output(base_name, std_format):
    """Удаляет старые/промежуточные PNG файлы перед извлечением."""
    target_format_dir = FORMAT_DIRS.get(std_format, FORMAT_DIRS["unknown"])
    final_png_path = target_format_dir / f"{base_name}.png"
    expected_output_png = EXTRACTED_DIR / f"{base_name}.png" # matool извлекает сюда

    if final_png_path.exists():
        print(f"  Удаление старого PNG в папке формата: {final_png_path.relative_to(BASE_DIR)}")
        try: final_png_path.unlink()
        except Exception as e: print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {final_png_path.name}: {e}")
    if expected_output_png.exists():
        print(f"  Удаление предыдущего извлеченного PNG: {expected_output_png.relative_to(BASE_DIR)}")
        try: expected_output_png.unlink()
        except Exception as e: print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {expected_output_png.name}: {e}")

def move_extracted_png(expected_output_png, target_format_dir, final_png_path):
    """Перемещает извлеченный PNG в соответствующую папку формата."""
    png_moved = False
    try:
        print(f"  Перемещение PNG из {expected_output_png.parent.name}/{expected_output_png.name} -> {target_format_dir.name}/{final_png_path.name}")
        target_format_dir.mkdir(parents=True, exist_ok=True) # На всякий случай
        shutil.move(str(expected_output_png), str(final_png_path))
        print(f"  Успешно перемещено PNG.")
        png_moved = True
    except Exception as e:
        print(f"  ОШИБКА: Не удалось переместить {expected_output_png.name} в {final_png_path.name}: {e}")
    return png_moved

def move_processed_mat(mat_path):
    """Перемещает исходный MAT файл в USED_MAT_DIR после успешной обработки."""
    mat_moved_or_deleted = False
    try:
        used_mat_target_path = USED_MAT_DIR / mat_path.name
        if not used_mat_target_path.exists():
            print(f"  Перемещение исходного MAT файла -> {USED_MAT_DIR.name}")
            shutil.move(str(mat_path), str(used_mat_target_path))
            print(f"  Исходный MAT успешно перемещен.")
            mat_moved_or_deleted = True
        else:
            print(f"  ПРЕДУПРЕЖДЕНИЕ: MAT {mat_path.name} уже существует в {USED_MAT_DIR.name}. Удаляем исходный из {MAT_DIR.name}.")
            try:
                mat_path.unlink()
                mat_moved_or_deleted = True
                print(f"  Исходный MAT удален.")
            except Exception as e_del:
                print(f"  ОШИБКА: Не удалось удалить {mat_path.name} из {MAT_DIR.name}: {e_del}")
    except Exception as e_move_mat:
        print(f"  ОШИБКА: Не удалось переместить/удалить исходный {mat_path.name}: {e_move_mat}")
        print(f"  !!! ВНИМАНИЕ: PNG мог быть извлечен, но MAT остался в {MAT_DIR.name}!")
    return mat_moved_or_deleted

def handle_single_texture_mat(mat_path, base_name, std_format):
    """Обрабатывает MAT файл с одной текстурой: извлечение, перемещение PNG и MAT."""
    target_format_dir = FORMAT_DIRS.get(std_format, FORMAT_DIRS["unknown"])
    final_png_path = target_format_dir / f"{base_name}.png"
    expected_output_png = EXTRACTED_DIR / f"{base_name}.png" # Куда matool извлекает

    # 1. Очистка старых файлов
    cleanup_previous_output(base_name, std_format)

    # 2. Извлечение
    print(f"  Извлечение PNG файла...")
    (stdout, stderr), error = run_matool("extract", mat_path)

    if error:
        print(f"  Ошибка при выполнении matool extract для {mat_path.name}. Пропускаем.")
        return None

    # 3. Проверка и перемещение PNG
    if not expected_output_png.exists():
        print(f"  ПРЕДУПРЕЖДЕНИЕ: matool extract завершился успешно (код 0), но PNG не найден: {expected_output_png.name}")
        return None

    print(f"  Извлечение PNG успешно: {expected_output_png.name}")
    png_moved = move_extracted_png(expected_output_png, target_format_dir, final_png_path)

    if not png_moved:
        return None

    # 4. Перемещение MAT (только если PNG успешно перемещен)
    mat_handled = move_processed_mat(mat_path)

    if not mat_handled:
         print(f"  ПРЕДУПРЕЖДЕНИЕ: PNG {final_png_path.name} обработан, но исходный MAT не был перемещен/удален из {MAT_DIR.name}.")

    return final_png_path


def print_summary_report(total_files, skipped_count, processed_count, files_to_upscale_paths):
    """Печатает итоговый отчет о работе скрипта."""
    print("\n--- Скрипт 1 Завершен ---")
    print(f"Всего найдено MAT файлов в {MAT_DIR.name}: {total_files}")
    print(f"Пропущено (уже обработано/отложено): {skipped_count}")
    print(f"Попытка обработки: {processed_count}")
    final_processed_ok = len(files_to_upscale_paths)
    print(f"Успешно извлечено и подготовлено PNG: {final_processed_ok}")
    errors_occurred = processed_count - final_processed_ok # Считаем ошибки из тех, что пытались обработать
    if errors_occurred > 0:
         print(f"Возникло ошибок при обработке (проверьте лог): {errors_occurred}")

    if files_to_upscale_paths:
        print("\nСледующие PNG файлы были извлечены и отсортированы по форматам:")
        print(f"(Пути указаны относительно {EXTRACTED_DIR})")
        relative_paths = []
        for png_path in files_to_upscale_paths:
            try:
                 relative_path = png_path.relative_to(EXTRACTED_DIR)
                 relative_paths.append(str(relative_path))
            except ValueError:
                 relative_paths.append(str(png_path))

        for rel_path_str in sorted(relative_paths):
             print(f"- {rel_path_str}")

        print(f"\nНе забудьте скачать результаты как .webp, переименовать их в 'имя_файла.webp'")
        print(f"и положить в папку: DOWNLOADED_WEBP_DIR (это для Скрипта 2)")
        print("\nЗатем запустите Скрипт 2 (`process_downloaded.py`).")
    else:
        print("\nНе найдено новых MAT файлов для извлечения (или все были пропущены/вызвали ошибки).")
        print(f"Проверьте папки {MAT_DIR.name}, {USED_DIR.name}, {USED_MAT_DIR.name}, {MANUAL_CEL_DIR.name} и лог выше.")


def main():
    # 1. Подготовка
    setup_directories()
    processed_bases = get_processed_bases()
    mat_files = sorted(list(MAT_DIR.glob('*.mat'))) # Сортируем для предсказуемого порядка
    total_mat_files = len(mat_files)
    print(f"\n3. Найдено {total_mat_files} .mat файлов для проверки в {MAT_DIR.name}")

    files_to_upscale_paths = []
    processed_count = 0
    skipped_count = 0
    processed_bases_in_run = set() # Отслеживаем обработанные/пропущенные в ЭТОМ запуске

    # 4. Основной цикл обработки файлов
    print("\n4. Начало обработки файлов...")
    for i, mat_path in enumerate(mat_files):
        base_name = mat_path.stem

        # Фильтрация: пропускаем уже обработанные/отложенные
        if base_name in processed_bases or base_name in processed_bases_in_run:
            if base_name not in processed_bases_in_run: # Считаем пропуск только один раз
                 skipped_count += 1
                 processed_bases_in_run.add(base_name)
            continue # Тихо пропускаем

        processed_count += 1
        processed_bases_in_run.add(base_name) # Добавляем в обработанные в этом запуске
        print(f"\n[{i + 1}/{total_mat_files} | Обработка {processed_count}] Файл: {mat_path.name}")

        # Получение информации
        std_format, has_alpha, texture_count = get_mat_info(mat_path)
        if texture_count is None or std_format is None:
            print(f"  Пропуск: Не удалось получить полную информацию (format={std_format}, count={texture_count}).")
            continue # Переходим к следующему файлу

        print(f"    Информация: Формат={std_format}, Альфа={has_alpha}, Текстур={texture_count}")

        if texture_count > 1:
            handle_multi_texture_mat(mat_path, base_name)
        elif texture_count == 1:
            result_png_path = handle_single_texture_mat(mat_path, base_name, std_format)
            if result_png_path:
                files_to_upscale_paths.append(result_png_path)
        else:
             print(f"  ПРЕДУПРЕЖДЕНИЕ: Количество текстур {texture_count}. Неожиданное значение. Пропускаем.")

    # 5. Итоговый отчет
    print_summary_report(total_mat_files, skipped_count, processed_count, files_to_upscale_paths)

def check_matool_exists():
    """Проверяет наличие matool.exe и выводит сообщение."""
    if MATOOL_EXE.exists():
        print(f"Используется matool.exe из {MATOOL_EXE}")
        return True
    else:
        alt_matool_path = BASE_DIR / "extracted" / "matool.exe"
        if alt_matool_path.exists():
            print(f"ПРЕДУПРЕЖДЕНИЕ: matool.exe не найден в {MATOOL_EXE}, но найден в {alt_matool_path}. Используем найденный, но рекомендуется переместить его в {BASE_DIR}.")
            return True
        else:
            print(f"КРИТИЧЕСКАЯ ОШИБКА: matool.exe не найден ни в {MATOOL_EXE}, ни в {alt_matool_path}.")
            return False

if __name__ == "__main__":
     if check_matool_exists():
        main()
     else:
        print("\nРабота скрипта прервана из-за отсутствия matool.exe.")
        sys.exit(1)