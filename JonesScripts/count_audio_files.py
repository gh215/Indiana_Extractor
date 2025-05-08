import os
import sys
from pathlib import Path
from audio_conf import Config

SOURCE_DIR_TO_COMPARE = Config.S5_COMPARISON_SOURCE_DIR
TARGET_DIR_TO_COMPARE = Config.S5_COMPARISON_TARGET_DIR

def get_file_stems(directory: Path, description: str) -> set[str] | None:
    if not directory.is_dir():
        print(f"ОШИБКА: Директория '{description}' не найдена: {directory}")
        return None
    print(f"\nСканирование папки '{description}' и ее подпапок: {directory}")
    stems = set()
    file_count = 0
    for item in directory.rglob('*'): # rglob сканирует рекурсивно
        if item.is_file():
            stems.add(item.stem.lower()) # Сравниваем по базовому имени в нижнем регистре
            file_count += 1
    print(f"Найдено {file_count} файлов (включая подпапки), {len(stems)} уникальных базовых имен.")
    return stems

def find_missing_files(source_dir: Path, target_dir: Path):
    source_stems = get_file_stems(source_dir, f"Источник ({source_dir.name})")
    if source_stems is None:
        return None # Ошибка уже выведена

    target_stems = get_file_stems(target_dir, f"Готовая папка ({target_dir.name})")
    if target_stems is None:
         print(f"\nПредупреждение: Готовая папка '{target_dir.name}' не найдена или не удалось прочитать. Все файлы из источника будут считаться отсутствующими в целевой папке.")
         missing_stems = source_stems # Если целевой нет, все из источника "отсутствуют"
    else:
        missing_stems = source_stems - target_stems

    print(f"\nВычислено отсутствующих базовых имен (файлы из '{source_dir.name}', которых нет в '{target_dir.name}'): {len(missing_stems)}")

    if not missing_stems:
        return []

    print(f"\nПоиск конкретных файлов в '{source_dir.name}' с отсутствующими аналогами (по базовому имени) в '{target_dir.name}'...")
    missing_files_list = []
    for item in source_dir.rglob('*'):
        if item.is_file():
            if item.stem.lower() in missing_stems:
                try:
                    # Получаем путь относительно исходной директории для более понятного вывода
                    relative_path = str(item.relative_to(source_dir))
                    missing_files_list.append(relative_path)
                except ValueError: # На случай, если item не является потомком source_dir (маловероятно с rglob)
                     missing_files_list.append(str(item) + " (ошибка получения относительного пути)")

    print(f"Найдено {len(missing_files_list)} конкретных отсутствующих файлов для вывода списка.")
    return sorted(missing_files_list) # Сортируем для консистентного вывода

if __name__ == "__main__":
    print("--- Скрипт Сравнения Папок (Настройки из Config) ---")
    print(f"Папка-источник для сравнения: {SOURCE_DIR_TO_COMPARE}")
    print(f"Папка-цель для сравнения:     {TARGET_DIR_TO_COMPARE}")
    print("-" * 50)

    if not SOURCE_DIR_TO_COMPARE.is_dir(): # Проверяем только источник, find_missing_files обработает отсутствие цели
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: Папка-источник не найдена: {SOURCE_DIR_TO_COMPARE}")
        sys.exit(1)

    missing_files = find_missing_files(SOURCE_DIR_TO_COMPARE, TARGET_DIR_TO_COMPARE)

    print("\n--- Результаты Сравнения ---")

    if missing_files is None: # Это означает ошибку при чтении исходной директории
        print("Сравнение не удалось из-за ошибки чтения директории источника. Проверьте вывод выше.")
        sys.exit(1)

    count = len(missing_files)
    source_name = SOURCE_DIR_TO_COMPARE.name # Для вывода
    target_name = TARGET_DIR_TO_COMPARE.name # Для вывода

    if count > 0:
        print(f"Обнаружено {count} файлов из папки '{source_name}' (и ее подпапок), "
              f"базовые имена которых ОТСУТСТВУЮТ в папке '{target_name}' (и ее подпапках):")
        for rel_path in missing_files:
            print(f"  - {rel_path}") # Выводим относительный путь
    else:
        if TARGET_DIR_TO_COMPARE.exists() and TARGET_DIR_TO_COMPARE.is_dir():
             print(f"Все файлы из папки '{source_name}' (и ее подпапок) имеют соответствующий файл "
                   f"(с таким же базовым именем) в папке '{target_name}' (и ее подпапках).")
        else:
             print(f"Целевая папка '{target_name}' не найдена или не является директорией. Сравнение показало {count} отсутствующих файлов.")


    print("\n--- Сравнение завершено ---")