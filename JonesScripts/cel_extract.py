import sys
import shutil
from pathlib import Path
# --- НОВЫЕ ИМПОРТЫ ---
from conf import Config
from matool import Tool

# --- ИНИЦИАЛИЗАЦИЯ CONFIG И MATOOL ---
config = Config()
try:
    matool = Tool(
        primary_exe_path=config.MATOOL_EXE_PRIMARY,
        cwd=config.BASE_DIR, # Команды matool будут выполняться из BASE_DIR
        alternative_exe_path=config.MATOOL_EXE_ALT
    )
except FileNotFoundError as e:
    print(f"\nКРИТИЧЕСКАЯ ОШИБКА: {e}")
    print("Работа скрипта прервана из-за отсутствия matool.exe.")
    sys.exit(1)
# --- КОНЕЦ ИНИЦИАЛИЗАЦИИ ---

# --- Вспомогательные функции (run_matool и get_mat_info УДАЛЕНЫ) ---

def setup_directories_cel_extract():
    """Проверяет и создает необходимые директории для извлечения CEL MAT."""
    print("1. Проверка/создание необходимых папок...")
    config.MANUAL_CEL_DIR.mkdir(parents=True, exist_ok=True)
    config.EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    config.USED_MANUAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    for fmt_dir in config.FORMAT_DIRS.values():
        fmt_dir.mkdir(parents=True, exist_ok=True)
    print(f"   Папка с CEL MAT для извлечения: {config.MANUAL_CEL_DIR.name}")
    print(f"   Папка для извлеченных PNG: {config.EXTRACTED_DIR.name} (с подпапками форматов)")
    print(f"   Папка для использованных CEL MAT: {config.USED_MANUAL_MAT_DIR.name}")
    print("   Папки проверены/созданы.")

def find_cel_mats_to_extract():
    """Находит MAT файлы в папке MANUAL_CEL_DIR."""
    print(f"\n2. Поиск MAT файлов в {config.MANUAL_CEL_DIR.name}...")
    mat_files = sorted(list(config.MANUAL_CEL_DIR.glob('*.mat')))
    if not mat_files:
        print(f"   Папка {config.MANUAL_CEL_DIR.name} пуста. Нет MAT файлов для извлечения.")
        return []
    print(f"   Найдено {len(mat_files)} .mat файлов для извлечения.")
    return mat_files

def cleanup_previous_cel_pngs(base_name, target_format_dir, actual_extract_output_dir):
    """Удаляет старые PNG файлы для данного base_name из папки формата и корня extracted."""
    # actual_extract_output_dir здесь будет config.EXTRACTED_DIR, так как matool.exe,
    # запущенный из config.BASE_DIR, вероятно, извлекает в подпапку 'extracted'.
    print(f"  Очистка предыдущих PNG для {base_name}__cel_*...")
    # В папке формата
    existing_format_pngs = list(target_format_dir.glob(f"{base_name}__cel_*.png"))
    if existing_format_pngs:
        print(f"    Удаление {len(existing_format_pngs)} старых PNG из {target_format_dir.name}...")
        for old_png in existing_format_pngs:
            try: old_png.unlink()
            except OSError as e: print(f"      Не удалось удалить {old_png.name}: {e}")
    # В корне extracted (actual_extract_output_dir)
    existing_root_pngs = list(actual_extract_output_dir.glob(f"{base_name}__cel_*.png"))
    if existing_root_pngs:
        print(f"    Удаление {len(existing_root_pngs)} старых PNG из {actual_extract_output_dir.name}...")
        for old_png in existing_root_pngs:
            try: old_png.unlink()
            except OSError as e: print(f"      Не удалось удалить {old_png.name}: {e}")

# extract_cel_mat функция больше не нужна, используется matool.extract()

def find_and_move_extracted_cels(base_name, actual_extract_output_dir, target_format_dir):
    """Находит извлеченные PNG в actual_extract_output_dir и перемещает их в папку формата."""
    # actual_extract_output_dir здесь config.EXTRACTED_DIR
    extracted_pngs_in_root = list(actual_extract_output_dir.glob(f"{base_name}__cel_*.png"))

    if not extracted_pngs_in_root:
        print(f"  ПРЕДУПРЕЖДЕНИЕ/ОШИБКА: matool extract завершился, но PNG файлы для {base_name}__cel_*.png не найдены в {actual_extract_output_dir.name}.")
        return False

    print(f"  Найдено {len(extracted_pngs_in_root)} извлеченных PNG в {actual_extract_output_dir.name}.")
    moved_count = 0
    move_errors = 0
    target_format_dir.mkdir(parents=True, exist_ok=True)

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
        return False

    print(f"  Успешно перемещено {moved_count} PNG файлов в {target_format_dir.name}.")
    return True

