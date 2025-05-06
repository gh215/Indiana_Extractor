import time
from pathlib import Path
from PIL import Image
from gradio_client import Client, handle_file
import sys
from conf import Config
from matool import Tool

def restore_alpha(original_png_path: Path, upscaled_png_path: Path):
    """Восстанавливает альфа-канал из оригинала в апскейленный PNG."""
    try:
        if not original_png_path.exists():
             print(f"    ОШИБКА: Оригинальный PNG {original_png_path.name} не найден в {original_png_path.parent}. Невозможно восстановить альфу.")
             return False
        with Image.open(original_png_path) as img_orig, Image.open(upscaled_png_path) as img_upscaled:
            if 'A' not in img_orig.getbands() and 'a' not in img_orig.mode.lower():
                # Если в оригинале нет альфы, но в апскейле есть, конвертируем в RGB
                if 'A' in img_upscaled.getbands() or 'a' in img_upscaled.mode.lower():
                     print("    В апскейле обнаружен альфа-канал, хотя в оригинале его не было. Конвертируем в RGB.")
                     rgb_img = img_upscaled.convert('RGB')
                     rgb_img.save(upscaled_png_path, "PNG")
                     rgb_img.close()
                return True

            print("    Обнаружен альфа-канал в оригинале. Применяем к апскейлу...")
            if img_upscaled.mode != 'RGBA':
                print(f"      Конвертируем апскейл из {img_upscaled.mode} в RGBA...")
                img_upscaled = img_upscaled.convert("RGBA")

            if 'A' in img_orig.getbands():
                alpha_orig = img_orig.getchannel('A')
            elif img_orig.mode == 'LA': # Grayscale + Alpha
                alpha_orig = img_orig.split()[-1]
            elif img_orig.mode == 'PA': # Palette + Alpha? (менее вероятно)
                # Попробуем конвертировать и взять альфу
                try:
                    alpha_orig = img_orig.convert('RGBA').getchannel('A')
                    print("      Взяли альфу из оригинала (режим PA) через конвертацию в RGBA.")
                except Exception:
                     print("      ОШИБКА: Не удалось извлечь альфа-канал из оригинала (режим PA).")
                     return False
            else: # Другие режимы с 'a'
                 try:
                    alpha_orig = img_orig.split()[-1] # Предполагаем, что альфа последняя
                    print(f"      Взяли альфа-канал из оригинала (режим {img_orig.mode}).")
                 except Exception:
                     print(f"      ОШИБКА: Не удалось извлечь альфа-канал из оригинала (режим {img_orig.mode}).")
                     return False


            alpha_resized = alpha_orig.resize(img_upscaled.size, Image.Resampling.NEAREST)

            # Вставляем альфу и сохраняем
            img_upscaled.putalpha(alpha_resized)
            img_upscaled.save(upscaled_png_path, "PNG")
            print("      Альфа-канал успешно восстановлен и сохранен.")
            return True

    except FileNotFoundError:
        print(f"    ОШИБКА: Файл не найден при попытке восстановления альфы ({original_png_path} или {upscaled_png_path}).")
        return False
    except Exception as e:
        print(f"    ОШИБКА: Не удалось восстановить альфа-канал для {upscaled_png_path.name}: {e}")
        return False

def setup_directories_phase2():
    """Проверяет и создает необходимые директории для фазы 2."""
    print("\n1. Проверка/создание необходимых папок...")
    Config.PROCESSED_PNG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Папка для обработанных PNG: {Config.PROCESSED_PNG_DIR.relative_to(Config.BASE_DIR)}")
    # Проверяем папки, откуда берутся MAT для информации
    if not Config.USED_MAT_DIR.exists():
        print(f"   ПРЕДУПРЕЖДЕНИЕ: Папка ({Config.USED_MAT_DIR.relative_to(Config.BASE_DIR)}) не найдена! Создаем.")
        Config.USED_MAT_DIR.mkdir(parents=True, exist_ok=True)
    if not Config.USED_MANUAL_MAT_DIR.exists():
        print(f"   ПРЕДУПРЕЖДЕНИЕ: Папка ({Config.USED_MANUAL_MAT_DIR.relative_to(Config.BASE_DIR)}) не найдена! Создаем.")
        Config.USED_MANUAL_MAT_DIR.mkdir(parents=True, exist_ok=True)
    if not Config.EXTRACTED_DIR.exists():
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Папка с извлеченными PNG ({Config.EXTRACTED_DIR}) не найдена!")
        sys.exit(1)
    print("   Папки проверены/созданы.")

