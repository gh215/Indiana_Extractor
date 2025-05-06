import re
import sys
from pathlib import Path
from conf import Config

def get_mat_bases(directory: Path) -> set | None:
    if not directory.is_dir():
        print(f"ОШИБКА: Директория с MAT файлами не найдена: {directory}")
        return None
    mat_bases = set()
    print(f"\nСканирование папки с MAT файлами: {directory}")
    count = 0
    skipped_matool = 0
    for item in directory.iterdir():
        if item.is_file() and item.suffix.lower() == ".mat":
            if item.name.lower() == Config.MATOOL_FILENAME.lower():
                skipped_matool += 1
                continue
            mat_bases.add(item.stem)
            count += 1
    print(f"Найдено {count} .mat файлов (базовых имен: {len(mat_bases)}).")
    if skipped_matool > 0:
        print(f"(Пропущено {skipped_matool} файлов с именем {Config.MATOOL_FILENAME})")
    return mat_bases

def get_accounted_bases(directory: Path) -> set | None:
    if not directory.is_dir():
        print(f"ОШИБКА: Директория с результатами ({directory.name}) не найдена: {directory}")
        return None

    accounted_bases = set()
    processed_cel_bases = set()

    print(f"\nСканирование папки с результатами: {directory}")
    all_files = list(directory.iterdir())
    files_to_check = [f for f in all_files if f.is_file() and f.suffix.lower() in Config.VALID_EXTENSIONS]
    print(f"Найдено {len(files_to_check)} файлов с расширениями ({', '.join(Config.VALID_EXTENSIONS)}) для проверки.")

    skipped_count = 0
    for file_path in files_to_check:
        filename_lower = file_path.name.lower()
        file_extension = file_path.suffix.lower()

        cel_match = re.match(r'(.+)__cel_0' + re.escape(file_extension) + r'$', filename_lower)

        if cel_match:
            base_name = cel_match.group(1)
            if base_name not in processed_cel_bases:
                accounted_bases.add(base_name)
                processed_cel_bases.add(base_name)
        elif '__cel_' in filename_lower:
             skipped_count += 1
        else:
            accounted_bases.add(file_path.stem)

    print(f"Найдено {len(accounted_bases)} 'учтенных' базовых имен в папке {directory.name}.")
    if skipped_count > 0:
        print(f"(Пропущено {skipped_count} файлов с __cel_X, где X != 0)")
    return accounted_bases

if __name__ == "__main__":
    print("--- Скрипт 4: Проверка отсутствующих MAT в папке used ---")

    mat_dir_to_check = Config.MAT_DIR
    used_dir_to_check = Config.USED_DIR

    mat_bases = get_mat_bases(mat_dir_to_check)
    if mat_bases is None:
        sys.exit(1)

    accounted_for_bases = get_accounted_bases(used_dir_to_check)
    if accounted_for_bases is None:
        sys.exit(1)

    missing_bases = mat_bases - accounted_for_bases

    print("\n--- Результаты Сравнения ---")
    print(f"Всего .mat файлов для проверки (в {mat_dir_to_check.name}): {len(mat_bases)}")
    print(f"Всего 'учтенных' записей в {used_dir_to_check.name} (по файлам без __cel_ или с __cel_0): {len(accounted_for_bases)}")

    if missing_bases:
        print(f"\nОбнаружено {len(missing_bases)} .mat файлов из '{mat_dir_to_check.name}', отсутствующих в папке '{used_dir_to_check.name}' (или не учтенных по правилам):")
        for base in sorted(list(missing_bases)):
            print(f"- {base}.mat")
    else:
        print(f"\nВсе .mat файлы из папки '{mat_dir_to_check.name}' имеют соответствующую запись в папке '{used_dir_to_check.name}' (согласно правилам подсчета).")