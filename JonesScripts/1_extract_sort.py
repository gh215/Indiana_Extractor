import shutil
from pathlib import Path
import sys
from conf import Config
from matool import Tool

def setup_directories():
    print("--- Скрипт 1: Извлечение MAT в PNG и Сортировка ---")
    print("1. Создание/проверка необходимых папок...")
    Config.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    Config.USED_DIR.mkdir(parents=True, exist_ok=True)
    Config.USED_MAT_DIR.mkdir(parents=True, exist_ok=True)
    Config.MANUAL_CEL_DIR.mkdir(parents=True, exist_ok=True)
    for fmt_dir in Config.FORMAT_DIRS.values():
        fmt_dir.mkdir(parents=True, exist_ok=True)
    print(f"   Базовые папки: {Config.EXTRACTED_DIR.relative_to(Config.BASE_DIR)}, "
          f"{Config.USED_DIR.relative_to(Config.BASE_DIR)}, "
          f"{Config.USED_MAT_DIR.relative_to(Config.BASE_DIR)}, "
          f"{Config.MANUAL_CEL_DIR.relative_to(Config.BASE_DIR)}")
    print(f"   Подпапки форматов в {Config.EXTRACTED_DIR.name} проверены/созданы.")

def get_processed_bases():
    print("\n2. Сбор информации об уже обработанных/отложенных файлах...")
    processed_result_stems_raw = set()
    for ext in Config.VALID_EXTENSIONS:
        processed_result_stems_raw.update(f.stem for f in Config.USED_DIR.glob(f'*{ext}'))

    processed_result_bases_normalized = set()
    for stem in processed_result_stems_raw:
        base_part = stem.split('__cel_')[0] if '__cel_' in stem else stem
        processed_result_bases_normalized.add(base_part)
    print(f"   Найдено {len(processed_result_stems_raw)} результатов ({'/'.join(Config.VALID_EXTENSIONS)}) в {Config.USED_DIR.name}, "
          f"нормализовано до {len(processed_result_bases_normalized)} баз.")

    processed_mat_bases = {f.stem for f in Config.USED_MAT_DIR.glob('*.mat')}
    print(f"   Найдено {len(processed_mat_bases)} обработанных MAT (single texture) в {Config.USED_MAT_DIR.name}")

    manual_cel_bases = {f.stem for f in Config.MANUAL_CEL_DIR.glob('*.mat')}
    print(f"   Найдено {len(manual_cel_bases)} MAT для ручной обработки (__cel_) в {Config.MANUAL_CEL_DIR.name}")

    processed_bases = processed_result_bases_normalized.union(processed_mat_bases).union(manual_cel_bases)
    print(f"   Итого {len(processed_bases)} уникальных базовых имен к пропуску.")
    return processed_bases

def handle_multi_texture_mat(mat_path, base_name):
    print(f"  Обнаружено больше одной текстуры. Перемещаем MAT в {Config.MANUAL_CEL_DIR.name}.")
    target_path = Config.MANUAL_CEL_DIR / mat_path.name
    moved = False
    try:
        if not target_path.exists():
            shutil.move(str(mat_path), str(target_path))
            print(f"    Успешно перемещен.")
            moved = True
        else:
            print(f"    Файл {mat_path.name} уже существует в {Config.MANUAL_CEL_DIR.name}. Удаляем исходный из {Config.MAT_DIR.name}.")
            try:
                mat_path.unlink()
                print(f"    Исходный файл удален.")
                moved = True # Считаем успешной обработкой, т.к. он уже в целевой папке
            except Exception as e_del:
                print(f"    ОШИБКА: Не удалось удалить {mat_path.name} из {Config.MAT_DIR.name}: {e_del}")
    except Exception as e:
        print(f"    ОШИБКА: Не удалось переместить/удалить {mat_path.name}: {e}")
    return moved

