import os
from dotenv import load_dotenv
from closeio_api import Client
import gspread
from gspread.utils import rowcol_to_a1
from env_loader import SECRETS_PATH
from sqlalchemy import create_engine
import json
import datetime as dt
import re
from collections import Counter
from typing import List, Dict, Optional
from functools import lru_cache
from tqdm import tqdm
import pandas as pd


SERVICE_ACCOUNT_FILE = os.path.join(SECRETS_PATH, 'service_account.json')
gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)

CONN_STR = os.getenv('CONN_STR')
api_key = os.getenv('CLOSE_API_KEY_MARY')
api = Client(api_key)


def df_columns_add_hours(df, columns=None, delta=3):
    """Приводит колонки в датафрейме к МСК времени, добавляя опциональное количество часов"""
    if columns is None:
        columns = ['date_created', 'date_sent']
    for col in columns:
        df[col] = df[col].str[:19]
        df[col] = pd.to_datetime(df[col]) + dt.timedelta(hours=delta)

    return df


def df_to_sheets_report(data_frame):
    """Преобразует pandas-датафрейм в список списков подходящий для записи в гугл-таблицу"""
    data_frame.fillna('', inplace=True)
    sheets_report = [data_frame.columns.tolist()] + data_frame.values.tolist()
    return sheets_report


def write_spread_sheet(spread, sheet, report):
    """Перезаписывает лист гугл таблицы"""
    sh = gc.open(spread)
    worksheet = sh.worksheet(sheet)
    worksheet.clear()
    print(f"Лист {sheet} в таблице {spread} очищен")

    # Получить размеры отчета (количество строк и столбцов)
    num_rows = len(report)
    num_cols = len(report[0])

    # Получить диапазон для записи данных
    start_cell = rowcol_to_a1(1, 1)
    end_cell = rowcol_to_a1(num_rows, num_cols)

    # Записать значения в диапазон
    cell_range = f"{start_cell}:{end_cell}"
    worksheet.update(report, cell_range, value_input_option="user_entered")

    print("Отчет записан")


def get_objects(json_query, only_totals=False, fields_lst=None):
    """Получение сущностей по json-запросу"""
    if fields_lst:
        json_query['_fields'] = {"activity.email": fields_lst}
    json_query['include_counts'] = True
    if only_totals:
        response = api.post('data/search/', data=json_query)
        return response['count']['total']

    objects = []
    while True:
        response = api.post('data/search/', data=json_query)
        objects.extend(response['data'])
        print(f"Получено: {len(objects)} из {response['count']['total']}")
        if response['cursor']:
            json_query['cursor'] = response['cursor']
        else:
            break
    return objects


def load_df_from_db(table_name, query=None, limit=None, conn_str=CONN_STR):
    """
    Загружает данные из таблицы PostgreSQL в DataFrame.

    Args:
        table_name: Название таблицы для загрузки
        query: Кастомный SQL запрос (опционально)
        limit: Ограничение количества строк (опционально)

    Returns:
        pandas DataFrame с данными из таблицы
    """

    print(f"Загрузка данных из таблицы '{table_name}'...")

    # Формируем SQL запрос
    if query:
        sql = query
        print(f"Используется кастомный запрос")
    else:
        if limit:
            sql = f"SELECT * FROM {table_name} LIMIT {limit}"
        else:
            sql = f"SELECT * FROM {table_name}"

    print(f"SQL запрос: {sql}")

    engine = create_engine(conn_str)
    try:
        # Выполняем запрос и загружаем в DataFrame
        df = pd.read_sql(sql, engine)
        engine.dispose()
        print(f"✓ Загружено строк: {len(df)}, колонок: {len(df.columns)}")
        return df

    except Exception as e:
        print(f"✗ Ошибка при загрузке данных: {e}")
        engine.dispose()
        return pd.DataFrame()  # Возвращаем пустой DataFrame при ошибке


