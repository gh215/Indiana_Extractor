import shutil
from pathlib import Path
import time
import sys
from conf import Config
from matool import Tool

def setup_directories_phase3():
    print("\n1. Проверка/создание необходимых папок...")
    Config.FINAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    Config.USED_MAT_DIR.mkdir(parents=True, exist_ok=True)
    Config.USED_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для финальных MAT: {Config.FINAL_MAT_DIR.relative_to(Config.BASE_DIR)}")
    print(f"   Папка с исходными MAT для инфо: {Config.USED_MAT_DIR.relative_to(Config.BASE_DIR)}")
    print(f"   Папка для использованных PNG: {Config.USED_DIR.relative_to(Config.BASE_DIR)}")
    if not Config.PROCESSED_PNG_DIR.exists() or not Config.PROCESSED_PNG_DIR.is_dir():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с обработанными PNG ({Config.PROCESSED_PNG_DIR}) не найдена!")
        sys.exit(1)
    if not Config.USED_MAT_DIR.exists() or not Config.USED_MAT_DIR.is_dir():
         print(f"КРИТИЧЕСКАЯ ОШИБКА: Не найдена папка с исходными MAT ({Config.USED_MAT_DIR}), необходимая для получения формата!")
         sys.exit(1)
    print("   Папки проверены/созданы.")

def find_processed_pngs():
    """Находит PNG файлы в папке PROCESSED_PNG_DIR."""
    print(f"\n2. Поиск обработанных PNG файлов в {Config.PROCESSED_PNG_DIR.name}...")
    # Исключаем файлы __cel_ из этого скрипта
    processed_png_files = sorted([
        p for p in Config.PROCESSED_PNG_DIR.glob('*.png')
        if '__cel_' not in p.name
    ])
    if not processed_png_files:
        print(f"   Папка {Config.PROCESSED_PNG_DIR.name} пуста или содержит только __cel_ файлы. Нет PNG для запаковки этим скриптом.")
        return []
    print(f"   Найдено {len(processed_png_files)} .png файлов (без __cel_) для запаковки.")
    return processed_png_files

def check_if_already_packed(final_mat_path: Path, processed_png_path: Path, used_png_target_path: Path):
    """Проверяет, существует ли финальный MAT, и перемещает PNG, если да."""
    if final_mat_path.exists():
        print(f"  Пропуск: Финальный файл {final_mat_path.name} уже существует в {Config.FINAL_MAT_DIR.name}.")
        # Перемещаем PNG в used, т.к. работа для него завершена
        if processed_png_path.exists():
            try:
                print(f"    Перемещение существующего PNG {processed_png_path.name} -> {used_png_target_path.relative_to(Config.BASE_DIR)}...")
                Config.USED_DIR.mkdir(parents=True, exist_ok=True)
                shutil.move(str(processed_png_path), str(used_png_target_path))
            except OSError as e:
                print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось переместить PNG {processed_png_path.name}: {e}")
        else:
             print(f"    Информация: PNG {processed_png_path.name} не найден для перемещения (возможно, уже перемещен).")
        return True # Да, пропущено
    return False # Нет, не пропущено

# Используем экземпляр matool.Tool
def get_packing_format_from_original(mt: Tool, original_mat_path: Path):
    """Проверяет наличие исходного MAT и возвращает формат для запаковки."""
    if not original_mat_path.exists():
        print(f"  ОШИБКА: Исходный MAT файл ({original_mat_path.name}) не найден в {Config.USED_MAT_DIR.name}.")
        print(f"           Невозможно получить формат для запаковки. Пропускаем.")
        return None # Ошибка: MAT не найден

    print(f"  Получение формата из {original_mat_path.name}...")
    info_dict = mt.info(original_mat_path)

    if info_dict.get('error'):
        print(f"  ОШИБКА: Не удалось получить информацию из {original_mat_path.name}: {info_dict['error']}")
        return None

    std_format = info_dict.get('format_standardized')
    format_raw = info_dict.get('format_raw')
    packing_format = None

    if format_raw and format_raw.replace('-', '') in ["rgb565", "rgba4444", "rgba5551"]:
         packing_format = format_raw
    elif std_format and std_format in ["rgb565", "rgba4444", "rgba5551"]:
         packing_format = std_format
    else:
        print(f"  ОШИБКА: Не удалось определить корректный формат для 'create' ({std_format=}, {format_raw=}) из {original_mat_path.name}.")
        print(f"           Формат должен быть одним из: rgb565, rgba4444, rgba5551 (или с дефисами).")
        print(f"           Невозможно выполнить 'matool create'. Пропускаем.")
        return None

    print(f"    Определен формат для запаковки: {packing_format}")
    return packing_format

