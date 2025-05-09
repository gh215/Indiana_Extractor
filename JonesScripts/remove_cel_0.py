import sys
from pathlib import Path
from conf import Config

directory_to_scan = Config.BASE_DIR

substring_to_remove = '__cel_0'

def main_rename(directory_path_obj: Path):
    """Переименовывает файлы в указанной папке."""
    print(f"Сканирую папку: {directory_path_obj}")
    print(f"Ищу файлы с '{substring_to_remove}' в имени...")

    count_renamed = 0
    count_skipped_exists = 0
    count_skipped_nochange = 0
    count_errors = 0
    processed_files = 0

    for item_path in directory_path_obj.iterdir():
        # Работаем только с файлами
        if item_path.is_file():
            processed_files += 1
            filename = item_path.name

            # Проверяем, содержит ли имя нужную часть
            if substring_to_remove in filename:
                # Создаем новое имя
                new_filename = filename.replace(substring_to_remove, '')
                new_filepath = directory_path_obj / new_filename

                # Проверка 1: Изменилось ли имя?
                if filename == new_filename:
                    print(f"Пропускаю '{filename}': Замена '{substring_to_remove}' не изменила имя.")
                    count_skipped_nochange += 1
                    continue

                # Проверка 2: Существует ли файл с новым именем?
                if new_filepath.exists():
                    print(f"Пропускаю '{filename}': Файл с новым именем '{new_filename}' уже существует.")
                    count_skipped_exists += 1
                    continue

                # Переименовываем
                try:
                    item_path.rename(new_filepath)
                    print(f"Переименовано: '{filename}' -> '{new_filename}'")
                    count_renamed += 1
                except OSError as e:
                    print(f"Ошибка при переименовании '{filename}' -> '{new_filename}': {e}")
                    count_errors += 1
            # else: # Файл не содержит подстроку - пропускаем молча

    print("\n--- Готово! ---")
    print(f"Всего проверено файлов: {processed_files}")
    print(f"Переименовано файлов: {count_renamed}")
    print(f"Пропущено (новое имя совпало со старым): {count_skipped_nochange}")
    print(f"Пропущено (файл с новым именем уже существует): {count_skipped_exists}")
    print(f"Ошибок при переименовании: {count_errors}")

if __name__ == "__main__":
    print("--- Скрипт 6: Переименование файлов с __cel_0 ---")

    if not directory_to_scan.is_dir():
        print(f"ОШИБКА: Папка '{directory_to_scan}' не найдена. Проверь путь в 'directory_to_scan' внутри скрипта.")
        sys.exit(1)

    main_rename(directory_to_scan)