def find_original_pngs():
    """Находит все извлеченные PNG файлы в папках форматов."""
    print("\n2. Поиск извлеченных PNG файлов...")
    original_png_files = []
    # Ищем во всех подпапках Config.EXTRACTED_DIR, определенных в Config.FORMAT_DIRS
    for fmt_key, fmt_dir in Config.FORMAT_DIRS.items():
        if fmt_dir.exists():
            found = list(fmt_dir.glob('*.png'))
            if found:
                print(f"   Найдено в '{fmt_key}' ({fmt_dir.name}): {len(found)} файлов")
                original_png_files.extend(found)

    if not original_png_files:
        print(f"   Не найдено извлеченных PNG файлов в подпапках форматов внутри {Config.EXTRACTED_DIR.name}. Нечего обрабатывать.")
        return []
    print(f"   Всего найдено {len(original_png_files)} извлеченных PNG файлов для обработки.")
    return sorted(original_png_files)

def initialize_gradio_client():
    """Инициализирует и возвращает клиент Gradio, используя URL из Config."""
    print(f"\n3. Подключение к Hugging Face Space: {Config.HF_SPACE_URL}...")
    try:
        client = Client(Config.HF_SPACE_URL, verbose=False)
        # Попробуем вызвать status для проверки? Не все спейсы это поддерживают.
        # Лучше просто продолжить. predict() покажет ошибку если что.
        print("   Подключение успешно (предположительно).")
        return client
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось подключиться к {Config.HF_SPACE_URL}. Ошибка: {e}")
        sys.exit(1)

def get_original_mat_path(png_stem: str):
    """Определяет путь к соответствующему исходному MAT файлу в USED_MAT_DIR или USED_MANUAL_MAT_DIR."""
    mat_in_used = Config.USED_MAT_DIR / f"{png_stem}.mat"
    mat_in_manual = Config.USED_MANUAL_MAT_DIR / f"{png_stem}.mat"

    if mat_in_used.exists():
        return mat_in_used, mat_in_used.name
    elif mat_in_manual.exists():
        return mat_in_manual, mat_in_manual.name
    else:
        if "__cel_" in png_stem:
            base_name_only = png_stem.split('__cel_')[0]
            mat_file_name_to_find = f"{base_name_only}.mat"
            original_mat_path = Config.USED_MANUAL_MAT_DIR / mat_file_name_to_find
            if original_mat_path.exists():
                 return original_mat_path, mat_file_name_to_find
        return None, f"{png_stem}.mat"

def upscale_image_via_api(client, png_path_to_upscale: Path, target_png_path: Path):
    """Отправляет изображение на апскейл через API, обрабатывает результат."""
    temp_result_path_str = None
    try:
        print(f"  Отправка {png_path_to_upscale.name} на апскейл (модель: {Config.TARGET_MODEL_NAME})...")
        start_time = time.time()

        api_result = client.predict(
            handle_file(str(png_path_to_upscale)),
            Config.TARGET_MODEL_NAME,
            api_name=Config.API_NAME
        )
        end_time = time.time()
        print(f"    Апскейл завершен за {end_time - start_time:.2f} сек.")

        if isinstance(api_result, str) and Path(api_result).is_file():
            temp_result_path_str = api_result
        # Некоторые API могут возвращать список или кортеж, где путь - один из элементов
        elif isinstance(api_result, (list, tuple)) and len(api_result) > 0 and isinstance(api_result[0], str) and Path(api_result[0]).is_file():
             temp_result_path_str = api_result[0]
             print(f"      API вернул {type(api_result)}, используем первый элемент как путь.")
        # Если API вернул словарь, ищем ключ 'image' или 'output' (примеры)
        elif isinstance(api_result, dict):
            found_path = None
            for key in ['image', 'output', 'result', 'file']:
                if key in api_result and isinstance(api_result[key], str) and Path(api_result[key]).is_file():
                    found_path = api_result[key]
                    print(f"      API вернул dict, используем значение ключа '{key}' как путь.")
                    break
            if found_path:
                 temp_result_path_str = found_path
            else:
                print(f"    ОШИБКА: API вернул словарь, но не удалось найти путь к файлу: {api_result}")
                return None, "api_unexpected_result_dict"
        else:
            print(f"    ОШИБКА: API вернул неожиданный результат: {type(api_result)} {str(api_result)[:200]}") # Ограничиваем вывод
            return None, "api_unexpected_result_other"

        if not temp_result_path_str:
            print(f"    ОШИБКА: Путь к результату от API пуст или некорректен.")
            return None, "api_empty_or_invalid_path"

        temp_result_path = Path(temp_result_path_str)
        if not temp_result_path.exists():
            print(f"    ОШИБКА: API вернул путь ({temp_result_path_str}), но файл не найден.")
            return None, "api_file_not_found"

        print(f"    Конвертация результата в PNG: {target_png_path.name}")
        try:
            with Image.open(temp_result_path) as img:
                target_png_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(target_png_path, "PNG")
            print(f"    Успешно сохранено в {target_png_path.parent.name}")
        except Exception as e_conv:
             print(f"    ОШИБКА при конвертации/сохранении в PNG: {e_conv}")
             # Удаляем временный файл, если он еще есть
             try: temp_result_path.unlink()
             except OSError: pass
             return None, "conversion_error"

        try:
            temp_result_path.unlink()
        except OSError as e_del:
            print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось удалить временный файл {temp_result_path.name}: {e_del}")

        return target_png_path, None # Успех

    except Exception as e:
        error_message_lower = str(e).lower()
        if Config.QUOTA_ERROR_PHRASE.lower() in error_message_lower:
            print(f"\nОШИБКА: Обнаружена проблема с квотой GPU на Hugging Face Space!")
            print(f"  Сообщение API: {e}")
            return None, "quota_exceeded" # Возвращаем None и код ошибки квоты
        else:
            print(f"    ОШИБКА при взаимодействии с API {Config.HF_SPACE_URL} или обработке:")
            print(f"      {e}")
            if target_png_path.exists():
                try: target_png_path.unlink()
                except OSError: pass
            return None, "api_other_error"

