import sys
import shutil
from pathlib import Path
import time
import re

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

def get_cel_index(path: Path) -> int | float:
    """Извлекает числовой индекс из имени файла __cel_N.png"""
    match = re.search(r'__cel_(\d+)\.png$', path.name, re.IGNORECASE)
    return int(match.group(1)) if match else float('inf')

def setup_directories_cel_pack():
    """Проверяет и создает необходимые директории для фазы запаковки CEL."""
    print("1. Проверка/создание необходимых папок...")
    config.FINAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    config.USED_MANUAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    config.USED_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для финальных MAT: {config.FINAL_MAT_DIR.name}")
    print(f"   Папка с исходными CEL MAT (для инфо): {config.USED_MANUAL_MAT_DIR.name}")
    print(f"   Папка для использованных PNG: {config.USED_DIR.name}")
    if not config.PROCESSED_PNG_DIR.exists() or not config.PROCESSED_PNG_DIR.is_dir():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с обработанными PNG ({config.PROCESSED_PNG_DIR}) не найдена!")
        sys.exit(1)
    if not config.USED_MANUAL_MAT_DIR.exists() or not config.USED_MANUAL_MAT_DIR.is_dir():
         print(f"КРИТИЧЕСКАЯ ОШИБКА: Не найдена папка с исходными CEL MAT ({config.USED_MANUAL_MAT_DIR})!")
         sys.exit(1)
    print("   Папки проверены/созданы.")

def find_and_group_cel_pngs():
    """Находит CEL PNG в PROCESSED_PNG_DIR и группирует их по базовому имени."""
    print(f"\n2. Поиск и группировка CEL PNG файлов в {config.PROCESSED_PNG_DIR.name}...")
    # Ищем только PNG, так как апскейлер обычно выводит PNG
    cel_png_files = list(config.PROCESSED_PNG_DIR.glob('*__cel_*.png'))
    if not cel_png_files:
        print(f"   Папка {config.PROCESSED_PNG_DIR.name} не содержит файлов с '__cel_' и расширением .png.")
        return {}

    cel_groups = {}
    for png_path in cel_png_files:
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
        print(f"  Пропуск: Финальный файл {final_mat_path.name} уже существует в {config.FINAL_MAT_DIR.name}.")
        print(f"    Перемещение {len(png_group)} связанных PNG -> {config.USED_DIR.name}...")
        moved_png_count = 0
        config.USED_DIR.mkdir(parents=True, exist_ok=True)
        for png_to_move in png_group:
            if png_to_move.exists():
                try:
                    used_target = config.USED_DIR / png_to_move.name
                    shutil.move(str(png_to_move), str(used_target))
                    moved_png_count += 1
                except OSError as e: print(f"      Не удалось переместить {png_to_move.name}: {e}")
        print(f"    Перемещено: {moved_png_count} PNG.")
        return True
    return False

def get_original_cel_mat_info(original_mat_path):
    """Проверяет наличие исходного MAT и возвращает формат и кол-во текстур."""
    if not original_mat_path.exists():
        print(f"  ОШИБКА: Исходный CEL MAT ({original_mat_path.name}) не найден в {config.USED_MANUAL_MAT_DIR.name}.")
        return None, None

    print(f"  Получение инфо из {original_mat_path.name}...")
    info_result = matool.info(original_mat_path) # Используем matool.info

    if info_result['error']:
        # matool.info уже вывело подробности
        print(f"  ОШИБКА: Не удалось получить инфо из {original_mat_path.name} для запаковки.")
        return None, None

    std_format = info_result['format_standardized']
    original_texture_count = info_result['texture_count']

    if std_format is None or std_format == "unknown" or std_format == "rgba":
         print(f"  ОШИБКА: Не удалось определить корректный формат ({std_format}) для запаковки.")
         return None, None # original_texture_count здесь не важен
    if original_texture_count is None:
         print(f"  ОШИБКА: Не удалось определить исходное количество текстур из {original_mat_path.name}.")
         return None, None

    print(f"    Формат для create: {std_format}, Ожидаемое кол-во текстур: {original_texture_count}")
    return std_format, original_texture_count

