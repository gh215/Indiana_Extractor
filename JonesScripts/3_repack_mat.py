import sys
import shutil
import time
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

def setup_directories_phase3():
    """Проверяет и создает необходимые директории для фазы 3."""
    print("\n1. Проверка/создание необходимых папок...")
    config.FINAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    config.USED_MAT_DIR.mkdir(parents=True, exist_ok=True)
    config.USED_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для финальных MAT: {config.FINAL_MAT_DIR}")
    print(f"   Папка с исходными MAT для инфо: {config.USED_MAT_DIR}")
    print(f"   Папка для использованных PNG: {config.USED_DIR}")
    if not config.PROCESSED_PNG_DIR.exists() or not config.PROCESSED_PNG_DIR.is_dir():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с обработанными PNG ({config.PROCESSED_PNG_DIR}) не найдена или не является папкой!")
        sys.exit(1)
    if not config.USED_MAT_DIR.exists() or not config.USED_MAT_DIR.is_dir():
         print(f"КРИТИЧЕСКАЯ ОШИБКА: Не найдена папка с исходными MAT ({config.USED_MAT_DIR}), необходимая для получения формата!")
         sys.exit(1)
    print("   Папки проверены/созданы.")

def find_processed_pngs():
    """Находит PNG файлы в папке PROCESSED_PNG_DIR."""
    print(f"\n2. Поиск обработанных PNG файлов в {config.PROCESSED_PNG_DIR.name}...")
    # Ищем PNG, т.к. скрипт 2 сохраняет в PNG. config.VALID_EXTENSIONS может быть шире.
    processed_png_files = sorted(list(config.PROCESSED_PNG_DIR.glob('*.png')))
    if not processed_png_files:
        print(f"   Папка {config.PROCESSED_PNG_DIR.name} пуста. Нет PNG файлов для запаковки.")
        return []
    print(f"   Найдено {len(processed_png_files)} .png файлов для запаковки.")
    return processed_png_files

def check_if_already_packed(final_mat_path, processed_png_path, used_png_target_path):
    """Проверяет, существует ли финальный MAT, и перемещает PNG, если да."""
    if final_mat_path.exists():
        print(f"  Пропуск: Финальный файл {final_mat_path.name} уже существует в {config.FINAL_MAT_DIR.name}.")
        if processed_png_path.exists():
            try:
                print(f"    Перемещение существующего PNG {processed_png_path.name} -> {used_png_target_path.relative_to(config.BASE_DIR)}...")
                config.USED_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(processed_png_path), str(used_png_target_path))
            except OSError as e:
                print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось переместить PNG {processed_png_path.name}: {e}")
        return True
    return False

def get_packing_format_from_original(original_mat_path):
    """Проверяет наличие исходного MAT и возвращает формат для запаковки."""
    if not original_mat_path.exists():
        print(f"  ОШИБКА: Исходный MAT файл ({original_mat_path.name}) не найден в {config.USED_MAT_DIR.name}.")
        print(f"           Невозможно получить формат для запаковки. Пропускаем.")
        return None

    print(f"  Получение формата из {original_mat_path.name}...")
    info_result = matool.info(original_mat_path) # Используем matool.info

    if info_result['error']:
        print(f"  ОШИБКА: Не удалось получить информацию из {original_mat_path.name} для определения формата запаковки.")
        return None

    std_format = info_result['format_standardized']

    # Проверяем, удалось ли получить валидный формат для create
    # 'rgba' также не подходит для create, т.к. это общий идентификатор, а не конкретный формат кодирования
    if std_format is None or std_format == "unknown" or std_format == "rgba":
         print(f"  ОШИБКА: Не удалось определить корректный формат для запаковки ({std_format}) из {original_mat_path.name}.")
         print(f"           Невозможно выполнить 'matool create'. Пропускаем.")
         return None

    print(f"    Определен формат для запаковки: {std_format}")
    return std_format

def pack_png_to_mat(std_format, final_mat_path, processed_png_path):
    """Выполняет matool create, проверяет результат."""
    pack_successful = False

    # Используем matool.create
    # matool.create выводит информацию о запуске и stdout/stderr
    success_flag = matool.create(std_format, final_mat_path, processed_png_path)

    if not success_flag:
        return False

    time.sleep(0.2)

    # После успешного matool.create (возврат 0 от matool.exe), файл должен быть в final_mat_path
    if final_mat_path.exists():
        print(f"  Успех: matool создал {final_mat_path.name} в {final_mat_path.parent.name}.")
        pack_successful = True
    else:
        print(f"  ОШИБКА: matool create сообщил об успехе (код 0), но новый файл {final_mat_path.name} не найден в {final_mat_path.parent.name}!")
        pack_successful = False

    return pack_successful