def process_single_png(original_extracted_png_path: Path, client, mt: Tool):
    """Полный цикл обработки одного PNG: апскейл, восстановление альфы."""
    png_stem = original_extracted_png_path.stem
    processed_png_path = Config.PROCESSED_PNG_DIR / f"{png_stem}.png"
    print(f"\nОбработка: {original_extracted_png_path.relative_to(Config.EXTRACTED_DIR)}")

    # Пропуск, если уже обработан
    if processed_png_path.exists():
        print(f"  Пропуск: Файл {processed_png_path.name} уже существует в {Config.PROCESSED_PNG_DIR.name}.")
        return "skipped"

    original_mat_path, mat_file_name_to_find = get_original_mat_path(png_stem)
    if not original_mat_path:
        print(f"  ОШИБКА: Исходный файл {mat_file_name_to_find} не найден ни в {Config.USED_MAT_DIR.name}, ни в {Config.USED_MANUAL_MAT_DIR.name}.")
        return "error_mat_not_found"

    upscaled_path, api_error_code = upscale_image_via_api(client, original_extracted_png_path, processed_png_path)

    if api_error_code == "quota_exceeded":
        return "quota_exceeded"
    if api_error_code:
        return f"error_api_{api_error_code}"

    if not upscaled_path: # Доп. проверка на случай если upscale_image_via_api вернула (None, None)
        print("  Критическая ошибка: upscale_image_via_api не вернула путь, но и не код ошибки.")
        return "error_internal"

    print(f"  Получение информации из {original_mat_path.name} для проверки альфы...")
    info_dict = mt.info(original_mat_path)
    if info_dict.get('error'):
        print(f"  ОШИБКА: Не удалось получить инфо из {original_mat_path.name} после апскейла: {info_dict['error']}")
        # Апскейл прошел, но не можем проверить альфу. Оставляем как есть, но считаем ошибкой.
        return "error_mat_info_failed"

    has_alpha = info_dict.get('has_alpha', False)
    print(f"    Альфа-канал в оригинале: {'Да' if has_alpha else 'Нет'}")

    if has_alpha:
        print("  Восстановление альфа-канала...")
        alpha_restored_ok = restore_alpha(original_extracted_png_path, upscaled_path)
        if not alpha_restored_ok:
            return "error_alpha_restore"
    else:
         try:
             with Image.open(upscaled_path) as img_final:
                 if 'A' in img_final.getbands() or 'a' in img_final.mode.lower():
                     print("    Альфы не было в оригинале, но она есть в апскейле. Конвертируем в RGB.")
                     rgb_img = img_final.convert('RGB')
                     rgb_img.save(upscaled_path, "PNG")
                     rgb_img.close()
         except Exception as e_check:
             print(f"    ПРЕДУПРЕЖДЕНИЕ: Не удалось проверить/удалить альфа-канал из финального файла: {e_check}")


    # Пауза перед следующим файлом (используем значение из Config)
    if Config.API_PAUSE_DURATION > 0:
        print(f"  Пауза {Config.API_PAUSE_DURATION} сек...")
        time.sleep(Config.API_PAUSE_DURATION)

    return "success"

