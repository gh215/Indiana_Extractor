import sys
import subprocess
import re
import time
from pathlib import Path
from PIL import Image
from gradio_client import Client, handle_file

# --- НАСТРОЙКИ ---
BASE_DIR = Path(r"C:\Users\yaros\Desktop\in")
USED_MAT_DIR = BASE_DIR / "used_mat"
USED_MANUAL_MAT_DIR = BASE_DIR / "used_manual_mat"
EXTRACTED_DIR = BASE_DIR / "extracted"
PROCESSED_PNG_DIR = BASE_DIR / "processed_png"
MATOOL_EXE = BASE_DIR / "matool.exe"

# --- Папки форматов внутри EXTRACTED_DIR ---
FORMAT_DIRS = {
    "rgb565": EXTRACTED_DIR / "rgb565",
    "rgba4444": EXTRACTED_DIR / "rgba4444",
    "rgba5551": EXTRACTED_DIR / "rgba5551",
    "unknown": EXTRACTED_DIR / "unknown_format",
    "rgba": EXTRACTED_DIR / "rgba_unknown"
}

# --- Настройки Gradio ---
HF_SPACE_URL = "Phips/Upscaler"
TARGET_MODEL_NAME = "4xNomosWebPhoto_RealPLKSR"
API_NAME = "/upscale_image"
# --- Фраза для определения ошибки квоты ---
QUOTA_ERROR_PHRASE = "exceeded your gpu quota"
# --- Пауза между запросами к API ---
API_PAUSE_DURATION = 1 # секунды


