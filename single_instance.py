"""
Защита от второго запуска.

Если CtrlNote уже работает, новый запуск сразу завершается —
чтобы не было двух иконок в трее и конфликта горячих клавиш.
"""

from __future__ import annotations

import ctypes
import sys

# Код ошибки Windows: объект с таким именем уже существует
ERROR_ALREADY_EXISTS = 183
# Уникальное имя «замка» для CtrlNote в системе
_MUTEX_NAME = "Local\\CtrlNoteSingleInstanceMutex"
_mutex_handle = None  # держим ссылку, чтобы Windows не освободила mutex раньше времени


def ensure_single_instance() -> bool:
    """
    Проверяет, можно ли продолжать запуск.

    Возвращает True — это первый экземпляр, работаем дальше.
    Возвращает False — уже есть другой CtrlNote, выходим.
    """
    global _mutex_handle
    # На не-Windows просто разрешаем запуск
    if sys.platform != "win32":
        return True

    kernel32 = ctypes.windll.kernel32
    # Создаём системный mutex; если он уже есть — значит программа запущена
    _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return False
    return True