def cleanup_after_packing(processed_png_path, used_png_target_path, std_format, base_name):
    """Перемещает использованный PNG и удаляет оригинальный извлеченный PNG."""
    print("  Запаковка и перемещение нового файла прошли успешно. Начинаем очистку...")
    cleanup_error = False
    try:
        if processed_png_path.exists():
            print(f"    Перемещение обработанного PNG: {processed_png_path.name} -> {used_png_target_path.relative_to(config.BASE_DIR)}...")
            config.USED_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(processed_png_path), str(used_png_target_path))
        else:
            print(f"    ПРЕДУПРЕЖДЕНИЕ: Обработанный PNG {processed_png_path.name} не найден для перемещения.")

        if std_format and std_format != "unknown" and std_format != "rgba":
            original_format_dir = config.FORMAT_DIRS.get(std_format)
            if original_format_dir and original_format_dir.exists():
                original_extracted_png_path = original_format_dir / f"{base_name}.png"
                if original_extracted_png_path.exists():
                    print(f"    Удаление оригинального извлеченного PNG: {original_extracted_png_path.relative_to(config.BASE_DIR)}...")
                    try:
                        original_extracted_png_path.unlink()
                    except OSError as e:
                        print(f"      ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить {original_extracted_png_path.name}: {e}")
                        cleanup_error = True
    except Exception as e:
        print(f"  ОШИБКА при очистке файлов для {base_name}: {e}")
        cleanup_error = True

    if cleanup_error:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Запаковка {base_name} завершена, но возникли ошибки при очистке.")
    else:
        print(f"  Очистка для {base_name} завершена успешно.")
    return not cleanup_error

def process_single_png_for_packing(processed_png_path):
    """Полный цикл обработки одного PNG для запаковки."""
    base_name = processed_png_path.stem
    print(f"\nОбработка: {processed_png_path.name}")

    original_mat_path = config.USED_MAT_DIR / f"{base_name}.mat"
    final_mat_path = config.FINAL_MAT_DIR / f"{base_name}.mat"
    used_png_target_path = config.USED_DIR / processed_png_path.name

    if check_if_already_packed(final_mat_path, processed_png_path, used_png_target_path):
        return "skipped"

    std_format = get_packing_format_from_original(original_mat_path)
    if std_format is None:
        return "error_format"

    pack_ok = pack_png_to_mat(std_format, final_mat_path, processed_png_path)

    if not pack_ok:
        # Проверяем, не остался ли .mat в config.BASE_DIR (маловероятно с прямым путем в matool.create)
        lingering_mat_in_base = config.BASE_DIR / f"{base_name}.mat"
        if lingering_mat_in_base.exists():
            print(f"  ПРЕДУПРЕЖДЕНИЕ: Обнаружен MAT файл ({lingering_mat_in_base.name}) в {config.BASE_DIR.name} после неудачной запаковки. Возможно, его стоит удалить или переместить вручную.")
        return "error_packing"

    cleanup_ok = cleanup_after_packing(processed_png_path, used_png_target_path, std_format, base_name)
    if not cleanup_ok:
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
    print(f"Пропущено (уже существовали в {config.FINAL_MAT_DIR.name}): {skipped_count}")
    print(f"Всего ошибок (не удалось получить формат / запаковать): {total_errors}")
    if total_errors > 0:
        print("  Детали ошибок:")
        if error_format_count > 0: print(f"    - Ошибка получения/валидации формата: {error_format_count}")
        if error_packing_count > 0: print(f"    - Ошибка запаковки/перемещения нового MAT: {error_packing_count}")
        print("  Просмотрите лог выше для информации по конкретным файлам.")

    print(f"\nФинальные MAT файлы находятся в: {config.FINAL_MAT_DIR.name}")
    print(f"Исходные MAT для информации остались в: {config.USED_MAT_DIR.name}")
    print(f"Использованные PNG перемещены в: {config.USED_DIR.name}")

    remaining_png_processed = list(config.PROCESSED_PNG_DIR.glob('*.png'))
    if remaining_png_processed:
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В {config.PROCESSED_PNG_DIR.name} остались PNG файлы ({len(remaining_png_processed)}), которые не были обработаны из-за ошибок:")
        print(f"  Примеры: {[f.name for f in remaining_png_processed[:5]]}")

    lingering_mats = [p for p in config.BASE_DIR.glob('*.mat') if p.is_file() and p.name != config.MATOOL_FILENAME]
    if lingering_mats:
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В основной папке ({config.BASE_DIR.name}) обнаружены MAT файлы ({len(lingering_mats)}), которые могли остаться из-за ошибок:")
        print(f"  Примеры: {[f.name for f in lingering_mats[:5]]}")


def main():
    print("\n--- Скрипт 3: Запаковка PNG в MAT ---")
    setup_directories_phase3()
    processed_png_files = find_processed_pngs()
    if not processed_png_files:
        print("\nРабота скрипта завершена, так как нет файлов для обработки.")
        return

    print("\n3. Начало запаковки файлов...")
    status_counts = {}

    for png_path in processed_png_files:
        status = process_single_png_for_packing(png_path)
        status_counts[status] = status_counts.get(status, 0) + 1

    print_summary_report_phase3(len(processed_png_files), status_counts)

if __name__ == "__main__":
    main()