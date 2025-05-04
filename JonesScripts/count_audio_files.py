import sys
from pathlib import Path
import os

# Импортируем конфиг
from conf import Config

# --- НАСТРОЙКИ ---
SOURCE_DIR_TO_COMPARE = Config.AUDIO_INPUT_DIR
TARGET_DIR_TO_COMPARE = Config.AUDIO_OUTPUT_DIR
# --- КОНЕЦ НАСТРОЕК ---


def get_file_stems(directory: Path, description: str) -> set[str] | None:
    """Сканирует директорию рекурсивно (без изменений)."""
    if not directory.is_dir():
        print(f"ОШИБКА: Директория '{description}' не найдена: {directory}")
        return None
    print(f"\nСканирование папки '{description}' и ее подпапок: {directory}")
    stems = set()
    file_count = 0
    for item in directory.rglob('*'):
        if item.is_file():
            stems.add(item.stem.lower())
            file_count += 1
    print(f"Найдено {file_count} файлов (включая подпапки), {len(stems)} уникальных базовых имен.")
    return stems

def find_missing_files(source_dir: Path, target_dir: Path):
    """Находит отсутствующие файлы (без изменений в логике)."""
    source_stems = get_file_stems(source_dir, "Источник")
    if source_stems is None: return None

    target_stems = get_file_stems(target_dir, "Готовая папка")
    if target_stems is None:
         print(f"\nПредупреждение: Готовая папка '{target_dir.name}' не найдена или не удалось прочитать. Все файлы из источника считаются отсутствующими.")
         missing_stems = source_stems
    else:
        missing_stems = source_stems - target_stems

    print(f"\nВычислено отсутствующих базовых имен (source - target): {len(missing_stems)}")

    if not missing_stems: return []

    print(f"\nПоиск конкретных файлов в '{source_dir.name}' с отсутствующими аналогами в '{target_dir.name}'...")
    missing_files_list = []
    for item in source_dir.rglob('*'):
        if item.is_file():
            if item.stem.lower() in missing_stems:
                try:
                    relative_path = str(item.relative_to(source_dir))
                    missing_files_list.append(relative_path)
                except ValueError:
                     missing_files_list.append(item.name + " (ошибка получения относительного пути)")

    print(f"Найдено {len(missing_files_list)} отсутствующих файлов для вывода списка.")
    return sorted(missing_files_list)

# --- Основной блок ---
if __name__ == "__main__":
    print("--- Скрипт Сравнения Папок (из Config) ---")

    # Используем переменные с путями из настроек выше
    if not SOURCE_DIR_TO_COMPARE.is_dir():
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: Папка-источник не найдена: {SOURCE_DIR_TO_COMPARE}")
        sys.exit(1)

    missing_files = find_missing_files(SOURCE_DIR_TO_COMPARE, TARGET_DIR_TO_COMPARE)

    print("\n--- Результаты Сравнения ---")

    if missing_files is None:
        print("Сравнение не удалось из-за ошибки чтения директории источника.")
        sys.exit(1)

    count = len(missing_files)
    # Используем имена папок из переменных
    source_name = SOURCE_DIR_TO_COMPARE.name
    target_name = TARGET_DIR_TO_COMPARE.name

    if count > 0:
        print(f"Обнаружено {count} файлов из папки '{source_name}' (и подпапок), "
              f"базовые имена которых ОТСУТСТВУЮТ в папке '{target_name}' (и подпапках):")
        for rel_path in missing_files:
            print(f"- {rel_path}")
    else:
        print(f"Все файлы из папки '{source_name}' (и подпапок) имеют соответствующий файл "
              f"(с таким же базовым именем) в папке '{target_name}' (и подпапках).")

    print("\n--- Сравнение завершено ---")