def run_matool(command, *args, cwd=BASE_DIR):
    """Запускает matool.exe с заданной командой и аргументами."""
    matool_executable = MATOOL_EXE
    if not MATOOL_EXE.exists():
        alt_matool_path = BASE_DIR / "extracted" / "matool.exe"
        if alt_matool_path.exists():
            matool_executable = alt_matool_path
        else:
            print(f"ОШИБКА: matool.exe не найден ни в {MATOOL_EXE}, ни в {alt_matool_path}")
            return None, f"matool.exe не найден"
    cmd = [str(matool_executable), command] + [str(arg) for arg in args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore', cwd=cwd)
        if result.returncode != 0:
            error_msg = f"ОШИБКА: Команда matool {command} завершилась с кодом {result.returncode}."
            print(error_msg)
            if result.stderr:
                 stderr_lines = result.stderr.strip().splitlines()
                 if stderr_lines and any(line.strip() for line in stderr_lines):
                     print("    Stderr:")
                     print('\n'.join(f"      {line}" for line in stderr_lines if line.strip()))
            return (result.stdout, result.stderr), error_msg
        return (result.stdout, result.stderr), None
    except FileNotFoundError:
        error_msg = f"ОШИБКА: Не удалось запустить matool {command}. Убедитесь, что {matool_executable} доступен."
        print(error_msg); return None, error_msg
    except Exception as e:
        error_msg = f"ОШИБКА: Непредвиденная ошибка при запуске matool {command}: {e}"
        print(error_msg); return None, error_msg

def get_mat_info(mat_path):
    """Получает информацию из matool info и парсит формат, наличие альфы и кол-во текстур."""
    (stdout, stderr), error = run_matool("info", mat_path)
    if error: return None, False, None
    if not stdout:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Получен пустой stdout от matool info для {mat_path.name}."); return None, False, None
    color_format_raw = None; color_format_standardized = None; has_alpha = False; texture_count = None
    format_match = re.search(r"Encoding:\.*?\s*([A-Za-z0-9\-]+)", stdout, re.IGNORECASE)
    if format_match:
        color_format_raw = format_match.group(1).lower()
        color_format_standardized = color_format_raw.replace('-', '')
        if color_format_standardized in ["rgba4444", "rgba5551", "rgba"]: has_alpha = True
    else:
        mode_match = re.search(r"Color mode:\.*?\s*(RGBA)", stdout, re.IGNORECASE)
        if mode_match: has_alpha = True; color_format_standardized = "rgba"
    if color_format_standardized is None: color_format_standardized = "unknown"
    texture_count_match = re.search(r"Total textures:\.*?\s*(\d+)", stdout)
    if texture_count_match: texture_count = int(texture_count_match.group(1))
    else: print(f"    ПРЕДУПРЕЖДЕНИЕ ({mat_path.name}): Не удалось определить количество текстур.")
    return color_format_standardized, has_alpha, texture_count

def restore_alpha(original_png_path, upscaled_png_path):
    """Восстанавливает альфа-канал из оригинала в апскейленный PNG."""
    try:
        if not original_png_path.exists():
             print(f"    ОШИБКА: Оригинальный PNG {original_png_path.name} не найден в {original_png_path.parent}. Невозможно восстановить альфу.")
             return False
        with Image.open(original_png_path) as img_orig, Image.open(upscaled_png_path) as img_upscaled:
            if 'A' not in img_orig.getbands():
                if 'A' in img_upscaled.getbands():
                     print("    В апскейле обнаружен альфа-канал, хотя в оригинале его не было. Конвертируем в RGB.")
                     rgb_img = img_upscaled.convert('RGB'); rgb_img.save(upscaled_png_path, "PNG"); rgb_img.close()
                return True # Успех, ничего делать не надо или конвертировали
            # Альфа в оригинале есть
            if 'A' not in img_upscaled.getbands():
                 print("    Апскейл не содержит альфа-канал, конвертируем в RGBA.")
                 img_upscaled = img_upscaled.convert("RGBA")
            elif img_upscaled.mode != 'RGBA':
                 print(f"    Апскейл имеет режим {img_upscaled.mode}, но не RGBA. Конвертируем в RGBA.")
                 img_upscaled = img_upscaled.convert("RGBA")
            # Теперь img_upscaled точно RGBA
            alpha_orig = img_orig.getchannel('A')
            alpha_resized = alpha_orig.resize(img_upscaled.size, Image.Resampling.NEAREST)
            img_upscaled.putalpha(alpha_resized); img_upscaled.save(upscaled_png_path, "PNG")
            print("    Альфа-канал успешно восстановлен и сохранен.")
            return True
    except FileNotFoundError: print(f"    ОШИБКА: Файл не найден при попытке восстановления альфы ({original_png_path} или {upscaled_png_path})."); return False
    except Exception as e: print(f"    ОШИБКА: Не удалось восстановить альфа-канал для {upscaled_png_path.name}: {e}"); return False


def setup_directories_phase2():
    """Проверяет и создает необходимые директории для фазы 2."""
    print("\n1. Проверка/создание необходимых папок...")
    PROCESSED_PNG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для обработанных PNG: {PROCESSED_PNG_DIR}")
    if not USED_MAT_DIR.exists(): print(f"   ПРЕДУПРЕЖДЕНИЕ: Папка ({USED_MAT_DIR}) не найдена! Создаем."); USED_MAT_DIR.mkdir(parents=True, exist_ok=True)
    if not USED_MANUAL_MAT_DIR.exists(): print(f"   ПРЕДУПРЕЖДЕНИЕ: Папка ({USED_MANUAL_MAT_DIR}) не найдена! Создаем."); USED_MANUAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    if not EXTRACTED_DIR.exists():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с извлеченными PNG ({EXTRACTED_DIR}) не найдена!"); sys.exit(1)
    print("   Папки проверены/созданы.")

def find_original_pngs():
    """Находит все извлеченные PNG файлы в папках форматов."""
    print("\n2. Поиск извлеченных PNG файлов...")
    original_png_files = []
    for fmt_dir in FORMAT_DIRS.values():
        if fmt_dir.exists():
            original_png_files.extend(list(fmt_dir.glob('*.png')))
    if not original_png_files:
        print(f"   Не найдено извлеченных PNG файлов в подпапках {EXTRACTED_DIR}. Нечего обрабатывать.")
        return []
    print(f"   Найдено {len(original_png_files)} извлеченных PNG файлов для обработки.")
    return sorted(original_png_files) # Сортируем для предсказуемости

def initialize_gradio_client(url):
    """Инициализирует и возвращает клиент Gradio."""
    print(f"\n3. Подключение к Hugging Face Space: {url}...")
    try:
        client = Client(url, verbose=False)
        print("   Подключение успешно.")
        return client
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к {url}. Ошибка: {e}")
        sys.exit(1)

def get_original_mat_path(png_stem):
    """Определяет путь к соответствующему исходному MAT файлу."""
    if "__cel_" in png_stem:
        base_name_only = png_stem.split('__cel_')[0]
        mat_file_name_to_find = f"{base_name_only}.mat"
        original_mat_path = USED_MANUAL_MAT_DIR / mat_file_name_to_find
    else:
        base_name_only = png_stem
        mat_file_name_to_find = f"{base_name_only}.mat"
        original_mat_path = USED_MAT_DIR / mat_file_name_to_find
    return original_mat_path, mat_file_name_to_find

def upscale_image_via_api(client, png_path_to_upscale, target_png_path):
    """Отправляет изображение на апскейл через API, обрабатывает результат."""
    temp_result_path_str = None
    try:
        print(f"  Отправка {png_path_to_upscale.name} на апскейл...")
        start_time = time.time()
        # --- Важно: передаем путь как строку ---
        api_result = client.predict(handle_file(str(png_path_to_upscale)), TARGET_MODEL_NAME, api_name=API_NAME)
        end_time = time.time()
        print(f"  Апскейл завершен за {end_time - start_time:.2f} сек.")

        # Обработка результата (может быть строка или список)
        if isinstance(api_result, list) and len(api_result) >= 2 and isinstance(api_result[1], str):
            temp_result_path_str = api_result[1]
        elif isinstance(api_result, str):
            temp_result_path_str = api_result
        else:
            print(f"  ОШИБКА: API вернул неожиданный результат: {type(api_result)} {api_result}")
            return None, "api_unexpected_result" # Возвращаем None и код ошибки

        if not temp_result_path_str:
            print(f"  ОШИБКА: Путь к результату от API пуст.")
            return None, "api_empty_path"

        temp_result_path = Path(temp_result_path_str)
        if not temp_result_path.exists():
            print(f"  ОШИБКА: API вернул путь ({temp_result_path_str}), но файл не найден.")
            return None, "api_file_not_found"

        # Конвертация в PNG и сохранение в целевую папку
        print(f"  Конвертация результата в PNG: {target_png_path.name}")
        with Image.open(temp_result_path) as img:
            img.save(target_png_path, "PNG")
        print(f"  Успешно сохранено в {target_png_path.parent.name}")

        # Удаление временного файла
        try:
            temp_result_path.unlink()
            # print(f"  Временный файл {temp_result_path.name} удален.") # Опционально
        except OSError as e:
            print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить временный файл {temp_result_path.name}: {e}")

        return target_png_path, None # Возвращаем путь и отсутствие ошибки

    except Exception as e:
        error_message_lower = str(e).lower()
        if QUOTA_ERROR_PHRASE in error_message_lower:
            print(f"\nОШИБКА: Обнаружена проблема с квотой GPU на Hugging Face Space!")
            print(f"  Сообщение API: {e}")
            return None, "quota_exceeded" # Возвращаем None и код ошибки квоты
        else:
            print(f"  ОШИБКА при взаимодействии с API {HF_SPACE_URL} или конвертации:")
            print(f"    {e}")
            # Удаляем частично созданный файл, если он есть
            if target_png_path.exists():
                try: target_png_path.unlink()
                except OSError: pass
            return None, "api_other_error" # Возвращаем None и другой код ошибки

def process_single_png(original_extracted_png_path, client):
    """Полный цикл обработки одного PNG: апскейл, восстановление альфы."""
    png_stem = original_extracted_png_path.stem
    processed_png_path = PROCESSED_PNG_DIR / f"{png_stem}.png"
    print(f"\nОбработка: {original_extracted_png_path.relative_to(EXTRACTED_DIR)}")

    # Пропуск, если уже обработан
    if processed_png_path.exists():
        print(f"  Пропуск: Файл {processed_png_path.name} уже существует в {PROCESSED_PNG_DIR.name}.")
        return "skipped" # Статус: пропущено

    # Найти исходный MAT
    original_mat_path, mat_file_name_to_find = get_original_mat_path(png_stem)
    if not original_mat_path.exists():
        print(f"  ОШИБКА: Исходный файл {mat_file_name_to_find} не найден в {original_mat_path.parent.name}.")
        return "error_mat_not_found" # Статус: ошибка

    # Апскейл через API
    upscaled_path, api_error_code = upscale_image_via_api(client, original_extracted_png_path, processed_png_path)

    if api_error_code == "quota_exceeded":
        return "quota_exceeded" # Передаем статус дальше
    if api_error_code:
        return "error_api" # Общий статус ошибки API/конвертации

    if not upscaled_path: # Дополнительная проверка на всякий случай
        print("  Критическая ошибка: upscale_image_via_api не вернула путь, но и не код ошибки.")
        return "error_internal"

    # Получение информации из MAT для альфы
    std_format, has_alpha, _ = get_mat_info(original_mat_path)
    if std_format is None:
        print(f"  ОШИБКА: Не удалось получить формат из {original_mat_path.name} после апскейла.")
        # Возможно, стоит удалить upscaled_path здесь? Решаем не удалять, т.к. апскейл прошел.
        return "error_mat_info_failed"

    # Восстановление альфы, если нужно
    if has_alpha:
        print("  Требуется восстановление альфа-канала...")
        alpha_restored_ok = restore_alpha(original_extracted_png_path, upscaled_path)
        if not alpha_restored_ok:
            print(f"  ОШИБКА: Не удалось восстановить альфа-канал для {upscaled_path.name}.")
            # Оставляем файл без альфы или с некорректной, но считаем ошибкой
            return "error_alpha_restore"
    # else:
        # print("  Альфа-канал не требуется.") # Опционально

    # Пауза перед следующим файлом
    if API_PAUSE_DURATION > 0:
        print(f"  Пауза {API_PAUSE_DURATION} сек...")
        time.sleep(API_PAUSE_DURATION)

    return "success" # Статус: успех

def print_summary_report_phase2(total_files, status_counts):
    """Печатает итоговый отчет для фазы 2."""
    print("\n--- Скрипт 2 Завершен ---")
    print(f"Всего найдено извлеченных PNG для обработки: {total_files}")
    print(f"Успешно обработано (апскейл+конвертация+альфа): {status_counts.get('success', 0)}")
    print(f"Пропущено (уже существовали в {PROCESSED_PNG_DIR.name}): {status_counts.get('skipped', 0)}")

    errors_total = sum(v for k, v in status_counts.items() if k.startswith("error_"))
    print(f"Возникло ошибок при обработке: {errors_total}")
    if errors_total > 0:
        print("  Детали ошибок:")
        for status, count in status_counts.items():
            if status.startswith("error_") and count > 0:
                 error_desc = {
                     "error_mat_not_found": "Не найден исходный MAT",
                     "error_api": "Ошибка API Hugging Face / Конвертации",
                     "error_mat_info_failed": "Не удалось получить инфо из MAT после апскейла",
                     "error_alpha_restore": "Ошибка восстановления альфа-канала",
                     "error_internal": "Внутренняя ошибка логики"
                 }.get(status, status) # Используем статус как ключ, если нет описания
                 print(f"    - {error_desc}: {count} раз")
        print("  Просмотрите лог выше для более подробной информации по каждому файлу.")

    print(f"\nТеперь можно запустить Скрипт 3 (pack_mats.py) или 4 (pack_cel_mats.py) для запаковки обработанных PNG из папки {PROCESSED_PNG_DIR.name}.")

def main():
    """Фаза 2: Автоматический апскейл через HF Space, конвертация и восстановление альфы."""
    print("\n--- Скрипт 2: Апскейл (Hugging Face API), Конвертация, Альфа ---")

    # 1. Подготовка
    setup_directories_phase2()
    original_png_files = find_original_pngs()
    if not original_png_files:
        print("\nРабота скрипта завершена, так как нет файлов для обработки.")
        return # Выходим, если нечего обрабатывать

    client = initialize_gradio_client(HF_SPACE_URL)
    if not client: # На случай, если initialize_gradio_client вернет None (хотя сейчас он делает sys.exit)
        return

    # 2. Основной цикл обработки
    print("\n4. Начало обработки PNG файлов...")
    status_counts = {} # Словарь для подсчета результатов {status: count}

    for png_path in original_png_files:
        status = process_single_png(png_path, client)
        status_counts[status] = status_counts.get(status, 0) + 1

        # Прерываем цикл, если достигли квоты
        if status == "quota_exceeded":
            print("\nРабота скрипта прервана из-за ошибки квоты GPU.")
            break # Выходим из цикла for

    # 3. Итоговый отчет
    print_summary_report_phase2(len(original_png_files), status_counts)


def check_dependencies():
    """Проверяет наличие matool.exe и необходимых библиотек."""
    print("Проверка зависимостей...")
    matool_ok = False
    if MATOOL_EXE.exists():
        print(f"  [OK] Найден matool.exe: {MATOOL_EXE}")
        matool_ok = True
    else:
        alt_matool_path = BASE_DIR / "extracted" / "matool.exe"
        if alt_matool_path.exists():
            print(f"  [ПРЕДУПРЕЖДЕНИЕ] matool.exe не найден в {MATOOL_EXE}, используется: {alt_matool_path}")
            matool_ok = True
        else:
            print(f"  [КРИТИЧЕСКАЯ ОШИБКА] matool.exe не найден ни в {MATOOL_EXE}, ни в {alt_matool_path}.")

    # Проверка Pillow и Gradio уже сделана при импорте, но можно добавить явное сообщение
    pillow_ok = 'PIL' in sys.modules
    gradio_ok = 'gradio_client' in sys.modules
    if pillow_ok: print("  [OK] Библиотека Pillow найдена.")
    if gradio_ok: print("  [OK] Библиотека gradio_client найдена.")

    return matool_ok and pillow_ok and gradio_ok

if __name__ == "__main__":
     if check_dependencies():
        main()
     else:
        print("\nРабота скрипта прервана из-за отсутствия необходимых зависимостей.")
        sys.exit(1)