def pack_png_to_mat(mt: Tool, packing_format: str, final_mat_path: Path, processed_png_path: Path):
    """Выполняет matool create, проверяет результат."""
    pack_successful = False
    try:
        print(f"  Запаковка {processed_png_path.name} в {final_mat_path.name} (формат: {packing_format})...")
        create_ok = mt.create(packing_format, final_mat_path, processed_png_path)

        if not create_ok:
            print(f"  ОШИБКА: matool create завершился с ошибкой.")
            return False

        time.sleep(0.2)

        if final_mat_path.exists():
            print(f"  Успех: matool создал файл {final_mat_path.name} в {Config.FINAL_MAT_DIR.name}.")
            pack_successful = True
        else:
            # Дополнительно проверим в CWD (Config.BASE_DIR), на всякий случай, если matool сработал по-старому
            fallback_path = Config.BASE_DIR / final_mat_path.name
            if fallback_path.exists():
                print(f"  ПРЕДУПРЕЖДЕНИЕ: matool создал файл в {Config.BASE_DIR.name}, а не в {Config.FINAL_MAT_DIR.name}!")
                print(f"    Перемещение {fallback_path.name} -> {final_mat_path.relative_to(Config.BASE_DIR)}...")
                try:
                    Config.FINAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(fallback_path), str(final_mat_path))
                    print("      Перемещение успешно.")
                    pack_successful = True
                except Exception as move_error:
                    print(f"    ОШИБКА при перемещении файла из {Config.BASE_DIR.name}: {move_error}")
                    # Файл остался в BASE_DIR, считаем неудачей
                    pack_successful = False
            else:
                print(f"  ОШИБКА: matool сообщил об успехе (код 0), но финальный файл {final_mat_path.name} не найден!")
                pack_successful = False

    except Exception as e:
        print(f"  КРИТИЧЕСКАЯ ОШИБКА во время вызова matool create для {processed_png_path.name}: {e}")
        pack_successful = False

    return pack_successful


