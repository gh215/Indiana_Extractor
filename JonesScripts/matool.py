import subprocess
import re
from pathlib import Path

class Tool:
    def __init__(self, primary_exe_path: Path, cwd: Path):
        self.cwd = cwd
        self.executable_path = None #

        if primary_exe_path.exists() and primary_exe_path.is_file():
            self.executable_path = primary_exe_path
            print(f"Matool: Используется {self.executable_path}")
        else:
            error_msg = f"matool.exe не найден по пути: {primary_exe_path}"
            raise FileNotFoundError(error_msg)
    def run_command(self, command: str, *args) -> tuple[str | None, str | None, str | None]:
        # Почему str(arg)
        cmd = [str(self.executable_path), command] + [str(arg) for arg in args]

        # Формируем строку для лога (сокращенную для create с большим числом файлов)
        cmd_str_display = f"'{self.executable_path.name}' {command}"

        # НОВОЕ: Блок для сокращения отображения команды 'create' с большим количеством файлов.
        if command.lower() == 'create' and len(args) > 3:
            format_str_arg = args[0] # Извлечение аргументов для ясности
            output_mat_path_arg = Path(args[1])
            input_png_paths_args = [Path(p) for p in args[2:]]
            if len(input_png_paths_args) > 1: # Если PNG файлов больше одного
                # Формирование сокращенной строки для лога
                cmd_str_display += f" {format_str_arg} '{output_mat_path_arg.name}' '{input_png_paths_args[0].name}' ... ({len(input_png_paths_args) - 1} more PNGs)"
            else: # Если PNG файл один
                cmd_str_display += f" {format_str_arg} '{output_mat_path_arg.name}'"
                if input_png_paths_args: # И если он действительно есть
                    cmd_str_display += f" '{input_png_paths_args[0].name}'"
        else:
             # НОВОЕ: Блок для формирования строки аргументов для лога для остальных команд (или create с <2 PNG).
             processed_args = []
             for p_arg in args:
                 if isinstance(p_arg, Path): # Проверка, является ли аргумент объектом Path
                     arg_display = f"'{p_arg.name}'"
                 else:
                     s_arg = str(p_arg)
                     if ' ' in s_arg:  # Если есть пробел, то в кавычки
                         arg_display = f"'{s_arg}'"
                     else:  # Иначе без кавычек
                         arg_display = s_arg
                 processed_args.append(arg_display)
             if processed_args:  # Добавляем пробел только если есть аргументы
                 cmd_str_display += " " + ' '.join(processed_args)

        print(f"  Matool Запуск: {cmd_str_display} (в {self.cwd.name})")

        try:
            # Разобраться
            result = subprocess.run(cmd, capture_output=True, text=True, check=False,
                                    encoding='utf-8', errors='ignore', cwd=self.cwd)

            stdout = result.stdout.strip() if result.stdout else None
            stderr = result.stderr.strip() if result.stderr else None

            # Разобраться в chr, replace
            if command.lower() in ['create', 'info']:
                if stdout: print(f"    Matool Stdout:\n      {stdout.replace(chr(10), chr(10) + '      ')}")
                if stderr: print(f"    Matool Stderr:\n      {stderr.replace(chr(10), chr(10) + '      ')}")

            if result.returncode != 0: #
                error_msg = f"Команда matool {command} завершилась с кодом {result.returncode}."
                print(f"  Matool ОШИБКА: {error_msg}")
                # ИЗМЕНЕНО: В первой версии здесь был дополнительный `if stderr: print(...)`.
                # Сейчас он убран, т.к. stderr для 'create'/'info' печатается выше, а для других команд stderr будет возвращен и может быть обработан вызывающим кодом.
                return stdout, stderr, error_msg
            return stdout, stderr, None

        except Exception as e:
            error_msg = f"Непредвиденная ошибка при запуске matool {command}: {e}"
            print(f"  Matool КРИТ. ОШИБКА: {error_msg}")
            return None, None, error_msg

    def info(self, mat_path: Path) -> dict:
        stdout, stderr, run_error = self.run_command("info", mat_path)
        result = {
            'format_raw': None,
            'format_standardized': 'unknown',
            'has_alpha': False,
            'texture_count': None,
            'stdout': stdout,
            'stderr': stderr,
            'error': run_error
        }

        if run_error:
            return result

        if not stdout:
            result['error'] = f"Получен пустой stdout от matool info для {mat_path.name}"
            print(f"  Matool ПРЕДУПРЕЖДЕНИЕ: {result['error']}")
            return result

        try:
            format_match = re.search(r"Encoding:\.*([A-Z0-9\-]+)", stdout)
            if format_match:
                result['format_raw'] = format_match.group(1).lower()
                std_format = result['format_raw'].replace('-', '')
                if std_format in ["rgb565", "rgba4444", "rgba5551"]:
                     result['format_standardized'] = std_format
                if std_format in ["rgba4444", "rgba5551"]:
                    result['has_alpha'] = True
            else:
                mode_match = re.search(r"Color mode:\.*?\s*(RGBA)", stdout)
                if mode_match:
                    result['has_alpha'] = True
                    result['format_standardized'] = "rgba"

            # ИСПРАВЛЕНО: Условие изменено с `is None` на `== 'unknown'`.
            if result['format_standardized'] == 'unknown':
                 result['format_standardized'] = "rgba" if result['has_alpha'] else "unknown"

        except Exception as e_fmt:
            # ИСПРАВЛЕНО: Реализовано добавление новой ошибки к существующей, а не перезапись.
            # В первой версии ошибка парсинга формата перезаписывала result['error'].
            current_error = result.get('error')
            error_message = f"Ошибка парсинга формата: {e_fmt}"
            result['error'] = f"{current_error}; {error_message}" if current_error else error_message
            print(f"  Matool ОШИБКА парсинга: {error_message}")

        try:
            texture_count_match = re.search(r"Total textures:\.*?(\d+)", stdout)
            if texture_count_match:
                result['texture_count'] = int(texture_count_match.group(1))
            else:
                 print(f"  Matool ПРЕДУПРЕЖДЕНИЕ: Не удалось определить количество текстур для {mat_path.name}.")
                 result['texture_count'] = None
        except Exception as e_cnt:
             # Логика добавления ошибки парсинга кол-ва текстур к существующей ошибке
             result['error'] = (result['error'] + "; " if result['error'] else "") + f"Ошибка парсинга кол-ва текстур: {e_cnt}"
             print(f"  Matool ОШИБКА парсинга: {result['error']}")
             result['texture_count'] = None

        return result

    def extract(self, mat_path: Path) -> bool:
        _, _, run_error = self.run_command("extract", mat_path)
        return run_error is None

    def create(self, format_str: str, output_mat_path: Path, *input_png_paths: Path) -> bool:
        if not input_png_paths:
             print("  Matool ОШИБКА: Для команды create не переданы входные PNG файлы.")
             return False
        _, _, run_error = self.run_command("create", format_str, output_mat_path, *input_png_paths)
        return run_error is None