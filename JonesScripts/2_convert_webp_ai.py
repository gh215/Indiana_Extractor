import sys
import time
from pathlib import Path
from PIL import Image
from gradio_client import Client, handle_file
from conf import Config
from matool import Tool

config = Config()
try:
    matool = Tool(
        primary_exe_path=config.MATOOL_EXE_PRIMARY,
        cwd=config.BASE_DIR,
        alternative_exe_path=config.MATOOL_EXE_ALT
    )
except FileNotFoundError as e:
    print(f"\nКРИТИЧЕСКАЯ ОШИБКА: {e}")
    print("Работа скрипта прервана из-за отсутствия matool.exe.")
    sys.exit(1)

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
                return True
            if 'A' not in img_upscaled.getbands():
                 print("    Апскейл не содержит альфа-канал, конвертируем в RGBA.")
                 img_upscaled = img_upscaled.convert("RGBA")
            elif img_upscaled.mode != 'RGBA':
                 print(f"    Апскейл имеет режим {img_upscaled.mode}, но не RGBA. Конвертируем в RGBA.")
                 img_upscaled = img_upscaled.convert("RGBA")
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
    config.PROCESSED_PNG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для обработанных PNG: {config.PROCESSED_PNG_DIR}")
    if not config.USED_MAT_DIR.exists(): print(f"   ПРЕДУПРЕЖДЕНИЕ: Папка ({config.USED_MAT_DIR}) не найдена! Создаем."); config.USED_MAT_DIR.mkdir(parents=True, exist_ok=True)
    if not config.USED_MANUAL_MAT_DIR.exists(): print(f"   ПРЕДУПРЕЖДЕНИЕ: Папка ({config.USED_MANUAL_MAT_DIR}) не найдена! Создаем."); config.USED_MANUAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    if not config.EXTRACTED_DIR.exists():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с извлеченными PNG ({config.EXTRACTED_DIR}) не найдена!"); sys.exit(1)
    print("   Папки проверены/созданы.")

def find_original_pngs():
    """Находит все извлеченные PNG файлы в папках форматов."""
    print("\n2. Поиск извлеченных PNG файлов...")
    original_png_files = []
    for fmt_dir in config.FORMAT_DIRS.values():
        if fmt_dir.exists():
            original_png_files.extend(list(fmt_dir.glob('*.png'))) # Предполагаем, что апскейлить надо только PNG
    if not original_png_files:
        print(f"   Не найдено извлеченных PNG файлов в подпапках {config.EXTRACTED_DIR}. Нечего обрабатывать.")
        return []
    print(f"   Найдено {len(original_png_files)} извлеченных PNG файлов для обработки.")
    return sorted(original_png_files)

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
        original_mat_path = config.USED_MANUAL_MAT_DIR / mat_file_name_to_find
    else:
        base_name_only = png_stem
        mat_file_name_to_find = f"{base_name_only}.mat"
        original_mat_path = config.USED_MAT_DIR / mat_file_name_to_find
    return original_mat_path, mat_file_name_to_find

def upscale_image_via_api(client, png_path_to_upscale, target_png_path):
    """Отправляет изображение на апскейл через API, обрабатывает результат."""
    temp_result_path_str = None
    try:
        print(f"  Отправка {png_path_to_upscale.name} на апскейл...")
        start_time = time.time()
        api_result = client.predict(handle_file(str(png_path_to_upscale)), config.TARGET_MODEL_NAME, api_name=config.API_NAME)
        end_time = time.time()
        print(f"  Апскейл завершен за {end_time - start_time:.2f} сек.")

        if isinstance(api_result, list) and len(api_result) >= 2 and isinstance(api_result[1], str):
            temp_result_path_str = api_result[1]
        elif isinstance(api_result, str):
            temp_result_path_str = api_result
        else:
            print(f"  ОШИБКА: API вернул неожиданный результат: {type(api_result)} {api_result}")
            return None, "api_unexpected_result"

        if not temp_result_path_str:
            print(f"  ОШИБКА: Путь к результату от API пуст.")
            return None, "api_empty_path"

        temp_result_path = Path(temp_result_path_str)
        if not temp_result_path.exists():
            print(f"  ОШИБКА: API вернул путь ({temp_result_path_str}), но файл не найден.")
            return None, "api_file_not_found"

        print(f"  Конвертация результата в PNG: {target_png_path.name}")
        with Image.open(temp_result_path) as img:
            img.save(target_png_path, "PNG")
        print(f"  Успешно сохранено в {target_png_path.parent.name}")

        try:
            temp_result_path.unlink()
        except OSError as e:
            print(f"  ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить временный файл {temp_result_path.name}: {e}")

        return target_png_path, None

    except Exception as e:
        error_message_lower = str(e).lower()
        if config.QUOTA_ERROR_PHRASE in error_message_lower:
            print(f"\nОШИБКА: Обнаружена проблема с квотой GPU на Hugging Face Space!")
            print(f"  Сообщение API: {e}")
            return None, "quota_exceeded"
        else:
            print(f"  ОШИБКА при взаимодействии с API {config.HF_SPACE_URL} или конвертации:")
            print(f"    {e}")
            if target_png_path.exists():
                try: target_png_path.unlink()
                except OSError: pass
            return None, "api_other_error"

