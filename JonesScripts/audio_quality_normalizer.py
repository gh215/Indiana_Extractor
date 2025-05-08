import sys
from pathlib import Path
import soundfile as sf
import numpy as np
import pyloudnorm as pyln
import traceback
import math
# Предполагается, что у тебя есть файл audio_conf.py с классом Config
# Если его нет, нужно будет определить константы прямо в этом скрипте
from audio_conf import Config

# --- Константы и Настройки из конфига ---
NORMALIZATION_MODE = Config.S2_NORMALIZER_MODE
TARGET_LOUDNESS_LUFS_CONFIG = Config.S2_NORMALIZER_TARGET_LOUDNESS_LUFS  # Переименовал, чтобы не конфликтовать
ORIGINAL_FOLDER = Config.S2_NORMALIZER_ORIGINAL_AUDIO_DIR_FOR_MATCHING
INPUT_FOLDER = Config.S2_NORMALIZER_INPUT_UPSCALED_DIR
OUTPUT_FOLDER = Config.S2_NORMALIZER_OUTPUT_DIR
MAX_PEAK_DBFS_CONFIG = Config.S2_NORMALIZER_MAX_TRUE_PEAK_DBFS  # Переименовал
SUPPORTED_EXTENSIONS_LIST = Config.SUPPORTED_AUDIO_EXTENSIONS
MIN_DURATION_SEC_FOR_LUFS = Config.S2_NORMALIZER_MIN_DURATION_SEC_FOR_LUFS_MEASUREMENT


# --- Вспомогательные функции ---

def calculate_rms(audio_data):
    """Рассчитывает RMS (среднеквадратичное) значение для аудиоданных."""
    if audio_data.shape[0] == 0:
        return 0.0
    rms = np.sqrt(np.mean(audio_data ** 2))
    return rms


def measure_lufs_peak_rms(audio_data, sample_rate):
    """
    Измеряет LUFS (если возможно), Sample Peak (dBFS) и RMS (линейное) аудиоданных.
    Возвращает: (lufs, sample_peak_dbfs, rms_linear)
    lufs будет None, если измерение невозможно (слишком короткий файл).
    """
    lufs = None
    sample_peak_dbfs = -np.inf  # Для тишины
    rms_linear = 0.0  # Для тишины

    try:
        # Убедимся, что данные в float32 и имеют правильную размерность
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        if audio_data.ndim == 1:
            audio_data = audio_data[:, np.newaxis]  # Преобразуем моно в (samples, 1)

        num_samples = audio_data.shape[0]
        if num_samples == 0:
            print("    Предупреждение: Пустой аудиофайл.")
            return None, -np.inf, 0.0

        # 1. Измеряем Sample Peak и RMS (это можно сделать всегда)
        max_abs_sample = np.max(np.abs(audio_data))
        if max_abs_sample > 1e-9:  # Проверка на очень малые значения, близкие к нулю
            sample_peak_dbfs = 20.0 * np.log10(
                max_abs_sample)  # Не добавляем эпсилон, если max_abs_sample гарантированно > 0
        # Если max_abs_sample == 0 (или очень мал), sample_peak_dbfs остается -np.inf

        rms_linear = calculate_rms(audio_data)

        # 2. Пытаемся измерить LUFS
        duration_sec = num_samples / sample_rate if sample_rate > 0 else 0
        if duration_sec >= MIN_DURATION_SEC_FOR_LUFS:
            try:
                meter = pyln.Meter(sample_rate)  # block_size можно настроить, если нужно
                measured_lufs = meter.integrated_loudness(audio_data)
                if math.isfinite(measured_lufs):
                    lufs = measured_lufs
                else:  # pyloudnorm может вернуть -inf для тишины
                    if rms_linear < 1e-7:  # Если RMS очень мал (практически тишина)
                        lufs = -np.inf  # Согласуем с пиком для тишины
                    else:
                        # Если RMS значим, а LUFS=-inf, это странно, но может быть для некоторых сигналов
                        print(
                            f"    Предупреждение: LUFS измерен как {measured_lufs}, но RMS ({rms_linear:.2e}) не нулевой. LUFS будет None.")
                        lufs = None  # Заставим использовать RMS, если это возможно
            except ValueError as e:
                if "Audio must have length greater than the block size" in str(e) or \
                        "Input signal is too short" in str(e):  # pyloudnorm может выдавать разные сообщения
                    print(
                        f"    Информация: Файл слишком короткий ({duration_sec:.3f} сек, порог {MIN_DURATION_SEC_FOR_LUFS} сек) для LUFS. LUFS будет None.")
                    lufs = None
                else:
                    raise  # Другая ошибка ValueError
        else:
            print(
                f"    Информация: Файл слишком короткий ({duration_sec:.3f} сек, порог {MIN_DURATION_SEC_FOR_LUFS} сек) для LUFS. LUFS будет None.")
            lufs = None

        return lufs, sample_peak_dbfs, rms_linear

    except Exception as e:
        print(f"    !!! Ошибка при измерении LUFS/пика/RMS для файла: {e}")
        traceback.print_exc(limit=1)
        return None, None, None


