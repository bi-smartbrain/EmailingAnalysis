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



def get_objects(json_query, only_totals=False):
    """Получение сущностей по json-запросу"""
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


def extract_subject_key_improved(
        subject: str,
        known_phrases: Optional[List[str]] = None,
        all_subjects: Optional[List[str]] = None,
        min_phrase_words: int = 4,
        min_percentage: float = 1.0,
        min_absolute_count: int = 3,
        prefer_shorter_common: bool = True  # Новый параметр!
) -> Optional[str]:
    """
    Извлекает ключевую фразу из темы письма.
    prefer_shorter_common: если True, предпочитает более короткие общие фразы
    """

    @lru_cache(maxsize=10000)
    def clean_text_cached(text: str) -> str:
        """Очищает текст."""
        text = re.sub(r'^(Re:|Fwd:|Fw:|🚀|📧|\s*[-–—|]*\s*)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'[|/\\–—]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip().lower()
        return text

    def get_ngrams(text: str, min_n: int, max_n: int) -> List[str]:
        """Генерирует n-граммы."""
        words = text.split()
        ngrams = []
        for n in range(min_n, min(max_n, len(words)) + 1):
            for i in range(len(words) - n + 1):
                ngram = ' '.join(words[i:i + n])
                ngrams.append(ngram)
        return ngrams

    # ШАГ 1: Очищаем тему
    cleaned_subject = clean_text_cached(subject)
    if not cleaned_subject:
        return None

    # ШАГ 2: Проверяем известные фразы
    if known_phrases:
        for phrase in known_phrases:
            if clean_text_cached(phrase) in cleaned_subject:
                return phrase

    # ШАГ 3: Находим ВСЕ подходящие фразы из частотных
    if all_subjects:
        cleaned_all = [clean_text_cached(s) for s in all_subjects if s]
        total_subjects = len(cleaned_all)

        # Динамический порог
        dynamic_min_count = max(min_absolute_count, int(total_subjects * min_percentage / 100))

        # Собираем и считаем n-граммы
        all_ngrams = []
        for s in cleaned_all:
            ngrams = get_ngrams(s, min_phrase_words, min_phrase_words + 4)  # +4 для гибкости
            all_ngrams.extend(ngrams)

        ngram_counts = Counter(all_ngrams)

        # Находим все фразы, которые подходят для текущей темы
        candidate_phrases = []
        for ngram, count in ngram_counts.items():
            if count >= dynamic_min_count and ngram in cleaned_subject:
                candidate_phrases.append((ngram, count, len(ngram.split())))

        # Если нашли кандидатов, выбираем лучшего
        if candidate_phrases:
            if prefer_shorter_common:
                # Сортируем: сначала по частоте, потом по длине (предпочитаем короче)
                candidate_phrases.sort(key=lambda x: (-x[1], x[2], x[0]))
            else:
                # Сортируем: сначала по длине (предпочитаем длиннее), потом по частоте
                candidate_phrases.sort(key=lambda x: (-x[2], -x[1], x[0]))

            best_phrase = candidate_phrases[0][0]
            return ' '.join(word.capitalize() for word in best_phrase.split())

    # Если ничего не нашли
    return None


def add_subject_key_into_emails(emails, known_phrases=None, update_phrases=True):
    """
    Ищет ключевые фразы в теме письма и добавляет ее в поле subject_key.
    Инкрементально обновляет список известных фраз.

    Args:
        emails: список словарей с данными писем (должен содержать 'subject')
        known_phrases: начальный список известных фраз (опционально)
        update_phrases: обновлять ли список фраз в процессе (True по умолчанию)

    Returns:
        dict: {
            'emails': список писем с добавленным 'subject_key',
            'phrases': обновленный список известных фраз,
            'phrase_stats': статистика по фразам (Counter),
            'coverage': процент писем, получивших subject_key
        }
    """
    if known_phrases is None:
        known_phrases = []

    # Создаем копию списка фраз для модификации
    current_phrases = known_phrases.copy()
    email_results = []
    phrase_counter = Counter()

    # Собираем все темы для анализа в extract_subject_key_improved
    all_subjects = [email['subject'] for email in emails]

    print(f"Обработка {len(emails)} писем...")
    print(f"Начальный список фраз: {len(current_phrases)}")

    for email in tqdm(emails, desc="Обработка писем"):
        # Извлекаем ключевую фразу из темы
        subject_key = extract_subject_key_improved(
            subject=email['subject'],
            known_phrases=current_phrases,
            all_subjects=all_subjects,
            min_phrase_words=4,
            min_percentage=0.05,
            min_absolute_count=2
        )

        # Добавляем результат к email
        email_with_key = email.copy()  # Создаем копию, чтобы не модифицировать исходный
        email_with_key['subject_key'] = subject_key
        email_results.append(email_with_key)

        # Обновляем статистику
        if subject_key and subject_key != 'unknown':
            phrase_counter[subject_key] += 1

        # Инкрементально обновляем список фраз
        if update_phrases and subject_key and subject_key != 'unknown':
            if subject_key not in current_phrases:
                # Проверяем, не является ли новая фраза подфразой существующей
                is_subphrase = False
                for existing_phrase in current_phrases:
                    if subject_key in existing_phrase or existing_phrase in subject_key:
                        # Оставляем более длинную фразу
                        if len(subject_key) > len(existing_phrase):
                            current_phrases.remove(existing_phrase)
                            current_phrases.append(subject_key)
                            print(f"Обновлена фраза: '{existing_phrase}' → '{subject_key}'")
                        is_subphrase = True
                        break

                if not is_subphrase:
                    current_phrases.append(subject_key)

    # Сортируем фразы по частоте использования
    sorted_phrases = sorted(current_phrases,
                            key=lambda x: phrase_counter.get(x, 0),
                            reverse=True)

    # Вычисляем покрытие
    emails_with_key = sum(1 for email in email_results
                          if email.get('subject_key') and email['subject_key'] != 'unknown')
    coverage = (emails_with_key / len(email_results)) * 100 if email_results else 0

    print(f"\nРезультаты:")
    print(f"- Обработано писем: {len(email_results)}")
    print(f"- Писем с определенной темой: {emails_with_key} ({coverage:.1f}%)")
    print(f"- Уникальных фраз: {len(sorted_phrases)}")
    print(f"- Топ-5 фраз: {list(phrase_counter.most_common(5))}")

    return {
        'emails': email_results,
        'phrases': sorted_phrases,
        'phrase_stats': dict(phrase_counter.most_common()),
        'coverage': coverage
    }


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