def print_summary_report_phase2(total_files, status_counts):
    """Печатает итоговый отчет для фазы 2."""
    print("\n--- Скрипт 2 Завершен ---")
    print(f"Всего найдено извлеченных PNG для обработки: {total_files}")
    print(f"Успешно обработано (апскейл+конвертация+альфа): {status_counts.get('success', 0)}")
    print(f"Пропущено (уже существовали в {Config.PROCESSED_PNG_DIR.name}): {status_counts.get('skipped', 0)}")

    # Собираем все ошибки
    errors_total = sum(v for k, v in status_counts.items() if k.startswith("error_"))
    quota_errors = status_counts.get('quota_exceeded', 0)

    print(f"Возникло ошибок при обработке: {errors_total}")
    if quota_errors > 0:
         print(f"Прервано из-за ошибки квоты GPU: {quota_errors} раз")

    if errors_total > 0:
        print("  Детали ошибок:")
        api_errors_general = 0
        api_errors_detail = {}
        for status, count in status_counts.items():
             if status.startswith("error_api_"):
                 api_error_type = status.replace("error_api_", "")
                 api_errors_detail[api_error_type] = api_errors_detail.get(api_error_type, 0) + count
                 api_errors_general += count
             elif status.startswith("error_") and status != "error_api_" and count > 0:
                 # Другие ошибки
                 error_desc = {
                     "error_mat_not_found": "Не найден исходный MAT",
                     "error_mat_info_failed": "Не удалось получить инфо из MAT после апскейла",
                     "error_alpha_restore": "Ошибка восстановления альфа-канала",
                     "error_internal": "Внутренняя ошибка логики"
                 }.get(status, status) #
                 print(f"    - {error_desc}: {count} раз")

        if api_errors_general > 0:
             print(f"    - Ошибка API Hugging Face / Конвертации: {api_errors_general} раз")
             for api_type, count in api_errors_detail.items():
                 print(f"        - Тип: {api_type}: {count} раз")

        print("  Просмотрите лог выше для более подробной информации по каждому файлу.")

    if status_counts.get('success', 0) > 0:
        print(f"\nТеперь можно запустить Скрипт 3 (`pack_mats.py`) или 4 (`pack_cel_mats.py`)")
        print(f"для запаковки обработанных PNG из папки: {Config.PROCESSED_PNG_DIR.name}")
    else:
        print("\nНе было успешно обработано ни одного файла.")


def main():
    """Фаза 2: Автоматический апскейл через HF Space, конвертация и восстановление альфы."""
    print("\n--- Скрипт 2: Апскейл (Hugging Face API), Конвертация, Альфа ---")

    # 1. Подготовка
    setup_directories_phase2()

    try:
        mt = Tool(Config.MATOOL_EXE_PRIMARY, Config.BASE_DIR, Config.MATOOL_EXE_ALT)
    except FileNotFoundError as e:
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: Не удалось инициализировать matool: {e}")
        print("Работа скрипта прервана.")
        sys.exit(1)

    original_png_files = find_original_pngs()
    if not original_png_files:
        print("\nРабота скрипта завершена, так как нет файлов для обработки.")
        return

    client = initialize_gradio_client()
    if not client:
        return

    # 2. Основной цикл обработки
    print("\n4. Начало обработки PNG файлов...")
    status_counts = {}
    total_files_to_process = len(original_png_files)

    for i, png_path in enumerate(original_png_files):
        print(f"--- Файл {i + 1}/{total_files_to_process} ---")
        status = process_single_png(png_path, client, mt)
        status_counts[status] = status_counts.get(status, 0) + 1

        if status == "quota_exceeded":
            print("\nРабота скрипта прервана из-за ошибки квоты GPU.")
            break

    # 3. Итоговый отчет
    print_summary_report_phase2(total_files_to_process, status_counts)

def check_dependencies_phase2():
    """Проверяет наличие необходимых библиотек."""
    print("Проверка зависимостей...")
    ok = True
    try:
        import PIL
        print("  [OK] Библиотека Pillow (PIL) найдена.")
    except ImportError:
        print("  [ОШИБКА] Библиотека Pillow (PIL) не найдена. Установите: pip install Pillow")
        ok = False
    try:
        import gradio_client
        print("  [OK] Библиотека gradio_client найдена.")
    except ImportError:
        print("  [ОШИБКА] Библиотека gradio_client не найдена. Установите: pip install gradio_client")
        ok = False
    return ok

if __name__ == "__main__":
     if check_dependencies_phase2():
        main()
     else:
        print("\nРабота скрипта прервана из-за отсутствия необходимых зависимостей.")
        sys.exit(1)