def move_processed_cel_mat(mat_path):
    """Перемещает исходный CEL MAT в папку USED_MANUAL_MAT_DIR."""
    mat_moved_or_deleted = False
    used_manual_mat_target = config.USED_MANUAL_MAT_DIR / mat_path.name
    try:
        if not used_manual_mat_target.exists():
            print(f"  Перемещение исходного MAT {mat_path.name} -> {config.USED_MANUAL_MAT_DIR.name}")
            shutil.move(str(mat_path), str(used_manual_mat_target))
            mat_moved_or_deleted = True
        else:
             print(f"  ПРЕДУПРЕЖДЕНИЕ: MAT {mat_path.name} уже существует в {config.USED_MANUAL_MAT_DIR.name}.")
             print(f"    Удаляем исходный из {config.MANUAL_CEL_DIR.name}...")
             try:
                 mat_path.unlink()
                 mat_moved_or_deleted = True
                 print(f"    Исходный файл удален.")
             except Exception as e_del:
                 print(f"    ОШИБКА: Не удалось удалить {mat_path.name}: {e_del}")

    except Exception as e_mat_move:
         print(f"  ОШИБКА при перемещении/удалении исходного MAT {mat_path.name}: {e_mat_move}")
         print(f"  !!! ВНИМАНИЕ: PNG извлечены, но MAT остался в {config.MANUAL_CEL_DIR.name}!")
         mat_moved_or_deleted = False
    return mat_moved_or_deleted

def process_single_cel_mat(mat_path, actual_extract_output_dir):
    """Полный цикл обработки одного CEL MAT файла."""
    base_name = mat_path.stem
    print(f"\nОбработка: {mat_path.name}")

    info_result = matool.info(mat_path) # Используем matool.info
    if info_result['error']:
        # matool.info уже вывел подробности ошибки
        print(f"  ОШИБКА: Не удалось получить информацию для {mat_path.name}. Пропускаем.")
        return "error_info"

    std_format = info_result['format_standardized']
    has_alpha = info_result['has_alpha']
    texture_count = info_result['texture_count']

    if texture_count is None: # std_format может быть 'unknown', но не None если нет info_result['error']
        print(f"  ОШИБКА: Не удалось получить полную информацию (format={std_format}, count=None). Пропускаем.")
        return "error_info"

    if texture_count <= 1:
         print(f"  ПРЕДУПРЕЖДЕНИЕ: Файл {mat_path.name} имеет {texture_count} текстур (ожидалось > 1). Пропускаем извлечение этим скриптом.")
         return "skipped_low_tex_count"

    print(f"    Информация: Формат={std_format}, Альфа={has_alpha}, Текстур={texture_count}")
    target_format_dir = config.FORMAT_DIRS.get(std_format, config.FORMAT_DIRS["unknown"])

    cleanup_previous_cel_pngs(base_name, target_format_dir, actual_extract_output_dir)

    print(f"  Извлечение PNG из {mat_path.name}...")
    extract_ok = matool.extract(mat_path) # Используем matool.extract
    if not extract_ok:
        # matool.extract() уже выводит информацию об ошибке
        return "error_extract"

    move_png_ok = find_and_move_extracted_cels(base_name, actual_extract_output_dir, target_format_dir)
    if not move_png_ok:
        return "error_move_png"

    move_mat_ok = move_processed_cel_mat(mat_path)
    if not move_mat_ok:
        return "error_move_mat"

    return "success"

def print_summary_report_cel_extract(total_files, status_counts):
    """Печатает итоговый отчет для извлечения CEL MAT."""
    print("\n--- Скрипт 1.5 Завершен ---") # Название скрипта условное
    print(f"Всего найдено MAT файлов в {config.MANUAL_CEL_DIR.name}: {total_files}")

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

    print(f"\nИсходные CEL MAT после обработки перемещены в: {config.USED_MANUAL_MAT_DIR.name}")
    print(f"Извлеченные PNG файлы находятся в папках форматов внутри: {config.EXTRACTED_DIR.name}")
    print(f"\nТеперь запустите Скрипт 2 для апскейла извлеченных PNG файлов.")
    print(f"После этого запустите Скрипт для запаковки результатов CEL MAT (аналог Скрипта 3, но для CEL).")


def main():
    """Фаза 1.5: Извлечение CEL MAT в PNG"""
    print("\n--- Скрипт (извлечение CEL MAT): Извлечение CEL MAT в PNG ---") # Название скрипта условное

    setup_directories_cel_extract()
    mat_files = find_cel_mats_to_extract()
    if not mat_files:
        print("\nРабота скрипта завершена, так как нет файлов для обработки.")
        return

    # Предполагаем, что matool.exe, запущенный из config.BASE_DIR,
    # извлекает файлы в config.EXTRACTED_DIR (например, config.BASE_DIR / "extracted")
    # Это поведение должно быть согласовано с тем, как работает matool.exe
    actual_extract_output_dir = config.EXTRACTED_DIR

    print("\n3. Начало извлечения файлов...")
    status_counts = {}
    total_files = len(mat_files)

    for i, mat_path in enumerate(mat_files):
        status = process_single_cel_mat(mat_path, actual_extract_output_dir)
        status_counts[status] = status_counts.get(status, 0) + 1

    print_summary_report_cel_extract(total_files, status_counts)

# def check_matool_exists_cel_extract(): -- Эта функция больше не нужна

if __name__ == "__main__":
     main()