def apply_gain_and_clip(audio_data, gain_db, clipping_limit_dbfs):  # Переименовал для ясности
    """Применяет усиление (gain_db) и затем жестко клипует до clipping_limit_dbfs."""
    try:
        audio_data_processed = audio_data.copy()
        if audio_data_processed.dtype != np.float32:
            audio_data_processed = audio_data_processed.astype(np.float32)

        gain_linear = 10.0 ** (gain_db / 20.0)
        audio_data_processed = audio_data_processed * gain_linear

        clipping_limit_linear = 10.0 ** (clipping_limit_dbfs / 20.0)
        np.clip(audio_data_processed, -clipping_limit_linear, clipping_limit_linear, out=audio_data_processed)

        return audio_data_processed
    except Exception as e:
        print(f"    !!! Ошибка при применении усиления/клиппинга: {e}")
        traceback.print_exc(limit=1)
        return None


def normalize_audio_file(input_path: Path, output_path: Path, mode: str,
                         target_lufs_from_config: float, max_peak_from_config: float,
                         original_dir: Path = None):
    """
    Нормализует аудиофайл по LUFS/RMS, стремясь к параметрам оригинала
    или к целевому LUFS, с клиппингом по Sample Peak оригинала или конфига.
    """
    try:
        if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS_LIST:
            print(f"--- Пропуск: Неподдерживаемое расширение -> {input_path.name}")
            return "skipped_extension"

        print(f"Обработка: {input_path.name} (Режим: {mode})")

        audio_in, sample_rate = sf.read(input_path, dtype='float32', always_2d=True)
        current_lufs, current_sample_peak, current_rms = measure_lufs_peak_rms(audio_in, sample_rate)

        if current_lufs is None and current_sample_peak is None and current_rms is None:  # Полная ошибка измерения
            print(f"    !!! Не удалось измерить параметры для {input_path.name}")
            return "error_measure_input"

        if current_rms < 1e-7 and current_sample_peak == -np.inf:  # Проверка на тишину по RMS
            print("    Исходный апскейл-файл - тишина. Копирование...")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, audio_in, sample_rate)
            return "success_silent_copy"

        # Инициализация целевых значений и флагов
        target_lufs = None
        target_rms = None
        orig_lufs = None  # Для вывода в статистику
        orig_sample_peak = None  # Для определения лимита клиппинга

        gain_to_apply_db = 0.0  # Усиление по умолчанию
        final_clipping_limit_dbfs = max_peak_from_config  # Лимит клиппинга по умолчанию

        if mode == 'TARGET':
            if current_lufs is not None and current_lufs != -np.inf:
                target_lufs = target_lufs_from_config
                gain_to_apply_db = target_lufs - current_lufs
                print(f"    Метод: LUFS. Цель (из конфига): {target_lufs:.2f} LUFS.")
                print(f"    Текущий LUFS апскейла: {current_lufs:.2f} LUFS.")
            else:  # LUFS входного не измерим или тишина (но RMS не ноль)
                # В режиме TARGET нет осмысленного RMS-фоллбэка без эталона RMS.
                print(
                    f"    Предупреждение: LUFS не измерен для '{input_path.name}' в режиме TARGET. Оставляем громкость как есть.")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                sf.write(output_path, audio_in, sample_rate)
                return "success_target_lufs_unavailable"

        elif mode == 'MATCH_ORIGINAL':
            if not original_dir or not original_dir.is_dir():
                print(f"    !!! Ошибка: Папка с оригиналами '{original_dir}' не найдена.")
                return "error_original_dir_missing"

            relative_path_from_input_root = input_path.relative_to(INPUT_FOLDER)
            original_file_path_primary_attempt = original_dir / relative_path_from_input_root
            original_file_path = None

            if original_file_path_primary_attempt.is_file():
                original_file_path = original_file_path_primary_attempt
            else:
                print(f"    Оригинал не найден по прямому пути: {original_file_path_primary_attempt}.")
                print(f"    Поиск файла '{input_path.name}' во всех подпапках '{original_dir}'...")
                found_originals = list(original_dir.rglob(input_path.name))
                if not found_originals:
                    print(
                        f"    !!! Ошибка: Оригинальный файл '{input_path.name}' НЕ НАЙДЕН в '{original_dir}' и его подпапках.")
                    return "error_original_file_missing_deep_search"
                elif len(found_originals) == 1:
                    original_file_path = found_originals[0]
                    print(f"    Найден оригинал (поиск по имени): {original_file_path}")
                else:
                    print(
                        f"    !!! ПРЕДУПРЕЖДЕНИЕ: Найдено НЕСКОЛЬКО оригинальных файлов '{input_path.name}'. Пропуск.")
                    for f_path in found_originals: print(f"        - {f_path}")
                    return "error_original_file_ambiguous"

            if not original_file_path:  # Дополнительная проверка
                print(f"    !!! КРИТИЧЕСКАЯ ОШИБКА: Путь к оригиналу не определен для {input_path.name}.")
                return "error_original_path_not_determined_crit"

            print(f"    Измерение оригинала: {original_file_path.name} (Путь: {original_file_path})")
            try:
                audio_orig, sr_orig = sf.read(original_file_path, dtype='float32', always_2d=True)
            except Exception as e:
                print(f"    !!! Ошибка чтения оригинального файла {original_file_path}: {e}")
                return "error_read_original"

            if sr_orig != sample_rate:
                print(
                    f"    Предупреждение: Разная частота дискретизации у оригинала ({sr_orig}Hz) и апскейла ({sample_rate}Hz).")

            orig_lufs, orig_sample_peak, orig_rms = measure_lufs_peak_rms(audio_orig, sr_orig)

            if orig_lufs is None and orig_sample_peak is None and orig_rms is None:  # Ошибка измерения оригинала
                print(f"    !!! Не удалось измерить параметры ОРИГИНАЛА {original_file_path.name}")
                return "error_measure_original"

            if orig_rms < 1e-7 and orig_sample_peak == -np.inf:  # Оригинал - тишина
                print("    Оригинальный файл - тишина. Апскейл приводится к тишине.")
                silent_audio = np.zeros_like(audio_in)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                sf.write(output_path, silent_audio, sample_rate)
                return "success_match_original_silent"

            # Определяем метод и усиление
            if current_lufs is not None and current_lufs != -np.inf and \
                    orig_lufs is not None and orig_lufs != -np.inf:
                target_lufs = orig_lufs
                gain_to_apply_db = target_lufs - current_lufs
                print(f"    Метод: LUFS. Цель (из оригинала): {target_lufs:.2f} LUFS.")
                print(f"    Текущий LUFS апскейла: {current_lufs:.2f} LUFS.")
            elif current_rms > 1e-7 and orig_rms > 1e-7:  # Оба RMS значимы
                target_rms = orig_rms
                target_rms_db = 20 * np.log10(target_rms)
                current_rms_db = 20 * np.log10(current_rms)
                gain_to_apply_db = target_rms_db - current_rms_db
                print(f"    Метод: RMS (Fallback). Цель (из оригинала): {target_rms_db:.2f} dBFS RMS.")
                print(f"    Текущий RMS апскейла: {current_rms_db:.2f} dBFS RMS.")
            else:
                print(
                    f"    Предупреждение: Не удалось определить метод нормализации для {input_path.name} / его оригинала. Оставляем громкость как есть.")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                sf.write(output_path, audio_in, sample_rate)
                return "success_match_method_undefined"

            # Устанавливаем лимит клиппинга по Sample Peak оригинала, если он строже конфига
            if orig_sample_peak is not None and orig_sample_peak != -np.inf:
                if orig_sample_peak < final_clipping_limit_dbfs:
                    final_clipping_limit_dbfs = orig_sample_peak
                    print(
                        f"    Установлен лимит клиппинга по Sample Peak оригинала: {final_clipping_limit_dbfs:.2f} dBFS.")
                # else:
                #     print(f"    Лимит клиппинга из конфига ({max_peak_from_config:.2f} dBFS) остается (Sample Peak оригинала {orig_sample_peak:.2f} dBFS не строже).")

        else:  # Неизвестный режим
            print(f"!!! Неизвестный режим нормализации: {mode}")
            return "error_unknown_mode"

        # --- Применение усиления и клиппинга ---
        print(f"    Текущий Sample Peak апскейла: {current_sample_peak:.2f} dBFS.")
        print(f"    Применяемое усиление для достижения целевой громкости: {gain_to_apply_db:.2f} dB.")

        predicted_sample_peak_after_gain = current_sample_peak + gain_to_apply_db
        if predicted_sample_peak_after_gain > final_clipping_limit_dbfs:
            print(
                f"    Предупреждение: Целевое усиление поднимет Sample Peak до ~{predicted_sample_peak_after_gain:.2f} dBFS.")
            print(
                f"                   Результат будет ограничен (клиппирован) до {final_clipping_limit_dbfs:.2f} dBFS.")

        final_audio = apply_gain_and_clip(audio_in, gain_to_apply_db, final_clipping_limit_dbfs)

        if final_audio is None:
            return "error_apply_gain"

        # --- Финальная проверка и вывод ---
        final_lufs_check, final_peak_check, _ = measure_lufs_peak_rms(final_audio, sample_rate)
        print("    --- Финальные измеренные параметры обработанного файла ---")
        if final_lufs_check is not None:
            target_lufs_display = "N/A (RMS)"
            if target_lufs is not None:  # Если был LUFS-матчинг
                target_lufs_display = f"{target_lufs:.2f} LUFS"
            elif mode == 'TARGET' and target_lufs_from_config is not None:  # Если был TARGET LUFS
                target_lufs_display = f"{target_lufs_from_config:.2f} LUFS"
            print(f"    Измеренный LUFS: {final_lufs_check:.2f} LUFS (Цель была: {target_lufs_display})")

        if final_peak_check is not None:
            print(
                f"    Измеренный Sample Peak: {final_peak_check:.2f} dBFS (Лимит клиппинга был: {final_clipping_limit_dbfs:.2f} dBFS)")
        # True Peak будет виден в Youlean или другом анализаторе.

        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, final_audio, sample_rate)
        return "success"

    except sf.SoundFileError as e:
        print(f"!!! Ошибка чтения/записи файла {input_path.name}: {e}")
        return "error_soundfile"
    except Exception as e:
        print(f"!!! Неизвестная ошибка при обработке {input_path.name}: {e}")
        traceback.print_exc(limit=2)
        return "error_unknown"


