import os
import sys

# --- НАСТРОЙКА ---
# Укажи путь к папке, где лежат твои файлы.
# ВАЖНО: Используй двойные обратные слеши (\\) для Windows или одинарные прямые (/) для Linux/macOS.
# Пример для Windows: 'C:\\Users\\ТвоеИмя\\Documents\\МоиФайлы'
# Пример для Linux/macOS: '/home/ТвоеИмя/Документы/МоиФайлы'
directory_path = r'C:\Users\yaros\Desktop\Ready Scripts\cel_ready_scripts'  # <<<=== ИЗМЕНИ ЭТОТ ПУТЬ!

# Часть имени файла, которую нужно удалить
substring_to_remove = '__cel_0'
# --- КОНЕЦ НАСТРОЙКИ ---

# Проверка, указан ли путь
if directory_path == 'ПУТЬ_К_ТВОЕЙ_ПАПКЕ':
    print("Ошибка: Пожалуйста, укажи правильный путь к папке в переменной 'directory_path' внутри скрипта.")
    sys.exit(1)  # Выход из скрипта с кодом ошибки

# Проверка, существует ли папка
if not os.path.isdir(directory_path):
    print(f"Ошибка: Папка '{directory_path}' не найдена. Проверь правильность пути.")
    sys.exit(1)  # Выход из скрипта с кодом ошибки

print(f"Сканирую папку: {directory_path}")
print(f"Ищу файлы с '{substring_to_remove}' в имени...")

count_renamed = 0
count_skipped = 0

# Проходим по всем файлам и папкам в указанной директории
for filename in os.listdir(directory_path):
    # Полный путь к текущему файлу
    old_filepath = os.path.join(directory_path, filename)

    # Проверяем, является ли это файлом (а не папкой) и содержит ли имя нужную часть
    if os.path.isfile(old_filepath) and substring_to_remove in filename:

        # Создаем новое имя, заменяя (удаляя) указанную часть
        new_filename = filename.replace(substring_to_remove, '')
        new_filepath = os.path.join(directory_path, new_filename)

        # Проверяем, не существует ли уже файл с таким новым именем
        if filename == new_filename:
            # Это может случиться, если replace ничего не заменил (маловероятно с 'in', но на всякий случай)
            print(f"Пропускаю '{filename}': Новое имя совпадает со старым.")
            count_skipped += 1
        elif os.path.exists(new_filepath):
            print(f"Пропускаю '{filename}': Файл с именем '{new_filename}' уже существует.")
            count_skipped += 1
        else:
            # Переименовываем файл
            try:
                os.rename(old_filepath, new_filepath)
                print(f"Переименовано: '{filename}' -> '{new_filename}'")
                count_renamed += 1
            except OSError as e:
                print(f"Ошибка при переименовании '{filename}': {e}")
                count_skipped += 1
    # else:
    # Можно добавить вывод для файлов, которые не были обработаны, если нужно
    # print(f"Пропускаю '{filename}': Не содержит '{substring_to_remove}' или это папка.")

print("\n--- Готово! ---")
print(f"Переименовано файлов: {count_renamed}")
print(f"Пропущено файлов (уже существуют или ошибки): {count_skipped}")