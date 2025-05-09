import re
import shutil
from pathlib import Path
import time
import sys
from conf import Config
from matool import Tool

def get_cel_index(path: Path) -> int | float:
    """Извлекает числовой индекс из имени файла __cel_N.png"""
    match = re.search(r'__cel_(\d+)\.png$', path.name, re.IGNORECASE)
    # Возвращаем большое число, если индекс не найден, чтобы они оказались в конце при ошибке
    return int(match.group(1)) if match else float('inf')

def setup_directories_cel_pack():
    print("1. Проверка/создание необходимых папок...")
    Config.FINAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    Config.USED_MANUAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    Config.USED_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для финальных MAT: {Config.FINAL_MAT_DIR.relative_to(Config.BASE_DIR)}")
    print(f"   Папка с исходными CEL MAT: {Config.USED_MANUAL_MAT_DIR.relative_to(Config.BASE_DIR)}")
    print(f"   Папка для использованных PNG: {Config.USED_DIR.relative_to(Config.BASE_DIR)}")
    if not Config.PROCESSED_PNG_DIR.exists() or not Config.PROCESSED_PNG_DIR.is_dir():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с обработанными PNG ({Config.PROCESSED_PNG_DIR}) не найдена!")
        sys.exit(1)
    if not Config.USED_MANUAL_MAT_DIR.exists() or not Config.USED_MANUAL_MAT_DIR.is_dir():
         print(f"КРИТИЧЕСКАЯ ОШИБКА: Не найдена папка с исходными CEL MAT ({Config.USED_MANUAL_MAT_DIR})!")
         sys.exit(1)
    print("   Папки проверены/созданы.")

def find_and_group_cel_pngs():
    """Находит CEL PNG в PROCESSED_PNG_DIR и группирует их по базовому имени."""
    print(f"\n2. Поиск и группировка CEL PNG файлов в {Config.PROCESSED_PNG_DIR.name}...")
    cel_png_files = list(Config.PROCESSED_PNG_DIR.glob('*__cel_*.png'))
    if not cel_png_files:
        print(f"   Папка {Config.PROCESSED_PNG_DIR.name} не содержит PNG файлов с '__cel_' в имени.")
        return {}

    cel_groups = {}
    malformed_count = 0
    for png_path in cel_png_files:
        base_name_match = re.match(r'(.+)__cel_\d+', png_path.stem, re.IGNORECASE)
        if base_name_match:
            base_name = base_name_match.group(1)
            if base_name not in cel_groups:
                cel_groups[base_name] = []
            cel_groups[base_name].append(png_path)
        else:
             print(f"   ПРЕДУПРЕЖДЕНИЕ: Не удалось извлечь базовое имя из {png_path.name} (ожидался формат 'name__cel_N.png')")
             malformed_count += 1

    print(f"   Найдено {len(cel_png_files)} CEL PNG файлов, сгруппированных по {len(cel_groups)} базовым именам.")
    if malformed_count > 0:
        print(f"   (Обнаружено {malformed_count} файлов с некорректным форматом имени __cel_)")
    return cel_groups

def check_if_cel_packed(final_mat_path: Path, png_group: list[Path]):
    if final_mat_path.exists():
        print(f"  Пропуск: Финальный файл {final_mat_path.name} уже существует в {Config.FINAL_MAT_DIR.name}.")
        print(f"    Перемещение {len(png_group)} связанных PNG -> {Config.USED_DIR.name}...")
        moved_png_count = 0
        Config.USED_DIR.mkdir(parents=True, exist_ok=True)
        for png_to_move in png_group:
            if png_to_move.exists():
                try:
                    used_target = Config.USED_DIR / png_to_move.name
                    shutil.move(str(png_to_move), str(used_target))
                    moved_png_count += 1
                except OSError as e: print(f"      ПРЕДУПРЕЖДЕНИЕ: Не удалось переместить {png_to_move.name}: {e}")
        print(f"    Перемещено: {moved_png_count} PNG.")
        return True
    return False

