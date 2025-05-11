import sys
import shutil
from conf import Config
from matool import Tool

config = Config()
try:
    matool = Tool(
        primary_exe_path=config.MATOOL_EXE_PRIMARY,
        cwd=config.BASE_DIR,
        alternative_exe_path=config.MATOOL_EXE_ALT
    )
except FileNotFoundError as e:
    print(f"\nКРИТИЧЕСКАЯ ОШИБКА: {e}")
    print("Работа скрипта прервана из-за отсутствия matool.exe.")
    sys.exit(1)

def setup_directories():
    """Создает все необходимые директории для работы скрипта."""
    print("--- Скрипт 1: Извлечение MAT в PNG и Сортировка ---")
    print("1. Создание/проверка необходимых папок...")
    config.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    config.USED_DIR.mkdir(parents=True, exist_ok=True)
    config.USED_MAT_DIR.mkdir(parents=True, exist_ok=True)
    config.MANUAL_CEL_DIR.mkdir(parents=True, exist_ok=True)
    for fmt_dir in config.FORMAT_DIRS.values():
        fmt_dir.mkdir(parents=True, exist_ok=True)
    print(f"   Базовые папки: {config.EXTRACTED_DIR}, {config.USED_DIR}, {config.USED_MAT_DIR}, {config.MANUAL_CEL_DIR}")
    print(f"   Подпапки форматов в {config.EXTRACTED_DIR} проверены/созданы.")

def get_processed_bases():
    """Собирает набор базовых имен файлов, которые уже обработаны или отложены."""
    print("\n2. Сбор информации об уже обработанных/отложенных файлах...")
    processed_result_stems_raw = set()
    processed_result_stems_raw.update(f.stem for f in config.USED_DIR.glob('*.png'))

    processed_result_bases_normalized = set()
    for stem in processed_result_stems_raw:
        base_part = stem.split('__cel_')[0] if '__cel_' in stem else stem
        processed_result_bases_normalized.add(base_part)
    print(f"   Найдено {len(processed_result_stems_raw)} результатов (*.png) в {config.USED_DIR.name}, нормализовано до {len(processed_result_bases_normalized)} баз.")

    processed_mat_bases = {f.stem for f in config.USED_MAT_DIR.glob('*.mat')}
    print(f"   Найдено {len(processed_mat_bases)} обработанных MAT (single texture) в {config.USED_MAT_DIR.name}")

    manual_cel_bases = {f.stem for f in config.MANUAL_CEL_DIR.glob('*.mat')}
    print(f"   Найдено {len(manual_cel_bases)} MAT для ручной обработки (__cel_) в {config.MANUAL_CEL_DIR.name}")

    processed_bases = processed_result_bases_normalized.union(processed_mat_bases).union(manual_cel_bases)
    print(f"   Итого {len(processed_bases)} уникальных базовых имен к пропуску.")
    return processed_bases

def handle_multi_texture_mat(mat_path):
    """Обрабатывает MAT файлы с несколькими текстурами (перемещает в MANUAL_CEL_DIR)."""
    print(f"  Обнаружено > 1 текстур. Перемещаем MAT в {config.MANUAL_CEL_DIR.name}.")
    target_path = config.MANUAL_CEL_DIR / mat_path.name
    moved = False
    try:
        if not target_path.exists():
            shutil.move(str(mat_path), str(target_path))
            print(f"  Успешно перемещен.")
            moved = True
        else:
            print(f"  Файл {mat_path.name} уже существует в {config.MANUAL_CEL_DIR.name}. Удаляем исходный из {config.MAT_DIR.name}.")
            try:
                mat_path.unlink()
                print(f"  Исходный файл удален.")
                moved = True
            except Exception as e_del:
                print(f"  ОШИБКА: Не удалось удалить {mat_path.name} из {config.MAT_DIR.name}: {e_del}")
    except Exception as e:
        print(f"  ОШИБКА: Не удалось переместить/удалить {mat_path.name}: {e}")
    return moved

