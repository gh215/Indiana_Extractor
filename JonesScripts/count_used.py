from pathlib import Path
import re
import sys
from conf import Config

config = Config()

def get_mat_bases(directory: Path) -> set | None:
    """
    Получает множество базовых имен (.stem) всех .mat файлов в директории,
    исключая matool.exe.
    """
    if not directory.is_dir():
        print(f"ОШИБКА: Директория с MAT файлами не найдена: {directory}")
        return None
    mat_bases = set()
    print(f"\nСканирование папки с MAT файлами: {directory}")
    count = 0
    for item in directory.iterdir():
        # Используем config.MATOOL_FILENAME
        if item.is_file() and item.suffix.lower() == ".mat" and item.name.lower() != config.MATOOL_FILENAME.lower():
            mat_bases.add(item.stem)
            count += 1
    print(f"Найдено {count} .mat файлов (базовых имен: {len(mat_bases)}).")
    return mat_bases

def get_accounted_bases(directory: Path, valid_extensions: set) -> set | None:
    """ Получает множество "учтенных" базовых имен из папки с результатами (used), применяя правила для __cel_ файлов. """
    if not directory.is_dir():
        print(f"ОШИБКА: Директория с результатами (used) не найдена: {directory}")
        return None

    accounted_bases = set()
    processed_cel_bases = set()

    print(f"\nСканирование папки с результатами: {directory}")
    all_files = list(directory.iterdir())
    files_to_check = [f for f in all_files if f.is_file()]
    print(f"Найдено {len(files_to_check)} файлов для проверки.")

    for file_path in files_to_check:
        filename_lower = file_path.name.lower()
        file_extension = file_path.suffix.lower()

        if file_extension not in valid_extensions: # valid_extensions будет из config
            continue

        cel_match = re.match(r'(.+)__cel_(\d+)' + re.escape(file_extension) + r'$', filename_lower)

        if cel_match:
            base_name = cel_match.group(1)
            cel_index = int(cel_match.group(2))
            if cel_index == 0:
                if base_name not in processed_cel_bases:
                    accounted_bases.add(base_name)
                    processed_cel_bases.add(base_name)
        else:
            accounted_bases.add(file_path.stem)

    print(f"Найдено {len(accounted_bases)} 'учтенных' базовых имен в папке {directory.name}.")
    return accounted_bases

# --- Запуск и сравнение ---
if __name__ == "__main__":
    # Используем пути и константы из config
    mat_bases = get_mat_bases(config.MAT_DIR) # MAT_DIR из config
    if mat_bases is None:
        sys.exit(1)

    accounted_for_bases = get_accounted_bases(config.USED_DIR, config.VALID_EXTENSIONS) # USED_DIR и VALID_EXTENSIONS из config
    if accounted_for_bases is None:
        sys.exit(1)

    missing_bases = mat_bases - accounted_for_bases

    print("\n--- Результаты Сравнения ---")
    print(f"Всего .mat файлов для проверки (в {config.MAT_DIR.name}): {len(mat_bases)}")
    print(f"Всего 'учтенных' записей в {config.USED_DIR.name} (по правилам): {len(accounted_for_bases)}")

    if missing_bases:
        print(f"\nОбнаружено {len(missing_bases)} .mat файлов, отсутствующих в папке '{config.USED_DIR.name}' (или не учтенных по правилам):")
        for base in sorted(list(missing_bases)):
            print(f"- {base}.mat")
    else:
        print(f"\nВсе .mat файлы из папки '{config.MAT_DIR.name}' имеют соответствующую запись в папке '{config.USED_DIR.name}' (согласно правилам подсчета).")