def get_original_cel_mat_info(mt: Tool, original_mat_path: Path):
    """Проверяет наличие исходного MAT и возвращает формат и кол-во текстур."""
    if not original_mat_path.exists():
        print(f"  ОШИБКА: Исходный CEL MAT ({original_mat_path.name}) не найден в {Config.USED_MANUAL_MAT_DIR.name}.")
        return None, None

    print(f"  Получение инфо из {original_mat_path.name}...")
    info_dict = mt.info(original_mat_path)

    if info_dict.get('error'):
        print(f"  ОШИБКА: Не удалось получить инфо из {original_mat_path.name}: {info_dict['error']}")
        return None, None

    std_format = info_dict.get('format_standardized')
    format_raw = info_dict.get('format_raw')
    original_texture_count = info_dict.get('texture_count')

    packing_format = None
    if format_raw and format_raw.replace('-', '') in ["rgb565", "rgba4444", "rgba5551"]:
         packing_format = format_raw
    elif std_format and std_format in ["rgb565", "rgba4444", "rgba5551"]:
         packing_format = std_format
    else:
        print(f"  ОШИБКА: Не удалось определить корректный формат для 'create' ({std_format=}, {format_raw=}) из {original_mat_path.name}.")
        return None, None

    if original_texture_count is None:
         print(f"  ОШИБКА: Не удалось определить исходное количество текстур из {original_mat_path.name}.")
         return None, None
    if original_texture_count <= 1:
         print(f"  ПРЕДУПРЕЖДЕНИЕ: Исходный MAT ({original_mat_path.name}) содержит {original_texture_count} текстур, но находится в папке для CEL. Проверьте файл.")

    print(f"    Формат для create: {packing_format}, Ожидаемое кол-во текстур: {original_texture_count}")
    return packing_format, original_texture_count

def sort_and_validate_pngs(png_group: list[Path], expected_count: int, base_name: str):
    """Сортирует PNG по индексу __cel_N и проверяет их количество."""
    print(f"  Сортировка и проверка {len(png_group)} PNG для группы {base_name}...")
    if not png_group:
         print("  ОШИБКА: Список PNG для сортировки пуст.")
         return None

    try:
        sorted_png_paths = sorted(png_group, key=get_cel_index)
        invalid_indexed_files = [p.name for p in sorted_png_paths if get_cel_index(p) == float('inf')]
        if invalid_indexed_files:
             print(f"  ОШИБКА: Не удалось извлечь числовой индекс __cel_N из следующих файлов:")
             for f_name in invalid_indexed_files: print(f"    - {f_name}")
             return None
        print(f"    Отсортированные PNG ({len(sorted_png_paths)} шт.): {[p.name for p in sorted_png_paths]}")
    except Exception as e_sort:
         print(f"  ОШИБКА при сортировке PNG файлов: {e_sort}")
         return None

    if len(sorted_png_paths) != expected_count:
        print(f"  ОШИБКА: Количество найденных/отсортированных PNG ({len(sorted_png_paths)}) не совпадает с ожидаемым из MAT ({expected_count}).")
        print(f"           Проверьте файлы {base_name}__cel_*.png в папке {Config.PROCESSED_PNG_DIR.name}.")
        return None

    print(f"    Количество PNG ({len(sorted_png_paths)}) совпадает с ожидаемым ({expected_count}).")
    return sorted_png_paths

def pack_cel_pngs_to_mat(mt: Tool, packing_format: str, final_mat_path: Path, sorted_png_paths: list[Path]):
    """Выполняет matool create для CEL файлов, проверяет результат."""
    pack_successful = False
    if not sorted_png_paths:
         print("  ОШИБКА: Список PNG для запаковки пуст.")
         return False
    try:
        print(f"  Запаковка {len(sorted_png_paths)} PNG в {final_mat_path.name} (формат: {packing_format})...")
        create_ok = mt.create(packing_format, final_mat_path, *sorted_png_paths)

        if not create_ok:
            print(f"  ОШИБКА: matool create завершился с ошибкой.")
            return False

        time.sleep(0.2)

        if final_mat_path.exists():
            print(f"  Успех: matool создал файл {final_mat_path.name} в {Config.FINAL_MAT_DIR.name}.")
            pack_successful = True
        else:
            fallback_path = Config.BASE_DIR / final_mat_path.name
            if fallback_path.exists():
                print(f"  ПРЕДУПРЕЖДЕНИЕ: matool создал файл в {Config.BASE_DIR.name}!")
                print(f"    Перемещение {fallback_path.name} -> {final_mat_path.relative_to(Config.BASE_DIR)}...")
                try:
                    Config.FINAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(fallback_path), str(final_mat_path))
                    print("      Перемещение успешно.")
                    pack_successful = True
                except Exception as move_error:
                    print(f"    ОШИБКА при перемещении файла из {Config.BASE_DIR.name}: {move_error}")
                    pack_successful = False
            else:
                print(f"  ОШИБКА: matool сообщил об успехе (код 0), но финальный файл {final_mat_path.name} не найден!")
                pack_successful = False

    except Exception as e:
        print(f"  КРИТИЧЕСКАЯ ОШИБКА во время вызова matool create: {e}")
        pack_successful = False

    return pack_successful

