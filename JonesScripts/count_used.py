from pathlib import Path
import re
import sys # Добавили sys для выхода при ошибке

# --- НАСТРОЙКИ ---
# Папка с ИСХОДНЫМИ .mat файлами, которые должны были быть обработаны
MAT_DIR = Path(r"C:\Users\yaros\Desktop\in")
# Папка с РЕЗУЛЬТАТАМИ обработки (PNG/WEBP)
USED_DIR = Path(r"C:\Users\yaros\Desktop\in\used")

# Расширения файлов-результатов в папке USED_DIR
VALID_EXTENSIONS = {".png", ".webp"}

# Имя исполняемого файла matool, чтобы исключить его из списка .mat
MATOOL_FILENAME = "matool.exe"

# --- Логика ---

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
        # Считаем только .mat файлы, исключая matool.exe
        if item.is_file() and item.suffix.lower() == ".mat" and item.name.lower() != MATOOL_FILENAME.lower():
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
    processed_cel_bases = set() # Для уникального учета CEL баз

    print(f"\nСканирование папки с результатами: {directory}")
    all_files = list(directory.iterdir())
    files_to_check = [f for f in all_files if f.is_file()]
    print(f"Найдено {len(files_to_check)} файлов для проверки.")

    for file_path in files_to_check:
        filename_lower = file_path.name.lower()
        file_extension = file_path.suffix.lower()

        if file_extension not in valid_extensions:
            continue

        cel_match = re.match(r'(.+)__cel_(\d+)' + re.escape(file_extension) + r'$', filename_lower)

        if cel_match:
            # CEL файл
            base_name = cel_match.group(1)
            cel_index = int(cel_match.group(2))
            if cel_index == 0:
                # __cel_0 файл - учитываем базу один раз
                if base_name not in processed_cel_bases:
                    accounted_bases.add(base_name)
                    processed_cel_bases.add(base_name)
        else:
            # Обычный файл - учитываем stem
            accounted_bases.add(file_path.stem)

    print(f"Найдено {len(accounted_bases)} 'учтенных' базовых имен в папке {directory.name}.")
    return accounted_bases

# --- Запуск и сравнение ---
if __name__ == "__main__":
    # Получаем базовые имена из MAT_DIR
    mat_bases = get_mat_bases(MAT_DIR)
    if mat_bases is None:
        sys.exit(1) # Выход, если папка не найдена

    # Получаем учтенные базовые имена из USED_DIR
    accounted_for_bases = get_accounted_bases(USED_DIR, VALID_EXTENSIONS)
    if accounted_for_bases is None:
        sys.exit(1) # Выход, если папка не найдена

    # Находим разницу: какие MAT базы НЕ представлены в учтенных базах
    missing_bases = mat_bases - accounted_for_bases

    print("\n--- Результаты Сравнения ---")
    print(f"Всего .mat файлов для проверки (в {MAT_DIR.name}): {len(mat_bases)}")
    print(f"Всего 'учтенных' записей в {USED_DIR.name} (по правилам): {len(accounted_for_bases)}")

    if missing_bases:
        print(f"\nОбнаружено {len(missing_bases)} .mat файлов, отсутствующих в папке '{USED_DIR.name}' (или не учтенных по правилам):")
        # Сортируем для удобства чтения
        for base in sorted(list(missing_bases)):
            print(f"- {base}.mat")
    else:
        print("\nВсе .mat файлы из папки 'mat' имеют соответствующую запись в папке 'used' (согласно правилам подсчета).")