def sort_and_validate_pngs(png_group, expected_count, base_name):
    """Сортирует PNG по индексу __cel_N и проверяет их количество."""
    print(f"  Сортировка {len(png_group)} PNG для группы {base_name}...")
    try:
        sorted_png_paths = sorted(png_group, key=get_cel_index)
        if any(get_cel_index(p) == float('inf') for p in sorted_png_paths):
             print(f"  ОШИБКА: Не удалось извлечь числовой индекс __cel_N из одного или нескольких PNG файлов для группы {base_name}.")
             return None
        print(f"    Отсортированные PNG: {[p.name for p in sorted_png_paths]}")
    except Exception as e_sort:
         print(f"  ОШИБКА при сортировке PNG файлов для группы {base_name}: {e_sort}")
         return None

    if len(sorted_png_paths) != expected_count:
        print(f"  ОШИБКА: Количество найденных/отсортированных PNG ({len(sorted_png_paths)}) для группы {base_name} не совпадает с ожидаемым ({expected_count}).")
        print(f"           Проверьте файлы {base_name}__cel_*.png в папке {config.PROCESSED_PNG_DIR.name}.")
        return None

    print(f"    Количество PNG ({len(sorted_png_paths)}) совпадает с ожидаемым ({expected_count}).")
    return sorted_png_paths

def pack_cel_pngs_to_mat(std_format, final_mat_path, sorted_png_paths):
    """Выполняет matool create для CEL файлов, проверяет результат."""
    # actual_output_path больше не нужен как отдельный параметр, matool.create работает с final_mat_path
    # matool.create выводит информацию о запуске и stdout/stderr
    success_flag = matool.create(std_format, final_mat_path, *sorted_png_paths)

    if not success_flag:
        return False

    time.sleep(0.2)

    if final_mat_path.exists():
        print(f"  Успех: matool создал {final_mat_path.name} в {final_mat_path.parent.name}.")
        return True
    else:
        print(f"  ОШИБКА: matool create сообщил об успехе (код 0), но новый файл {final_mat_path.name} не найден!")
        return False

def verify_packed_cel_mat(final_mat_path, expected_count):
    """Проверяет количество текстур в созданном MAT файле."""
    print(f"  Проверка количества текстур в новом файле {final_mat_path.name}...")
    info_result = matool.info(final_mat_path) # Используем matool.info

    if info_result['error']:
        print(f"  ОШИБКА: Не удалось получить информацию о новом файле {final_mat_path.name}: {info_result['error']}.")
        try: final_mat_path.unlink(missing_ok=True); print(f"    Попытка удалить некорректный файл {final_mat_path.name}...")
        except OSError: pass
        return False

    new_texture_count = info_result['texture_count']
    if new_texture_count is None:
        print(f"  ОШИБКА: Не удалось определить количество текстур в новом файле {final_mat_path.name}.")
        try: final_mat_path.unlink(missing_ok=True); print(f"    Попытка удалить некорректный файл {final_mat_path.name}...")
        except OSError: pass
        return False

    if new_texture_count != expected_count:
        print(f"  КРИТИЧЕСКАЯ ОШИБКА: Количество текстур в новом файле ({new_texture_count}) не совпадает с ожидаемым ({expected_count})!")
        try: final_mat_path.unlink(missing_ok=True); print(f"    Попытка удалить некорректный файл {final_mat_path.name}...")
        except OSError: pass
        return False

    print(f"    Проверка количества текстур пройдена ({new_texture_count}).")
    return True

def cleanup_after_cel_packing(sorted_png_paths, original_mat_path):
    """Перемещает использованные PNG и удаляет оригинальный MAT из used_manual_mat."""
    print("  Запаковка и проверка прошли успешно. Начинаем очистку...")
    cleanup_error = False
    config.USED_DIR.mkdir(parents=True, exist_ok=True)
    moved_png_count = 0

    print(f"    Перемещение {len(sorted_png_paths)} обработанных PNG -> {config.USED_DIR.name}...")
    for png_to_move in sorted_png_paths:
        if png_to_move.exists():
            try:
                used_target = config.USED_DIR / png_to_move.name
                shutil.move(str(png_to_move), str(used_target))
                moved_png_count += 1
            except OSError as e:
                print(f"      Не удалось переместить {png_to_move.name}: {e}")
                cleanup_error = True
        else:
             print(f"      ПРЕДУПРЕЖДЕНИЕ: PNG {png_to_move.name} не найден для перемещения.")
    print(f"    Перемещено: {moved_png_count} PNG.")

    if original_mat_path.exists():
        print(f"    Удаление оригинального MAT ({original_mat_path.name}) из {config.USED_MANUAL_MAT_DIR.name}...")
        try:
            original_mat_path.unlink()
        except OSError as e:
            print(f"      ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {original_mat_path.name}: {e}")
            cleanup_error = True
    else:
         print(f"    ПРЕДУПРЕЖДЕНИЕ: Оригинальный MAT {original_mat_path.name} не найден для удаления из {config.USED_MANUAL_MAT_DIR.name}.")

    if cleanup_error:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Возникли ошибки при очистке файлов.")
    else:
        print(f"  Очистка завершена успешно.")
    return not cleanup_error