# --- Основной блок выполнения ---
if __name__ == "__main__":
    print("-" * 70)
    print("Запуск скрипта пакетной LUFS/RMS нормализации аудио")
    print(f"Режим: {NORMALIZATION_MODE}")
    print(f"Папка с исходными (апскейленными) файлами: {INPUT_FOLDER}")
    if NORMALIZATION_MODE == 'TARGET':
        print(f"Целевая громкость (из конфига): {TARGET_LOUDNESS_LUFS_CONFIG} LUFS")
    elif NORMALIZATION_MODE == 'MATCH_ORIGINAL':
        print(f"Папка с оригиналами для сопоставления: {ORIGINAL_FOLDER}")
        if not ORIGINAL_FOLDER or not ORIGINAL_FOLDER.is_dir():
            print(f"!!! КРИТИЧЕСКАЯ ОШИБКА: Папка с оригиналами '{ORIGINAL_FOLDER}' не найдена!")
            sys.exit(1)
    print(f"Папка для сохранения результатов: {OUTPUT_FOLDER}")
    print(f"Максимальный Sample Peak (из конфига, может быть переопределен оригиналом): {MAX_PEAK_DBFS_CONFIG} dBFS")
    print(f"Поддерживаемые расширения: {', '.join(SUPPORTED_EXTENSIONS_LIST)}")
    print(f"Минимальная длина для LUFS: {MIN_DURATION_SEC_FOR_LUFS} сек.")
    print("-" * 70)

    if not INPUT_FOLDER.is_dir():
        print(f"Ошибка: Папка с исходными файлами не найдена: {INPUT_FOLDER}")
        sys.exit(1)

    try:
        OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
        print(f"Выходная папка '{OUTPUT_FOLDER}' готова.")
    except OSError as e:
        print(f"Ошибка: Не удалось создать выходную папку: {OUTPUT_FOLDER} ({e})")
        sys.exit(1)

    status_counts = {}
    all_input_files = [item for item in INPUT_FOLDER.rglob('*') if
                       item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS_LIST]
    total_files_to_process = len(all_input_files)
    print(f"Найдено поддерживаемых аудиофайлов для обработки: {total_files_to_process}")

    for i, item_path in enumerate(all_input_files):
        print(f"\n--- Файл {i + 1} из {total_files_to_process}: {item_path.name} ---")

        relative_path = item_path.relative_to(INPUT_FOLDER)
        output_file_path = OUTPUT_FOLDER / relative_path

        status = normalize_audio_file(
            input_path=item_path,
            output_path=output_file_path,
            mode=NORMALIZATION_MODE,
            target_lufs_from_config=TARGET_LOUDNESS_LUFS_CONFIG,
            max_peak_from_config=MAX_PEAK_DBFS_CONFIG,
            original_dir=ORIGINAL_FOLDER if NORMALIZATION_MODE == 'MATCH_ORIGINAL' else None
        )
        status_counts[status] = status_counts.get(status, 0) + 1

    # Статистика пропущенных не-аудио файлов (если нужно)
    all_items_in_input = list(INPUT_FOLDER.rglob('*'))
    skipped_non_audio_count = 0
    for item in all_items_in_input:
        if item.is_file() and item.suffix.lower() not in SUPPORTED_EXTENSIONS_LIST:
            skipped_non_audio_count += 1
        elif not item.is_file():  # Папки и др.
            skipped_non_audio_count += 1  # Считаем все не-файлы и не-поддерживаемые файлы как пропущенные тут
    if "skipped_extension" in status_counts:  # Если уже посчитано внутри normalize_audio_file
        # Убираем дублирование подсчета неподдерживаемых расширений
        skipped_non_audio_count -= status_counts["skipped_extension"]

    print("-" * 70)
    print("Обработка завершена.")
    print("\n--- ИТОГОВАЯ СТАТИСТИКА ---")

    success_keys = [k for k in status_counts if k.startswith("success")]
    total_successful = sum(status_counts[k] for k in success_keys)
    print(f"Успешно обработано/скопировано файлов: {total_successful}")
    for k in success_keys:
        print(f"  - {k}: {status_counts[k]}")

    error_keys = [k for k in status_counts if k.startswith("error")]
    total_errors = sum(status_counts[k] for k in error_keys)
    if total_errors > 0:
        print(f"\nОшибок при обработке: {total_errors}")
        for k in error_keys:
            print(f"  - {k}: {status_counts[k]}")

    skipped_keys = [k for k in status_counts if k.startswith("skipped_")]  # Только из функции normalize
    total_skipped_in_func = sum(status_counts[k] for k in skipped_keys)

    # Добавляем пропущенные вне функции (папки, другие расширения)
    # Это немного грубый подсчет, если много вложенных папок
    # total_skipped_overall = total_skipped_in_func + skipped_non_audio_count - total_files_to_process

    if total_skipped_in_func > 0:
        print(f"\nПропущено файлов при попытке обработки (из функции): {total_skipped_in_func}")
        for k in skipped_keys:
            print(f"  - {k}: {status_counts[k]}")

    print("-" * 70)

    if total_errors > 0:
        print("!!! В процессе обработки были ошибки. Проверьте вывод выше. !!!")
    else:
        print("Скрипт завершился (проверьте статистику на наличие ошибок или пропусков).")