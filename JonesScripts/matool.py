import subprocess
import re
from pathlib import Path

class Tool:
    def __init__(self, primary_exe_path: Path, cwd: Path, alternative_exe_path: Path | None = None):
        self.cwd = cwd
        self.executable_path = None

        if primary_exe_path.exists() and primary_exe_path.is_file():
            self.executable_path = primary_exe_path
            print(f"Matool: Используется {self.executable_path}")
        elif alternative_exe_path and alternative_exe_path.exists() and alternative_exe_path.is_file():
            self.executable_path = alternative_exe_path
            print(f"Matool: ПРЕДУПРЕЖДЕНИЕ: {primary_exe_path.name} не найден, используется {self.executable_path}")
        else:
            error_msg = f"matool.exe не найден по путям: {primary_exe_path} или {alternative_exe_path}"
            raise FileNotFoundError(error_msg)

    def run_command(self, command: str, *args) -> tuple[str | None, str | None, str | None]:
        cmd = [str(self.executable_path), command] + [str(arg) for arg in args]

        # Формируем строку для лога (сокращенную для create с большим числом файлов)
        cmd_str_display = f"'{self.executable_path.name}' {command}"
        if command.lower() == 'create' and len(args) > 3:
             cmd_str_display += f" {args[0]} '{Path(args[1]).name}' '{Path(args[2]).name}' ... ({len(args) - 3} more PNGs)"
        else:
             cmd_str_display += ' '.join(f"'{Path(p).name if isinstance(p, Path) else str(p)}'"
                                        if isinstance(p, Path) or ' ' in str(p) else str(p) for p in args)

        print(f"  Matool Запуск: {cmd_str_display} (в {self.cwd.name})")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False,
                                    encoding='utf-8', errors='ignore', cwd=self.cwd)

            stdout = result.stdout.strip() if result.stdout else None
            stderr = result.stderr.strip() if result.stderr else None

            if command.lower() in ['create', 'info']:
                if stdout: print(f"    Matool Stdout:\n      {stdout.replace(chr(10), chr(10)+'      ')}")
                if stderr: print(f"    Matool Stderr:\n      {stderr.replace(chr(10), chr(10)+'      ')}")

            if result.returncode != 0:
                error_msg = f"Команда matool {command} завершилась с кодом {result.returncode}."
                print(f"  Matool ОШИБКА: {error_msg}")
                if stderr: print(f"    Matool Stderr: {stderr}")
                return stdout, stderr, error_msg

            return stdout, stderr, None

        except FileNotFoundError:
            error_msg = f"Не удалось запустить команду {command}. Убедитесь, что {self.executable_path} доступен."
            print(f"  Matool КРИТ. ОШИБКА: {error_msg}")
            return None, None, error_msg
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
            format_match = re.search(r"Encoding:\.*?\s*([A-Za-z0-9\-]+)", stdout, re.IGNORECASE)
            if format_match:
                result['format_raw'] = format_match.group(1).lower()
                std_format = result['format_raw'].replace('-', '')
                if std_format in ["rgb565", "rgba4444", "rgba5551", "rgba"]:
                     result['format_standardized'] = std_format
                # Определяем альфу для известных форматов
                if std_format in ["rgba4444", "rgba5551", "rgba"]:
                    result['has_alpha'] = True
            else:
                # Ищем RGBA в Color mode, если Encoding не найден
                mode_match = re.search(r"Color mode:\.*?\s*(RGBA)", stdout, re.IGNORECASE)
                if mode_match:
                    result['has_alpha'] = True
                    result['format_standardized'] = "rgba" # Неясный формат, но с альфой

            if result['format_standardized'] is None:
                 result['format_standardized'] = "rgba" if result['has_alpha'] else "unknown"

        except Exception as e_fmt:
            result['error'] = f"Ошибка парсинга формата: {e_fmt}"
            print(f"  Matool ОШИБКА парсинга: {result['error']}")

        try:
            texture_count_match = re.search(r"Total textures:\.*?\s*(\d+)", stdout)
            if texture_count_match:
                result['texture_count'] = int(texture_count_match.group(1))
            else:
                 print(f"  Matool ПРЕДУПРЕЖДЕНИЕ: Не удалось определить количество текстур для {mat_path.name}.")
                 result['texture_count'] = None
        except Exception as e_cnt:
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