def cleanup_previous_output(base_name, std_format):
    target_format_dir = Config.FORMAT_DIRS.get(std_format, Config.FORMAT_DIRS["unknown"])
    final_png_path = target_format_dir / f"{base_name}.png"
    expected_output_png = Config.BASE_DIR / f"{base_name}.png"

    if final_png_path.exists():
        print(f"  Удаление старого PNG в папке формата: {final_png_path.relative_to(Config.BASE_DIR)}")
        try: final_png_path.unlink()
        except Exception as e: print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {final_png_path.name}: {e}")
    if expected_output_png.exists():
        print(f"  Удаление предыдущего извлеченного PNG из CWD: {expected_output_png.relative_to(Config.BASE_DIR)}")
        try: expected_output_png.unlink()
        except Exception as e: print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {expected_output_png.name}: {e}")

def move_extracted_png(expected_output_png, target_format_dir, final_png_path):
    png_moved = False
    try:
        print(f"  Перемещение PNG из {expected_output_png.parent.name}/{expected_output_png.name} -> {target_format_dir.name}/{final_png_path.name}")
        target_format_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(expected_output_png), str(final_png_path))
        print(f"    Успешно перемещено PNG.")
        png_moved = True
    except Exception as e:
        print(f"    ОШИБКА: Не удалось переместить {expected_output_png.name} в {final_png_path.name}: {e}")
    return png_moved

def move_processed_mat(mat_path):
    """Перемещает исходный MAT файл в USED_MAT_DIR после успешной обработки."""
    mat_moved_or_deleted = False
    try:
        used_mat_target_path = Config.USED_MAT_DIR / mat_path.name
        if not used_mat_target_path.exists():
            print(f"  Перемещение исходного MAT файла -> {Config.USED_MAT_DIR.name}")
            shutil.move(str(mat_path), str(used_mat_target_path))
            print(f"    Исходный MAT успешно перемещен.")
            mat_moved_or_deleted = True
        else:
            print(f"    ПРЕДУПРЕЖДЕНИЕ: MAT {mat_path.name} уже существует в {Config.USED_MAT_DIR.name}. Удаляем исходный из {Config.MAT_DIR.name}.")
            try:
                mat_path.unlink()
                mat_moved_or_deleted = True
                print(f"    Исходный MAT удален.")
            except Exception as e_del:
                print(f"    ОШИБКА: Не удалось удалить {mat_path.name} из {Config.MAT_DIR.name}: {e_del}")
    except Exception as e_move_mat:
        print(f"    ОШИБКА: Не удалось переместить/удалить исходный {mat_path.name}: {e_move_mat}")
        print(f"    !!! ВНИМАНИЕ: PNG мог быть извлечен, но MAT остался в {Config.MAT_DIR.name}!")
    return mat_moved_or_deleted

# Используем экземпляр matool.Tool
def handle_single_texture_mat(mt: Tool, mat_path: Path, base_name: str, std_format: str):
    """Обрабатывает MAT файл с одной текстурой: извлечение, перемещение PNG и MAT."""
    target_format_dir = Config.FORMAT_DIRS.get(std_format, Config.FORMAT_DIRS["unknown"])
    final_png_path = target_format_dir / f"{base_name}.png"
    # matool извлекает в CWD (Config.BASE_DIR)
    expected_output_png = Config.BASE_DIR / f"{base_name}.png"

    # 1. Очистка старых файлов
    cleanup_previous_output(base_name, std_format)

    # 2. Извлечение с помощью mt.extract()
    print(f"  Извлечение PNG файла...")
    extract_ok = mt.extract(mat_path) # Возвращает True при успехе

    if not extract_ok:
        print(f"  Ошибка при выполнении matool extract для {mat_path.name}. Пропускаем.")
        # Ошибка уже залогирована внутри mt.extract/run_command
        return None

    # 3. Проверка и перемещение PNG
    if not expected_output_png.exists():
        print(f"  ПРЕДУПРЕЖДЕНИЕ: matool extract завершился успешно, но PNG не найден в CWD: {expected_output_png.name}")
        return None

    print(f"  Извлечение PNG успешно: {expected_output_png.name}")
    png_moved = move_extracted_png(expected_output_png, target_format_dir, final_png_path)

    if not png_moved:
        return None

    # 4. Перемещение MAT (только если PNG успешно перемещен)
    mat_handled = move_processed_mat(mat_path)

    if not mat_handled:
         print(f"  ПРЕДУПРЕЖДЕНИЕ: PNG {final_png_path.name} обработан, но исходный MAT не был перемещен/удален из {Config.MAT_DIR.name}.")

    return final_png_path