def verify_packed_cel_mat(mt: Tool, final_mat_path: Path, expected_count: int):
    """Проверяет количество текстур в созданном MAT файле."""
    if not final_mat_path.exists():
         print(f"  ОШИБКА верификации: Файл {final_mat_path.name} не найден.")
         return False

    print(f"  Верификация: проверка кол-ва текстур в {final_mat_path.name}...")
    info_dict = mt.info(final_mat_path)

    if info_dict.get('error'):
        print(f"  ОШИБКА верификации: Не удалось получить информацию о новом файле: {info_dict['error']}")
        # Пытаемся удалить некорректный файл
        try: final_mat_path.unlink(); print(f"    Некорректный файл {final_mat_path.name} удален.")
        except OSError: print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить некорректный файл {final_mat_path.name}.")
        return False

    new_texture_count = info_dict.get('texture_count')
    if new_texture_count is None:
        print(f"  ОШИБКА верификации: Не удалось определить количество текстур в новом файле.")
        try: final_mat_path.unlink(); print(f"    Некорректный файл {final_mat_path.name} удален.")
        except OSError: print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить некорректный файл {final_mat_path.name}.")
        return False

    if new_texture_count != expected_count:
        print(f"  КРИТИЧЕСКАЯ ОШИБКА ВЕРИФИКАЦИИ: Количество текстур в новом файле ({new_texture_count}) не совпадает с ожидаемым ({expected_count})!")
        try: final_mat_path.unlink(); print(f"    Некорректный файл {final_mat_path.name} удален.")
        except OSError: print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить некорректный файл {final_mat_path.name}.")
        return False

    print(f"    Верификация количества текстур пройдена ({new_texture_count}).")
    return True

def cleanup_after_cel_packing(sorted_png_paths: list[Path], original_mat_path: Path):
    """Перемещает использованные PNG и удаляет оригинальный MAT."""
    print("  Запаковка и проверка прошли успешно. Начинаем очистку...")
    cleanup_error = False
    Config.USED_DIR.mkdir(parents=True, exist_ok=True)
    moved_png_count = 0

    print(f"    Перемещение {len(sorted_png_paths)} обработанных PNG -> {Config.USED_DIR.name}...")
    for png_to_move in sorted_png_paths:
        if png_to_move.exists():
            try:
                used_target = Config.USED_DIR / png_to_move.name
                shutil.move(str(png_to_move), str(used_target))
                moved_png_count += 1
            except OSError as e:
                print(f"      ПРЕДУПРЕЖДЕНИЕ: Не удалось переместить {png_to_move.name}: {e}")
                cleanup_error = True

    print(f"    Перемещено: {moved_png_count} PNG.")

    if original_mat_path.exists():
        print(f"    Удаление оригинального MAT ({original_mat_path.name}) из {Config.USED_MANUAL_MAT_DIR.name}...")
        try:
            original_mat_path.unlink()
        except OSError as e:
            print(f"      ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {original_mat_path.name}: {e}")
            cleanup_error = True
    else:
         print(f"    ПРЕДУПРЕЖДЕНИЕ: Оригинальный MAT {original_mat_path.name} не найден для удаления (возможно, уже удален).")

    if cleanup_error:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Возникли ошибки при очистке файлов.")
    else:
        print(f"  Очистка завершена успешно.")

    return not cleanup_error # True если успешно, False если были ошибки

