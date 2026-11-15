"""Выполнение сценариев в браузере через Selenium."""
import os
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from . import db

TIMEOUT = int(os.getenv("STEP_TIMEOUT", "10"))  
HEADLESS = os.getenv("HEADLESS", "1") == "1"    


ACTIONS = {
    "open":           {"label": "Открыть страницу",           "target": None,           "value": "URL, например https://shop3-test.mts.by"},
    "click":          {"label": "Кликнуть по элементу",       "target": "CSS-селектор", "value": None},
    "type":           {"label": "Ввести текст",               "target": "CSS-селектор", "value": "Текст для ввода"},
    "press_enter":    {"label": "Нажать Enter в поле",        "target": "CSS-селектор", "value": None},
    "wait":           {"label": "Пауза",                      "target": None,           "value": "Секунды, например 2"},
    "assert_visible": {"label": "Проверить: элемент виден",   "target": "CSS-селектор", "value": None},
    "assert_text":    {"label": "Проверить: текст элемента",  "target": "CSS-селектор", "value": "Ожидаемый текст (часть)"},
    "assert_title":   {"label": "Проверить: заголовок вкладки", "target": None,         "value": "Ожидаемый текст (часть)"},
    "assert_url":     {"label": "Проверить: адрес страницы",  "target": None,           "value": "Ожидаемый текст (часть)"},
}


def make_driver() -> webdriver.Chrome:
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1366,900")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
   
    return webdriver.Chrome(options=options)


def execute_step(driver: webdriver.Chrome, step: dict) -> None:
    """Выполняет один шаг. Если что-то не так, бросает исключение."""
    action, target, value = step["action"], step["target"], step["value"]
    wait = WebDriverWait(driver, TIMEOUT)
    
    if target.startswith("//") or target.startswith("("):
        locator = (By.XPATH, target)
    else:
        locator = (By.CSS_SELECTOR, target)

    if action == "open":
        driver.get(value)
    elif action == "click":
        element = wait.until(EC.element_to_be_clickable(locator))
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.5) 
        try:
            element.click()
        except Exception:
            
            driver.execute_script("arguments[0].click();", element)
    elif action == "type":
        field = wait.until(EC.visibility_of_element_located(locator))
        field.clear()
        field.send_keys(value)
    elif action == "press_enter":
        wait.until(EC.visibility_of_element_located(locator)).send_keys(Keys.ENTER)
    elif action == "wait":
        time.sleep(float(value))
    elif action == "assert_visible":
        wait.until(EC.visibility_of_element_located(locator))
    elif action == "assert_text":
        element = wait.until(EC.visibility_of_element_located(locator))
        if value not in element.text:
            raise AssertionError(f"Текст «{value}» не найден. Фактический текст: «{element.text[:100]}»")
    elif action == "assert_title":
        wait.until(lambda d: value in d.title)
    elif action == "assert_url":
        wait.until(lambda d: value in d.current_url)
    else:
        raise ValueError(f"Неизвестное действие: {action}")


def _short_error(error: Exception) -> str:
    """Короткий текст ошибки без длинного стека Selenium."""
    text = str(error).strip()
    first_line = text.splitlines()[0] if text else ""
    return f"{type(error).__name__}: {first_line}".rstrip(": ")


def _save_step(run_id, position, step, status, message, duration_ms) -> None:
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO run_steps
               (run_id, position, action, target, value, status, message, duration_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (run_id, position, step["action"], step["target"], step["value"],
             status, message, duration_ms),
        )


def _finish_run(run_id: int, status: str) -> None:
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE runs SET status = %s, finished_at = now() WHERE id = %s",
            (status, run_id),
        )


def run_scenario(run_id: int, steps: list[dict]) -> None:
    """Запускает все шаги по порядку. После первой ошибки остальные шаги пропускаются."""
    run_status = "passed"
    driver = None
    driver_error = ""
    try:
        try:
            driver = make_driver()
        except Exception as error:  # noqa: BLE001 - браузер мог не запуститься по любой причине
            driver_error = _short_error(error)

        for position, step in enumerate(steps, start=1):
            if run_status == "failed":
                _save_step(run_id, position, step, "skipped", "Пропущен из-за ошибки выше", 0)
                continue

            started = time.monotonic()
            status, message = "passed", ""
            try:
                if driver is None:
                    raise RuntimeError(f"Не удалось запустить браузер: {driver_error}")
                execute_step(driver, step)
            except TimeoutException:
                status = "failed"
                message = f"Не дождались за {TIMEOUT} с: {step['target'] or step['value']}"
            except Exception as error:  # noqa: BLE001 - любая ошибка шага = шаг провален
                status, message = "failed", _short_error(error)

            duration_ms = int((time.monotonic() - started) * 1000)
            _save_step(run_id, position, step, status, message, duration_ms)
            if status == "failed":
                run_status = "failed"
    except Exception:  # noqa: BLE001 - например, пропала база данных
        run_status = "failed"
    finally:
        if driver is not None:
            driver.quit()
        _finish_run(run_id, run_status)
