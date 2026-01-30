#%%
# # создание диапазонов на основе crash_ranges
# date_ranges = []
# for arange in crash_ranges:
#     item = {
#         'after_dt': arange[0],
#         'before_dt': arange[1],
#     }
#     date_ranges.append(item)
#%%
# # создание кастом диапазона
#
# st_dt = dt.datetime(year=2026, month=1, day=8, hour=0, minute=35, second=0, microsecond=0)
# en_dt = dt.datetime(year=2026, month=1, day=8, hour=0, minute=40, second=0, microsecond=0)
# date_ranges = [{
#         'after_dt': st_dt,
#         'before_dt': en_dt,
#     }]
#%%





def get_leads_by_emails_dt(after_dt, before_dt, fields_lst=None, only_totals=False):
    query_row = """{
    "_limit": 200,
    "query": {
        "negate": false,
        "queries": [
            {
                "negate": false,
                "object_type": "lead",
                "type": "object_type"
            },
            {
                "negate": false,
                "queries": [
                    {
                        "negate": false,
                        "related_object_type": "activity.email",
                        "related_query": {
                            "negate": false,
                            "queries": [
                                {
                                    "condition": {
                                        "before": null,
                                        "on_or_after": {
                                            "type": "fixed_utc",
                                            "value": "2025-12-08T21:12:12+00:00"
                                        },
                                        "type": "moment_range"
                                    },
                                    "field": {
                                        "field_name": "date",
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
                                            "value": "2025-12-09T21:12:12+00:00"
                                        },
                                        "on_or_after": null,
                                        "type": "moment_range"
                                    },
                                    "field": {
                                        "field_name": "date",
                                        "object_type": "activity.email",
                                        "type": "regular_field"
                                    },
                                    "negate": false,
                                    "type": "field_condition"
                                }
                            ],
                            "type": "and"
                        },
                        "this_object_type": "lead",
                        "type": "has_related"
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
                "object_type": "lead",
                "type": "regular_field"
            }
        }
    ]
}"""
    after_dt -= dt.timedelta(hours=3)
    before_dt -= dt.timedelta(hours=3)

    after_str = after_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    before_str = before_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    query_row = query_row.replace("2025-12-08T21:12:12+00:00", after_str)
    query_row = query_row.replace("2025-12-09T21:12:12+00:00", before_str)
    query = json.loads(query_row)
    if fields_lst:
        query["_fields"] = {"lead": fields_lst}
    resp = get_objects(query, only_totals=only_totals)
    return resp


def detect_lead_age(lead, email=None):
    """Определяет возраст лида на основе даты его создания.
        Возвращает словарь по форме {age_group: Новые, age_days: 27}"""

    try:
        # Парсим дату создания лида и добавляем 3 часа
        lead_created_str = lead['date_created'].split('+')[0]
        lead_created_dt = pd.to_datetime(lead_created_str)
        lead_created_dt += dt.timedelta(hours=3)

        # Определяем дату сравнения
        compare_dt = dt.datetime.today()
        if email:
            compare_str = email['date_sent'].split('+')[0]
            compare_dt = pd.to_datetime(compare_str)
            compare_dt += dt.timedelta(hours=3)

        # Сравниваем даты и определяем возрастную группу
        days_diff = (compare_dt - lead_created_dt).days

        if days_diff < 30:
            age_group = "1.Молодые"
        elif days_diff <= 365:
            age_group = "2.Зрелые"
        else:
            age_group = "3.Старые"

        return {'age_group': age_group, 'age_days': days_diff}

    except Exception as e:
        return f'Error: не удалось определить возраст лида: {str(e)}'


def get_leads_from_query(query, skip=0, maximum=10000000000):
    params = {
        "query": query,
        "_skip": skip,
        "_limit": 100
    }

    leads = []
    while True:
        resp = f.api.get('lead', params=params)
        leads.extend(resp['data'])
        if resp['has_more'] and len(leads) < maximum:
            params['_skip'] += params['_limit']
            print(f'{len(leads)} лидов получено')
        else:
            print(f'Всего {len(leads)} лидов получено')
            return leads


def detect_primary_status(email: dict) -> str:
    """
    Определяет первичность письма.

    Returns:
        'primary', 'follow_up' или строка с ошибкой
    """
    try:
        # 1. Проверка на главное письмо из сервиса рассылок
        if email.get('created_by_name') is None:
            return 'primary'

        # 2. Обработка писем, отправленных из CRM
        # а) Проверка followup_sequence_id
        followup_seq_id = email.get('followup_sequence_id')
        if followup_seq_id is not None and str(followup_seq_id).strip() != '':
            return 'follow_up'

        # б) Проверка ключевых слов в template_name
        template_name = email.get('template_name', '')
        if not isinstance(template_name, str):
            template_name = str(template_name)

        template_lower = template_name.lower()
        follow_keywords = ['follow', 'пинок', 'fup']

        for keyword in follow_keywords:
            if keyword in template_lower:
                return 'follow_up'

        # в) Проверка цифр 2-9 в начале или конце template_name
        # Очищаем от лишних пробелов
        template_clean = template_name.strip()

        if template_clean:
            # Проверяем начало строки
            first_char = template_clean[0]
            if first_char.isdigit() and '2' <= first_char <= '9':
                return 'follow_up'

            # Проверяем конец строки
            last_char = template_clean[-1]
            if last_char.isdigit() and '2' <= last_char <= '9':
                return 'follow_up'

        # Если ни одно условие для follow_up не сработало - это primary
        return 'primary'

    except Exception as e:
        return f'Error: не удалось определить первичность письма: {str(e)}'


def get_pre_sent_emails(email, lead):
    """Получает предыдущие отправленные письма в лиде"""
    after_str = "1990-01-01T00:00:00+00:00"
    after_dt = dt.datetime.strptime(after_str, "%Y-%m-%dT%H:%M:%S+00:00")
    before_dt = pd.to_datetime(email['date_sent'])
    pre_sent_emails = get_sent_emails(after_dt, before_dt, lead_id=lead['id'])
    return pre_sent_emails


def find_common_patterns(all_subjects, min_count=5):
    """Находит общие паттерны, игнорируя названия компаний."""

    @lru_cache(maxsize=10000)
    def clean_text(text: str) -> str:
        text = re.sub(r'^(Re:|Fwd:|Fw:|🚀|📧|\s*[-–—|]*\s*)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'[|/\\–—]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip().lower()
        return text

    # Собираем статистику по 3-словным фразам
    all_3grams = []
    for subject in all_subjects:
        cleaned = clean_text(subject)
        words = cleaned.split()
        if len(words) >= 3:
            for i in range(len(words) - 2):
                phrase = ' '.join(words[i:i + 3])
                all_3grams.append(phrase)

    # Подсчитываем частоту
    counter = Counter(all_3grams)

    # Фильтруем и сортируем
    common_phrases = []
    for phrase, count in counter.items():
        if count >= min_count:
            # Проверяем, что это не фраза с именем компании
            # (простейшая эвристика - не содержит 's, Ltd, Inc и т.д.)
            if not any(x in phrase for x in ["'s", " ltd", " inc", " corp", " co", " llc"]):
                common_phrases.append((phrase, count))

    # Сортируем по частоте
    common_phrases.sort(key=lambda x: -x[1])

    return [phrase.capitalize() for phrase, _ in common_phrases]