def cleanup_previous_output(base_name, std_format):
    """Удаляет старые/промежуточные PNG файлы перед извлечением."""
    target_format_dir = config.FORMAT_DIRS.get(std_format, config.FORMAT_DIRS["unknown"])
    final_png_path = target_format_dir / f"{base_name}.png"
    expected_output_png = config.EXTRACTED_DIR / f"{base_name}.png"

    if final_png_path.exists():
        print(f"  Удаление старого PNG в папке формата: {final_png_path.relative_to(config.BASE_DIR)}")
        try: final_png_path.unlink()
        except Exception as e: print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {final_png_path.name}: {e}")
    if expected_output_png.exists():
        print(f"  Удаление предыдущего извлеченного PNG: {expected_output_png.relative_to(config.BASE_DIR)}")
        try: expected_output_png.unlink()
        except Exception as e: print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {expected_output_png.name}: {e}")

def move_extracted_png(expected_output_png, target_format_dir, final_png_path):
    """Перемещает извлеченный PNG в соответствующую папку формата."""
    png_moved = False
    try:
        print(f"  Перемещение PNG из {expected_output_png.parent.name}/{expected_output_png.name} -> {target_format_dir.name}/{final_png_path.name}")
        target_format_dir.mkdir(parents=True, exist_ok=True)
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
        used_mat_target_path = config.USED_MAT_DIR / mat_path.name
        if not used_mat_target_path.exists():
            print(f"  Перемещение исходного MAT файла -> {config.USED_MAT_DIR.name}")
            shutil.move(str(mat_path), str(used_mat_target_path))
            print(f"  Исходный MAT успешно перемещен.")
            mat_moved_or_deleted = True
        else:
            print(f"  ПРЕДУПРЕЖДЕНИЕ: MAT {mat_path.name} уже существует в {config.USED_MAT_DIR.name}. Удаляем исходный из {config.MAT_DIR.name}.")
            try:
                mat_path.unlink()
                mat_moved_or_deleted = True
                print(f"  Исходный MAT удален.")
            except Exception as e_del:
                print(f"  ОШИБКА: Не удалось удалить {mat_path.name} из {config.MAT_DIR.name}: {e_del}")
    except Exception as e_move_mat:
        print(f"  ОШИБКА: Не удалось переместить/удалить исходный {mat_path.name}: {e_move_mat}")
        print(f"  !!! ВНИМАНИЕ: PNG мог быть извлечен, но MAT остался в {config.MAT_DIR.name}!")
    return mat_moved_or_deleted

def handle_single_texture_mat(mat_path, base_name, std_format):
    """Обрабатывает MAT файл с одной текстурой: извлечение, перемещение PNG и MAT."""
    target_format_dir = config.FORMAT_DIRS.get(std_format, config.FORMAT_DIRS["unknown"])
    final_png_path = target_format_dir / f"{base_name}.png"
    expected_output_png = config.EXTRACTED_DIR / f"{base_name}.png"

    cleanup_previous_output(base_name, std_format)

    print(f"  Извлечение PNG файла...")
    extract_successful = matool.extract(mat_path)

    if not extract_successful:
        # matool.extract() уже выводит информацию об ошибке через run_command
        return None

    if not expected_output_png.exists():
        print(f"  ПРЕДУПРЕЖДЕНИЕ: matool extract сообщил об успехе, но PNG не найден: {expected_output_png.name}")
        return None

    print(f"  Извлечение PNG успешно: {expected_output_png.name}")
    png_moved = move_extracted_png(expected_output_png, target_format_dir, final_png_path)

    if not png_moved:
        return None

    mat_handled = move_processed_mat(mat_path)

    if not mat_handled:
         print(f"  ПРЕДУПРЕЖДЕНИЕ: PNG {final_png_path.name} обработан, но исходный MAT не был перемещен/удален из {config.MAT_DIR.name}.")

    return final_png_path