def process_cel_group(mt: Tool, base_name: str, png_group: list[Path]):
    """Полный цикл обработки одной группы CEL файлов."""
    print(f"\n--- Обработка группы: {base_name} ({len(png_group)} PNG) ---")

    original_mat_path = Config.USED_MANUAL_MAT_DIR / f"{base_name}.mat"
    final_mat_path = Config.FINAL_MAT_DIR / f"{base_name}.mat"

    # 1. Проверить, не запакован ли уже
    if check_if_cel_packed(final_mat_path, png_group):
        return "skipped"

    # 2. Получить формат и кол-во из исходного MAT (передаем mt)
    packing_format, original_texture_count = get_original_cel_mat_info(mt, original_mat_path)
    if packing_format is None or original_texture_count is None:
        return "error_mat_info"

    # 3. Отсортировать и проверить кол-во PNG
    sorted_png_paths = sort_and_validate_pngs(png_group, original_texture_count, base_name)
    if sorted_png_paths is None:
        return "error_png_mismatch"

    # 4. Запаковать PNG в MAT (передаем mt)
    pack_ok = pack_cel_pngs_to_mat(mt, packing_format, final_mat_path, sorted_png_paths)
    if not pack_ok:
        return "error_packing"

    # 5. Верифицировать созданный MAT (передаем mt)
    verify_ok = verify_packed_cel_mat(mt, final_mat_path, original_texture_count)
    if not verify_ok:
        return "error_verification" # Ошибка верификации (файл удален)

    # 6. Очистить исходные файлы (PNG и MAT)
    cleanup_ok = cleanup_after_cel_packing(sorted_png_paths, original_mat_path)
    if not cleanup_ok:
        return "success_with_cleanup_issue"

    return "success"

def print_summary_report_cel_pack(total_groups, status_counts):
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
        if error_packing > 0: print(f"    - Ошибка запаковки MAT (matool create): {error_packing}")
        if error_verification > 0: print(f"    - Ошибка верификации созданного MAT (файл удален): {error_verification}")
        print("  Просмотрите лог выше для информации по конкретным группам.")

    print(f"\nФинальные MAT файлы находятся в: {Config.FINAL_MAT_DIR.name}")
    print(f"Использованные CEL PNG перемещены в: {Config.USED_DIR.name}")
    print(f"Оригинальные CEL MAT (успешно обработанные) удалены из: {Config.USED_MANUAL_MAT_DIR.name}")

    remaining_cel_png = list(Config.PROCESSED_PNG_DIR.glob('*__cel_*.png'))
    if remaining_cel_png:
        remaining_groups = set()
        for p in remaining_cel_png:
            match = re.match(r'(.+)__cel_\d+', p.stem, re.IGNORECASE)
            if match: remaining_groups.add(match.group(1))
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В {Config.PROCESSED_PNG_DIR.name} остались необработанные CEL PNG ({len(remaining_cel_png)}), затрагивающие {len(remaining_groups)} групп:")
        print(f"  Примеры затронутых групп: {sorted(list(remaining_groups))[:5]}")

    remaining_cel_mat = list(Config.USED_MANUAL_MAT_DIR.glob('*.mat'))
    if remaining_cel_mat:
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В {Config.USED_MANUAL_MAT_DIR.name} остались оригинальные CEL MAT ({len(remaining_cel_mat)}), которые не были обработаны из-за ошибок:")
        print(f"  Примеры: {[f.name for f in remaining_cel_mat[:5]]}")

    lingering_base_mats = [p for p in Config.BASE_DIR.glob('*.mat') if p.is_file() and p.name.lower() != Config.MATOOL_FILENAME.lower() and '__cel_' not in p.name]
    if lingering_base_mats:
         print(f"\nПРЕДУПРЕЖДЕНИЕ: В основной папке ({Config.BASE_DIR.name}) обнаружены MAT файлы ({len(lingering_base_mats)}) БЕЗ __cel_, которые могли остаться из-за ошибок перемещения:")
         print(f"  Примеры: {[f.name for f in lingering_base_mats[:5]]}")

def main():
    """Фаза 4: Запаковка CEL PNG в MAT"""
    print("\n--- Скрипт 4: Запаковка CEL файлов ---")

    # 1. Подготовка
    setup_directories_cel_pack()

    try:
        mt = Tool(Config.MATOOL_EXE_PRIMARY, Config.BASE_DIR, Config.MATOOL_EXE_ALT)
    except FileNotFoundError as e:
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать matool: {e}")
        print("Работа скрипта прервана.")
        sys.exit(1)

    cel_groups = find_and_group_cel_pngs()
    if not cel_groups:
        print("\nРабота скрипта завершена, так как нет CEL PNG файлов для обработки.")
        return

    # 2. Основной цикл обработки по группам
    print("\n3. Начало запаковки групп...")
    status_counts = {}
    total_groups = len(cel_groups)
    sorted_group_items = sorted(cel_groups.items()) # Сортируем по имени базы

    for i, (base_name, png_group) in enumerate(sorted_group_items):
        status = process_cel_group(mt, base_name, png_group)
        status_counts[status] = status_counts.get(status, 0) + 1

    # 3. Итоговый отчет
    print_summary_report_cel_pack(total_groups, status_counts)

if __name__ == "__main__":
     main()