def print_summary_report(total_files, skipped_count, processed_count, error_count, files_to_upscale_paths):
    print("\n--- Скрипт 1 Завершен ---")
    print(f"Всего найдено MAT файлов в {Config.MAT_DIR.name}: {total_files}")
    print(f"Пропущено (уже обработано/отложено): {skipped_count}")
    print(f"Попытка обработки: {processed_count}")
    final_processed_ok = len(files_to_upscale_paths)
    print(f"Успешно извлечено и подготовлено PNG: {final_processed_ok}")
    # Ошибки считаем как (попытались обработать - успешно извлекли) + ошибки получения инфо
    errors_occurred = (processed_count - final_processed_ok) + error_count
    if errors_occurred > 0:
         print(f"Возникло ошибок при обработке (вкл. ошибки info/extract, см. лог): {errors_occurred}")

    if files_to_upscale_paths:
        print("\nСледующие PNG файлы были извлечены и отсортированы по форматам:")
        print(f"(Пути указаны относительно {Config.EXTRACTED_DIR})")
        relative_paths = []
        for png_path in files_to_upscale_paths:
            try:
                 relative_path = png_path.relative_to(Config.EXTRACTED_DIR)
                 relative_paths.append(str(relative_path))
            except ValueError:
                 relative_paths.append(str(png_path)) # Если путь внезапно не там

        for rel_path_str in sorted(relative_paths):
             print(f"- {rel_path_str}")

        print("\nЗатем запустите Скрипт 2 (`upscale_and_restore.py`).")
    else:
        print("\nНе найдено новых MAT файлов для извлечения (или все были пропущены/вызвали ошибки).")
        print(f"Проверьте папки {Config.MAT_DIR.name}, {Config.USED_DIR.name}, {Config.USED_MAT_DIR.name}, {Config.MANUAL_CEL_DIR.name} и лог выше.")

def main():
    # 1. Подготовка
    setup_directories()

    try:
        mt = Tool(Config.MATOOL_EXE_PRIMARY, Config.BASE_DIR, Config.MATOOL_EXE_ALT)
    except FileNotFoundError as e:
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать matool: {e}")
        print("Работа скрипта прервана.")
        sys.exit(1)

    processed_bases = get_processed_bases()
    # Используем Config.MAT_DIR
    mat_files = sorted([p for p in Config.MAT_DIR.glob('*.mat') if p.name.lower() != Config.MATOOL_FILENAME.lower()])
    total_mat_files = len(mat_files)
    print(f"\n3. Найдено {total_mat_files} .mat файлов для проверки в {Config.MAT_DIR.name}")

    files_to_upscale_paths = []
    processed_count = 0
    skipped_count = 0
    error_count = 0 # Счетчик ошибок info/texture_count
    processed_bases_in_run = set()

    # 4. Основной цикл обработки файлов
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

        info_dict = mt.info(mat_path)
        if info_dict.get('error'):
            print(f"  Пропуск: Ошибка при получении информации: {info_dict['error']}")
            error_count += 1
            continue

        std_format = info_dict.get('format_standardized', 'unknown')
        has_alpha = info_dict.get('has_alpha', False)
        texture_count = info_dict.get('texture_count')

        if texture_count is None:
            print(f"  Пропуск: Не удалось определить количество текстур из вывода matool.")
            error_count += 1
            continue # Переходим к следующему файлу

        print(f"  Информация: Формат={std_format}, Альфа={has_alpha}, Текстур={texture_count}")

        if texture_count > 1:
            handle_multi_texture_mat(mat_path, base_name)
        elif texture_count == 1:
            # Передаем экземпляр mt в функцию
            result_png_path = handle_single_texture_mat(mt, mat_path, base_name, std_format)
            if result_png_path:
                files_to_upscale_paths.append(result_png_path)
        else:
             print(f"  ПРЕДУПРЕЖДЕНИЕ: Количество текстур {texture_count} (<=0?). Неожиданное значение. Пропускаем.")
             error_count += 1

    print_summary_report(total_mat_files, skipped_count, processed_count, error_count, files_to_upscale_paths)

if __name__ == "__main__":
     main()