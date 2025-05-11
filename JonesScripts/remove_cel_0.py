import os
import sys
from conf import Config

config = Config()

directory_path = config.RENAME_TARGET_DIR
substring_to_remove = config.RENAME_SUBSTRING_TO_REMOVE

# Проверка, существует ли папка (directory_path теперь объект Path)
if not directory_path.is_dir():
    print(f"Ошибка: Папка '{directory_path}' не найдена. Проверь правильность пути в conf.py (RENAME_TARGET_DIR).")
    sys.exit(1)

print(f"Сканирую папку: {directory_path}")
print(f"Ищу файлы с '{substring_to_remove}' в имени...")

count_renamed = 0
count_skipped = 0

# Проходим по всем файлам и папкам в указанной директории
for filename_str in os.listdir(str(directory_path)): # os.listdir ожидает строку
    old_filepath = directory_path / filename_str

    if old_filepath.is_file() and substring_to_remove in filename_str:

        new_filename_str = filename_str.replace(substring_to_remove, '')
        new_filepath = directory_path / new_filename_str

        if filename_str == new_filename_str:
            print(f"Пропускаю '{filename_str}': Новое имя совпадает со старым.")
            count_skipped += 1
        elif new_filepath.exists():
            print(f"Пропускаю '{filename_str}': Файл с именем '{new_filename_str}' уже существует.")
            count_skipped += 1
        else:
            try:
                os.rename(str(old_filepath), str(new_filepath))
                print(f"Переименовано: '{filename_str}' -> '{new_filename_str}'")
                count_renamed += 1
            except OSError as e:
                print(f"Ошибка при переименовании '{filename_str}': {e}")
                count_skipped += 1

print("\n--- Готово! ---")
print(f"Переименовано файлов: {count_renamed}")
print(f"Пропущено файлов (уже существуют или ошибки): {count_skipped}")

if __name__ == "__main__":
    pass