def process_cel_group(base_name, png_group):
    """Полный цикл обработки одной группы CEL файлов."""
    print(f"\nОбработка группы: {base_name}")
    print(f"  Найдено PNG для группы: {len(png_group)}")

    original_mat_path = config.USED_MANUAL_MAT_DIR / f"{base_name}.mat"
    final_mat_path = config.FINAL_MAT_DIR / f"{base_name}.mat"

    if check_if_cel_packed(final_mat_path, png_group):
        return "skipped"

    std_format, original_texture_count = get_original_cel_mat_info(original_mat_path)
    if std_format is None:
        return "error_mat_info"

    sorted_png_paths = sort_and_validate_pngs(png_group, original_texture_count, base_name)
    if sorted_png_paths is None:
        return "error_png_mismatch"

    pack_ok = pack_cel_pngs_to_mat(std_format, final_mat_path, sorted_png_paths)
    if not pack_ok:
        lingering_mat_in_base = config.BASE_DIR / f"{base_name}.mat"
        if lingering_mat_in_base.exists() and lingering_mat_in_base.name != config.MATOOL_FILENAME:
            print(f"  ПРЕДУПРЕЖДЕНИЕ: Обнаружен MAT ({lingering_mat_in_base.name}) в {config.BASE_DIR}, который мог остаться после ошибки.")
        return "error_packing"

    verify_ok = verify_packed_cel_mat(final_mat_path, original_texture_count)
    if not verify_ok:
        return "error_verification"

    cleanup_ok = cleanup_after_cel_packing(sorted_png_paths, original_mat_path)
    if not cleanup_ok:
        return "success_with_cleanup_issue"

    return "success"

def print_summary_report_cel_pack(total_groups, status_counts):
    """Печатает итоговый отчет для фазы запаковки CEL."""
    print("\n--- Скрипт (Запаковка CEL MAT) Завершен ---") # Условное название
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

    print(f"\nФинальные MAT файлы находятся в: {config.FINAL_MAT_DIR.name}")
    print(f"Использованные CEL PNG перемещены в: {config.USED_DIR.name}")
    print(f"Оригинальные CEL MAT (успешно обработанные) удалены из: {config.USED_MANUAL_MAT_DIR.name}")

    remaining_cel_png = list(config.PROCESSED_PNG_DIR.glob('*__cel_*.png'))
    if remaining_cel_png:
        remaining_groups = set()
        for p in remaining_cel_png:
            match = re.match(r'(.+)__cel_\d+', p.stem, re.IGNORECASE)
            if match: remaining_groups.add(match.group(1))
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В {config.PROCESSED_PNG_DIR.name} остались необработанные CEL PNG ({len(remaining_cel_png)}), затрагивающие {len(remaining_groups)} групп:")
        print(f"  Примеры затронутых групп: {list(remaining_groups)[:5]}")

    lingering_mats = [p for p in config.BASE_DIR.glob('*.mat') if p.is_file() and p.name != config.MATOOL_FILENAME]
    # Уточним, чтобы не выводить __cel_ в lingering_mats, если они там случайно окажутся
    lingering_mats_filtered = [p for p in lingering_mats if '__cel_' not in p.name]
    if lingering_mats_filtered:
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В основной папке ({config.BASE_DIR.name}) обнаружены MAT файлы ({len(lingering_mats_filtered)}), которые могли остаться из-за ошибок перемещения:")
        print(f"  Примеры: {[f.name for f in lingering_mats_filtered[:5]]}")

def main():
    """Фаза запаковки CEL PNG в MAT"""
    print("\n--- Скрипт (Запаковка CEL MAT): Запаковка CEL файлов ---") # Условное название

    setup_directories_cel_pack()
    cel_groups = find_and_group_cel_pngs()
    if not cel_groups:
        print("\nРабота скрипта завершена, так как нет CEL PNG файлов для обработки.")
        return

    print("\n3. Начало запаковки групп...")
    status_counts = {}
    total_groups = len(cel_groups)
    sorted_group_items = sorted(cel_groups.items())

    for i, (base_name, png_group) in enumerate(sorted_group_items):
        status = process_cel_group(base_name, png_group)
        status_counts[status] = status_counts.get(status, 0) + 1

    print_summary_report_cel_pack(total_groups, status_counts)

if __name__ == "__main__":
     main()