def process_single_png(original_extracted_png_path, client):
    """Полный цикл обработки одного PNG: апскейл, восстановление альфы."""
    png_stem = original_extracted_png_path.stem
    processed_png_path = config.PROCESSED_PNG_DIR / f"{png_stem}.png"
    print(f"\nОбработка: {original_extracted_png_path.relative_to(config.EXTRACTED_DIR)}")

    if processed_png_path.exists():
        print(f"  Пропуск: Файл {processed_png_path.name} уже существует в {config.PROCESSED_PNG_DIR.name}.")
        return "skipped"

    original_mat_path, mat_file_name_to_find = get_original_mat_path(png_stem)
    if not original_mat_path.exists():
        print(f"  ОШИБКА: Исходный файл {mat_file_name_to_find} не найден в {original_mat_path.parent.name}.")
        return "error_mat_not_found"

    upscaled_path, api_error_code = upscale_image_via_api(client, original_extracted_png_path, processed_png_path)

    if api_error_code == "quota_exceeded":
        return "quota_exceeded"
    if api_error_code:
        return "error_api"

    if not upscaled_path:
        print("  Критическая ошибка: upscale_image_via_api не вернула путь, но и не код ошибки.")
        return "error_internal"

    # Используем matool.info
    info_result = matool.info(original_mat_path)
    if info_result['error']:
        print(f"  ОШИБКА: Не удалось получить инфо из MAT {original_mat_path.name} после апскейла: {info_result['error']}.")
        return "error_mat_info_failed"

    has_alpha = info_result['has_alpha']

    if has_alpha:
        print("  Требуется восстановление альфа-канала...")
        alpha_restored_ok = restore_alpha(original_extracted_png_path, upscaled_path)
        if not alpha_restored_ok:
            print(f"  ОШИБКА: Не удалось восстановить альфа-канал для {upscaled_path.name}.")
            return "error_alpha_restore"

    if config.API_PAUSE_DURATION > 0:
        print(f"  Пауза {config.API_PAUSE_DURATION} сек...")
        time.sleep(config.API_PAUSE_DURATION)

    return "success"

def print_summary_report_phase2(total_files, status_counts):
    """Печатает итоговый отчет для фазы 2."""
    print("\n--- Скрипт 2 Завершен ---")
    print(f"Всего найдено извлеченных PNG для обработки: {total_files}")
    print(f"Успешно обработано (апскейл+конвертация+альфа): {status_counts.get('success', 0)}")
    print(f"Пропущено (уже существовали в {config.PROCESSED_PNG_DIR.name}): {status_counts.get('skipped', 0)}")

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
                 }.get(status, status)
                 print(f"    - {error_desc}: {count} раз")
        print("  Просмотрите лог выше для более подробной информации по каждому файлу.")

    print(f"\nТеперь можно запустить Скрипт для запаковки обработанных PNG из папки {config.PROCESSED_PNG_DIR.name}.")

def main():
    print("\n--- Скрипт 2: Апскейл (Hugging Face API), Конвертация, Альфа ---")

    setup_directories_phase2()
    original_png_files = find_original_pngs()
    if not original_png_files:
        print("\nРабота скрипта завершена, так как нет файлов для обработки.")
        return

    client = initialize_gradio_client(config.HF_SPACE_URL)
    if not client:
        return

    print("\n4. Начало обработки PNG файлов...")
    status_counts = {}

    for png_path in original_png_files:
        status = process_single_png(png_path, client)
        status_counts[status] = status_counts.get(status, 0) + 1

        if status == "quota_exceeded":
            print("\nРабота скрипта прервана из-за ошибки квоты GPU.")
            break

    print_summary_report_phase2(len(original_png_files), status_counts)


def check_dependencies():
    """Проверяет наличие matool.exe и необходимых библиотек."""
    print("Проверка зависимостей...")
    print(f"  [OK] Matool должен был быть найден (используется {matool.executable_path})")

    pillow_ok = 'PIL' in sys.modules
    gradio_ok = 'gradio_client' in sys.modules
    if pillow_ok: print("  [OK] Библиотека Pillow найдена.")
    else: print("  [ОШИБКА] Библиотека Pillow не найдена.")
    if gradio_ok: print("  [OK] Библиотека gradio_client найдена.")
    else: print("  [ОШИБКА] Библиотека gradio_client не найдена.")

    return pillow_ok and gradio_ok

if __name__ == "__main__":
     if check_dependencies():
        main()
     else:
        print("\nРабота скрипта прервана из-за отсутствия необходимых Python библиотек.")
        sys.exit(1)