def print_summary_report(total_files, skipped_count, processed_count, files_to_upscale_paths):
    """Печатает итоговый отчет о работе скрипта."""
    print("\n--- Скрипт 1 Завершен ---")
    print(f"Всего найдено MAT файлов в {config.MAT_DIR.name}: {total_files}")
    print(f"Пропущено (уже обработано/отложено): {skipped_count}")
    print(f"Попытка обработки: {processed_count}")
    final_processed_ok = len(files_to_upscale_paths)
    print(f"Успешно извлечено и подготовлено PNG: {final_processed_ok}")
    errors_occurred = processed_count - final_processed_ok
    if errors_occurred > 0:
         print(f"Возникло ошибок при обработке (проверьте лог): {errors_occurred}")

    if files_to_upscale_paths:
        print("\nСледующие PNG файлы были извлечены и отсортированы по форматам:")
        print(f"(Пути указаны относительно {config.EXTRACTED_DIR})")
        relative_paths = []
        for png_path in files_to_upscale_paths:
            try:
                 relative_path = png_path.relative_to(config.EXTRACTED_DIR)
                 relative_paths.append(str(relative_path))
            except ValueError:
                 relative_paths.append(str(png_path))

        for rel_path_str in sorted(relative_paths):
             print(f"- {rel_path_str}")

        print(f"\nНе забудьте обработать эти PNG (например, апскейлом),")
        print(f"и поместить результаты в папку для следующего этапа (например, {config.PROCESSED_PNG_DIR.name}).")
        print("\nЗатем запустите Скрипт для обработки апскейленных файлов и запаковки.")
    else:
        print("\nНе найдено новых MAT файлов для извлечения (или все были пропущены/вызвали ошибки).")
        print(f"Проверьте папки {config.MAT_DIR.name}, {config.USED_DIR.name}, {config.USED_MAT_DIR.name}, {config.MANUAL_CEL_DIR.name} и лог выше.")


def main():
    setup_directories()
    processed_bases = get_processed_bases()
    mat_files = sorted(list(config.MAT_DIR.glob('*.mat')))
    total_mat_files = len(mat_files)
    print(f"\n3. Найдено {total_mat_files} .mat файлов для проверки в {config.MAT_DIR.name}")

    files_to_upscale_paths = []
    processed_count = 0
    skipped_count = 0
    processed_bases_in_run = set()

    print("\n4. Начало обработки файлов...")
    for i, mat_path in enumerate(mat_files):
        base_name = mat_path.stem

        if base_name in processed_bases or base_name in processed_bases_in_run:
            if base_name not in processed_bases_in_run:
                 skipped_count += 1
                 processed_bases_in_run.add(base_name)
            continue

        processed_count += 1
        processed_bases_in_run.add(base_name)
        print(f"\n[{i + 1}/{total_mat_files} | Обработка {processed_count}] Файл: {mat_path.name}")

        info_result = matool.info(mat_path)

        if info_result['error']:
            print(f"  Пропуск: Ошибка получения информации для {mat_path.name}.")
            continue

        std_format = info_result['format_standardized']
        has_alpha = info_result['has_alpha']
        texture_count = info_result['texture_count']

        if texture_count is None: # std_format не может быть None если нет ошибки
            print(f"  Пропуск: Не удалось получить полную информацию (format={std_format}, count=None).")
            continue

        print(f"    Информация: Формат={std_format}, Альфа={has_alpha}, Текстур={texture_count}")

        if texture_count > 1:
            handle_multi_texture_mat(mat_path)
        elif texture_count == 1:
            result_png_path = handle_single_texture_mat(mat_path, base_name, std_format)
            if result_png_path:
                files_to_upscale_paths.append(result_png_path)
        else:
             print(f"  ПРЕДУПРЕЖДЕНИЕ: Количество текстур {texture_count}. Неожиданное значение. Пропускаем.")

    print_summary_report(total_mat_files, skipped_count, processed_count, files_to_upscale_paths)

# def check_matool_exists(): - Эта функция больше не нужна, Tool.__init__ обрабатывает это.

if __name__ == "__main__":
     # Проверка существования matool.exe теперь выполняется при инициализации объекта Tool
     main()