def get_sent_emails(after_dt, before_dt, fields_lst=None, only_totals=False, lead_id=None):
    query_row = """
        {
        "_limit": 200,
        "query": {
            "negate": false,
            "queries": [
                {
                    "negate": false,
                    "object_type": "activity.email",
                    "type": "object_type"
                },
                {
                    "negate": false,
                    "queries": [
                        {
                            "negate": false,
                            "queries": [
                                {
                                    "condition": {
                                        "before": null,
                                        "on_or_after": {
                                            "type": "fixed_utc",
                                            "value": "2025-12-18T13:33:33+00:00"
                                        },
                                        "type": "moment_range"
                                    },
                                    "field": {
                                        "field_name": "date_sent",
                                        "object_type": "activity.email",
                                        "type": "regular_field"
                                    },
                                    "negate": false,
                                    "type": "field_condition"
                                },
                                {
                                    "condition": {
                                        "type": "term",
                                        "values": [
                                            "outgoing"
                                        ]
                                    },
                                    "field": {
                                        "field_name": "direction",
                                        "object_type": "activity.email",
                                        "type": "regular_field"
                                    },
                                    "negate": false,
                                    "type": "field_condition"
                                },
                                {
                                    "condition": {
                                        "before": {
                                            "type": "fixed_utc",
                                            "value": "2025-12-18T13:34:34+00:00"
                                        },
                                        "on_or_after": null,
                                        "type": "moment_range"
                                    },
                                    "field": {
                                        "field_name": "date_sent",
                                        "object_type": "activity.email",
                                        "type": "regular_field"
                                    },
                                    "negate": false,
                                    "type": "field_condition"
                                }
                            ],
                            "type": "and"
                        }
                    ],
                    "type": "and"
                }
            ],
            "type": "and"
        },
        "results_limit": null,
        "sort": [
            {
                "direction": "desc",
                "field": {
                    "field_name": "date_created",
                    "object_type": "activity.email",
                    "type": "regular_field"
                }
            }
        ]
    }
    """
    after_dt -= dt.timedelta(hours=3)
    before_dt -= dt.timedelta(hours=3)

    after_str = after_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    before_str = before_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    query_row = query_row.replace("2025-12-18T13:33:33+00:00", after_str)
    query_row = query_row.replace("2025-12-18T13:34:34+00:00", before_str)
    query = json.loads(query_row)

    if fields_lst:
        query['_fields'] = {"activity.email": fields_lst}

    if lead_id:
        related_query = {
            "negate": False,
            "related_object_type": "lead",
            "related_query": {
                "negate": False,
                "queries": [
                    {
                        "mode": "exact_value",
                        "negate": False,
                        "type": "text",
                        "value": f"{lead_id}"
                    }
                ],
                "type": "and"
            },
            "this_object_type": "activity.email",
            "type": "has_related"
        }
        query["query"]['queries'].append(related_query)
    resp = get_objects(query, only_totals=only_totals)
    return resp


def add_subject_key_into_emails(emails, known_phrases):
    """
    Ищет ключевые фразы в теме письма и добавляет ее в поле subject_key.

    Args:
        emails: список словарей с данными писем (должен содержать 'subject')
        known_phrases: начальный список известных фраз

    Returns:
        'emails': обработанный список писем с добавленным 'subject_key, если найден',
    """

    email_results = []
    for email in emails:
        email_with_key = email.copy()
        email_with_key['subject_key'] = None  # Инициализируем пустым

        # Ищем первую подходящую фразу
        for phrase in known_phrases:
            if phrase.lower() in email['subject'].lower():
                email_with_key['subject_key'] = phrase
                break  # Прерываем поиск после первого совпадения

        # Добавляем обработанное письмо в результаты
        email_results.append(email_with_key)

    return email_results


def create_date_ranges(start_dt: dt.datetime,
                       end_dt: dt.datetime,
                       interval_min: int) -> List[Dict[str, dt.datetime]]:
    """
    Разрезает временной период на равные интервалы.

    Args:
        start_dt: Начало периода
        end_dt: Конец периода
        interval_min: Длина интервала в минутах

    Returns:
        Список словарей {'after_dt': ..., 'before_dt': ...}
    """
    date_ranges = []
    current_start = start_dt

    while current_start < end_dt:
        current_end = min(current_start + dt.timedelta(minutes=interval_min), end_dt)
        date_ranges.append({
            'after_dt': current_start,
            'before_dt': current_end
        })
        current_start = current_end

    # Вывод для контроля
    print(f"Создано диапазонов: {len(date_ranges)}")
    print(f"Период: {start_dt.strftime('%d.%m.%Y %H:%M:%S')} - {end_dt.strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"Интервал: {interval_min} минут")

    return date_ranges


def get_sheet_range(spread, sheet, arange):
    print(f"Получение данных из таблицы {spread} - {sheet}")
    sh = gc.open(spread)
    data = sh.worksheet(sheet).get(arange)
    print("Данне получены")
    return data


def add_report_to_sheet(spread, sheet, report):
    """
    Добавляет на лист данные отчета без удаления уже существующих там записей
    :param spread: гугл таблица (название)
    :param sheet: название листа
    :param report: отчет в виде списка списков
    :return: None
    """
    sh = gc.open(spread)
    worksheet = sh.worksheet(sheet)

    # Получить размеры отчета (количество строк и столбцов)
    num_rows = len(report)
    num_cols = len(report[0])

    # Получить диапазон для записи данных
    q_rows = len(worksheet.get_all_values())  # узнаем кол-во уже заполненных на листе строк

    start_cell = rowcol_to_a1(q_rows + 1, 1)
    end_cell = rowcol_to_a1(q_rows + num_rows, num_cols)

    # Записать значения в диапазон
    cell_range = f"{start_cell}:{end_cell}"
    worksheet.update(cell_range, report, value_input_option="user_entered")

    print("Отчет добавлен")


def save_df_to_db(data_frame, table_name, mode='append', conn_str=CONN_STR):
    print("Сохранение в БД...")
    engine = create_engine(conn_str)
    resp = data_frame.to_sql(
        name=table_name,       # название таблицы
        con=engine,            # подключение
        if_exists=mode,        # 'fail', 'replace' или 'append'
        index=False,           # не сохранять индексы
        chunksize=1000         # порционная запись
    )
    print(f"Сохранено строк: {len(data_frame)}")
    engine.dispose()
    return resp