def cleanup_after_packing(processed_png_path: Path, used_png_target_path: Path, std_format: str | None, base_name: str):
    """Перемещает использованный PNG и удаляет оригинальный извлеченный PNG."""
    if not processed_png_path.exists() and not used_png_target_path.exists():
         print(f"  Информация: Обработанный PNG {processed_png_path.name} не найден ни в {Config.PROCESSED_PNG_DIR.name}, ни в {Config.USED_DIR.name}. Очистка PNG не требуется.")
         return True #

    print("  Запаковка прошла успешно. Начинаем очистку PNG...")
    cleanup_error = False
    try:
        # 1. Перемещаем использованный PNG в USED_DIR (если он еще не там)
        if processed_png_path.exists():
            print(f"    Перемещение обработанного PNG: {processed_png_path.name} -> {used_png_target_path.relative_to(Config.BASE_DIR)}...")
            Config.USED_DIR.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(processed_png_path), str(used_png_target_path))
            except OSError as e:
                print(f"      ОШИБКА при перемещении PNG: {e}")
                cleanup_error = True
        else:
             # Уже мог быть перемещен при проверке check_if_already_packed
             if used_png_target_path.exists():
                 print(f"    Информация: PNG {processed_png_path.name} уже находится в {Config.USED_DIR.name}.")
             else:
                 # Странная ситуация, но не критичная для основной цели
                 print(f"    ПРЕДУПРЕЖДЕНИЕ: Обработанный PNG {processed_png_path.name} не найден для перемещения.")

        # 2. Удаляем оригинальный извлеченный PNG из папки формата в EXTRACTED_DIR (если формат известен)
        #    ВАЖНО: Эта логика может быть не нужна, если скрипт 1 уже удаляет исходные MAT
        #    Оставляем пока для полноты, но можно закомментировать, если не требуется
        if std_format and std_format != "unknown" and std_format != "rgba":
            original_format_dir = Config.FORMAT_DIRS.get(std_format)
            if original_format_dir and original_format_dir.exists():
                original_extracted_png_path = original_format_dir / f"{base_name}.png"
                if original_extracted_png_path.exists():
                    print(f"    Удаление оригинального извлеченного PNG: {original_extracted_png_path.relative_to(Config.BASE_DIR)}...")
                    try:
                        original_extracted_png_path.unlink()
                    except OSError as e:
                        print(f"      ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить оригинальный PNG {original_extracted_png_path.name}: {e}")
                        # Не считаем это критической ошибкой очистки, т.к. основной PNG перемещен
                        # cleanup_error = True
                # else: # Опционально
                #    print(f"    Информация: Оригинальный PNG {original_extracted_png_path.name} не найден для удаления.")
            # else: # Опционально
            #    print(f"    Информация: Папка формата {std_format} не найдена, удаление оригинала пропущено.")
        elif std_format:
            print(f"    Информация: Формат оригинала '{std_format}', удаление из папки формата пропущено.")


    except Exception as e:
        print(f"  ОШИБКА при очистке файлов для {base_name}: {e}")
        cleanup_error = True

    if cleanup_error:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Запаковка {base_name} завершена, но возникли ошибки при очистке PNG.")
    else:
        print(f"  Очистка PNG для {base_name} завершена успешно.")

    return not cleanup_error # True если успешно, False если были ошибки

def process_single_png_for_packing(mt: Tool, processed_png_path: Path):
    """Полный цикл обработки одного PNG для запаковки."""
    base_name = processed_png_path.stem
    print(f"\nОбработка: {processed_png_path.name}")

    original_mat_path = Config.USED_MAT_DIR / f"{base_name}.mat"
    final_mat_path = Config.FINAL_MAT_DIR / f"{base_name}.mat"
    # Используем Config.USED_DIR вместо USED_PNG_DIR
    used_png_target_path = Config.USED_DIR / processed_png_path.name

    # 1. Проверить, не запакован ли уже
    if check_if_already_packed(final_mat_path, processed_png_path, used_png_target_path):
        return "skipped"

    # 2. Получить формат из исходного MAT (передаем mt)
    packing_format = get_packing_format_from_original(mt, original_mat_path)
    if packing_format is None:
        return "error_format" # Ошибка получения/валидации формата

    # 3. Запаковать PNG в MAT (передаем mt)
    pack_ok = pack_png_to_mat(mt, packing_format, final_mat_path, processed_png_path)

    if not pack_ok:
        return "error_packing" # Ошибка запаковки или перемещения нового MAT

    # 4. Очистить исходные файлы (PNG)
    # Передаем packing_format (который может быть std_format или format_raw)
    # для поиска оригинального PNG в папке extracted
    cleanup_ok = cleanup_after_packing(processed_png_path, used_png_target_path, packing_format.replace('-',''), base_name)
    if not cleanup_ok:
        return "success_with_cleanup_issue"

    return "success"

def print_summary_report_phase3(total_files, status_counts):
    print("\n--- Скрипт 3 Завершен ---")
    print(f"Всего найдено PNG (без __cel_) для обработки: {total_files}")

    success_count = status_counts.get('success', 0)
    success_cleanup_issue = status_counts.get('success_with_cleanup_issue', 0)
    skipped_count = status_counts.get('skipped', 0)
    error_format_count = status_counts.get('error_format', 0)
    error_packing_count = status_counts.get('error_packing', 0)
    total_errors = error_format_count + error_packing_count

    print(f"Успешно запаковано и очищено: {success_count}")
    if success_cleanup_issue > 0:
        print(f"Успешно запаковано, но с ошибками очистки PNG: {success_cleanup_issue}")
    print(f"Пропущено (уже существовали в {Config.FINAL_MAT_DIR.name}): {skipped_count}")
    print(f"Всего ошибок (не удалось получить формат / запаковать): {total_errors}")
    if total_errors > 0:
        print("  Детали ошибок:")
        if error_format_count > 0: print(f"    - Ошибка получения/валидации формата из MAT: {error_format_count}")
        if error_packing_count > 0: print(f"    - Ошибка запаковки MAT (matool create): {error_packing_count}")
        print("  Просмотрите лог выше для информации по конкретным файлам.")

    print(f"\nФинальные MAT файлы находятся в: {Config.FINAL_MAT_DIR.name}")
    print(f"Исходные MAT для информации остались в: {Config.USED_MAT_DIR.name}")
    print(f"Использованные PNG перемещены в: {Config.USED_DIR.name}")

    # Проверка остатков
    remaining_png_processed = sorted([ p for p in Config.PROCESSED_PNG_DIR.glob('*.png') if '__cel_' not in p.name])

    if remaining_png_processed:
        print(f"\nПРЕДУПРЕЖДЕНИЕ: В {Config.PROCESSED_PNG_DIR.name} остались PNG файлы ({len(remaining_png_processed)}), которые не были обработаны из-за ошибок:")
        print(f"  Примеры: {[f.name for f in remaining_png_processed[:5]]}")

    lingering_mats = [p for p in Config.BASE_DIR.glob(f'{Config.FINAL_MAT_DIR.name}/*.mat') if p.is_file()] # Проверяем в BASE_DIR/final_mat
    if lingering_mats:
       pass

    # Проверяем остатки в BASE_DIR, которые могли остаться из-за ошибок перемещения
    lingering_base_mats = [p for p in Config.BASE_DIR.glob('*.mat') if p.is_file() and p.name.lower() != Config.MATOOL_FILENAME.lower()]
    if lingering_base_mats:
         print(f"\nПРЕДУПРЕЖДЕНИЕ: В основной папке ({Config.BASE_DIR.name}) обнаружены MAT файлы ({len(lingering_base_mats)}), которые могли остаться из-за ошибок перемещения:")
         print(f"  Примеры: {[f.name for f in lingering_base_mats[:5]]}")

def main():
    """Фаза 3: Запаковка PNG в MAT (с использованием MAT из used_mat)"""
    print("\n--- Скрипт 3: Запаковка PNG в MAT (Одиночные текстуры) ---")

    setup_directories_phase3()

    try:
        mt = Tool(Config.MATOOL_EXE_PRIMARY, Config.BASE_DIR, Config.MATOOL_EXE_ALT)
    except FileNotFoundError as e:
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать matool: {e}")
        print("Работа скрипта прервана.")
        sys.exit(1)

    processed_png_files = find_processed_pngs()
    if not processed_png_files:
        print("\nРабота скрипта завершена, так как нет подходящих файлов для обработки.")
        return

    # 2. Основной цикл обработки
    print("\n3. Начало запаковки файлов...")
    status_counts = {}
    total_files_to_process = len(processed_png_files)

    for i, png_path in enumerate(processed_png_files):
        print(f"--- Файл {i + 1}/{total_files_to_process} ---")
        # Передаем экземпляр mt
        status = process_single_png_for_packing(mt, png_path)
        status_counts[status] = status_counts.get(status, 0) + 1

    # 3. Итоговый отчет
    print_summary_report_phase3(total_files_to_process, status_counts)

if __name__ == "__main__":
     # Проверка matool теперь внутри main при создании Tool
     main()